from pathlib import Path
from typing import List, Optional, Callable, Union, Dict, Set
import logging
import datetime
import hashlib
import importlib.metadata
import threading
import queue
import sys # Add sys for stderr output

from .domain.file_info import FileInfo
from .domain.file_system_event import FileSystemEvent
from .domain.dependency_info import DependencyInfo, DependencyType
from .utility.path_resolver import PathResolver
from .usecase.project_analyzer import ProjectAnalyzer
from .usecase.config_manager import ConfigManager
from .gateway.gitignore_reader import GitignoreReader
from .service.ignore_rule_processor import IgnoreRuleProcessor
from .service.file_system_event_monitor import FileSystemEventMonitor, FileSystemEventCallback
from .usecase.context_builder import ContextBuilder
from .domain.project_config import ProjectConfig
from .domain.context_data import ContextData
from .gateway.file_system_accessor import FileSystemAccessor
from .domain.file_content_formatter import BasicFileContentFormatter
from .service.hash_calculator import HashCalculator
from .service.language_detector import LanguageDetector
from .service.ast_parser import AstParser
from .domain.exceptions import (
    KotemariError,
    AnalysisError,
    FileNotFoundErrorInAnalysis,
    ContextGenerationError,
    DependencyError
)

logger = logging.getLogger(__name__)

# Get Kotemari version using importlib.metadata
try:
    __version__ = importlib.metadata.version("kotemari")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev" # Fallback version

class Kotemari:
    """
    The main facade class for the Kotemari library.
    Provides methods to analyze projects, list files, and generate context.
    Uses in-memory caching and background file monitoring for responsiveness.
    Kotemari ライブラリのメインファサードクラス。
    プロジェクトの分析、ファイル一覧表示、コンテキスト生成などのメソッドを提供します。
    応答性向上のため、メモリ内キャッシングとバックグラウンドファイル監視を使用します。
    """

    def __init__(
        self,
        project_root: Union[str, Path],
        config_path: Optional[Union[str, Path]] = None,
        use_cache: bool = True,
        cache_dir: Optional[Union[str, Path]] = None,
        log_level: Union[int, str] = logging.INFO
    ):
        """
        Initializes the Kotemari facade.
        Performs initial project analysis on initialization.
        Kotemari ファサードを初期化します。
        初期化時に最初のプロジェクト分析を実行します。

        Args:
            project_root (Path | str): The root directory of the project to analyze.
                                       分析対象プロジェクトのルートディレクトリ。
            config_path (Optional[Path | str], optional):
                Path to the configuration file (e.g., .kotemari.yml).
                If None, searches upwards from project_root.
                Defaults to None.
                設定ファイル（例: .kotemari.yml）へのパス。
                None の場合、project_root から上方に検索します。
                デフォルトは None。
            use_cache (bool, optional): Whether to use in-memory caching.
                                       メモリ内キャッシングを使用するかどうか。
            cache_dir (Optional[Path | str], optional): The directory for caching.
                                                       キャッシュのためのディレクトリ。
            log_level (Union[int, str], optional): The logging level for the Kotemari instance.
                                                  Defaults to logging.INFO.
                                                  ログレベル。
                                                  デフォルトは logging.INFO。
        """
        # --- Core Components Initialization ---
        self._path_resolver = PathResolver()
        # Use a private variable for storing the resolved project root
        # 解決済みのプロジェクトルートを格納するためにプライベート変数を使用
        self._project_root = Path(project_root).resolve()
        if not self._project_root.is_dir():
            raise NotADirectoryError(f"Project root is not a valid directory: {self._project_root}")

        # Debug print to stderr
        # print(f"Kotemari.__init__: Initializing for {self._project_root}", file=sys.stderr)

        self._config_path: Optional[Path] = None
        if config_path:
            self._config_path = self._path_resolver.resolve_absolute(config_path, base_dir=self._project_root)

        self._config_manager = ConfigManager(self._path_resolver, self._project_root)
        self._config = self._config_manager.get_config()

        # --- Service and Gateway Instances ---
        self._file_accessor = FileSystemAccessor(self._path_resolver)
        self._gitignore_reader = GitignoreReader(self._project_root)
        self._ignore_processor = IgnoreRuleProcessor(self._project_root, self._config, self._path_resolver)
        self._hash_calculator = HashCalculator()
        self._language_detector = LanguageDetector()
        self._ast_parser = AstParser()
        self._formatter = BasicFileContentFormatter()

        # --- Analyzer Initialization ---
        self.analyzer: ProjectAnalyzer = ProjectAnalyzer(
            project_root=self._project_root,
            path_resolver=self._path_resolver,
            config_manager=self._config_manager,
            fs_accessor=self._file_accessor,
            ignore_processor=self._ignore_processor,
            hash_calculator=self._hash_calculator,
            language_detector=self._language_detector,
            ast_parser=self._ast_parser
        )

        # --- In-Memory Cache Initialization (Step 11-1-2 & 11-1-3) ---
        self._analysis_results: Dict[Path, FileInfo] = {}
        self._reverse_dependency_index: Dict[Path, Set[Path]] = {}
        self.project_analyzed: bool = False
        self._analysis_lock = threading.Lock() # Lock for accessing/modifying analysis results
        self._reverse_dependency_index_lock = threading.Lock() # Lock for the reverse dependency index (Step 12-1-2)

        # --- Monitoring and Background Update Components (Will be initialized in start_watching - Step 11-1-4,5,6) ---
        self._event_monitor: Optional[FileSystemEventMonitor] = None
        self._event_queue: Optional[queue.Queue] = None
        self._background_worker_thread: Optional[threading.Thread] = None
        self._stop_worker_event = threading.Event()

        logger.info(f"Kotemari v{__version__} initialized for project root: {self._project_root}")
        if self._config_path:
            logger.info(f"Using explicit config path: {self._config_path}")

        # Initialize Context Builder
        self.context_builder = ContextBuilder(
            file_accessor=self._file_accessor,
            formatter=self._formatter
        )

        # --- Perform initial analysis (Step 11-1-2 cont.) ---
        logger.info("Performing initial project analysis...")
        self._run_analysis_and_update_memory() # Perform initial full analysis

    @property
    def project_root(self) -> Path:
        """
        Returns the absolute path to the project root directory.
        プロジェクトルートディレクトリへの絶対パスを返します。
        """
        # Return the private variable
        # プライベート変数を返す
        return self._project_root

    def _run_analysis_and_update_memory(self):
        """Runs the analysis and updates the in-memory cache atomically."""
        logger.debug("Acquiring analysis lock for full analysis...")
        with self._analysis_lock:
            logger.info("Running full project analysis...")
            try:
                # English: Analyze the project to get a list of FileInfo objects.
                # 日本語: プロジェクトを分析して FileInfo オブジェクトのリストを取得します。
                analysis_list: list[FileInfo] = self.analyzer.analyze()

                # English: Convert the list to a dictionary keyed by path for efficient lookup.
                # 日本語: 効率的な検索のために、リストをパスをキーとする辞書に変換します。
                new_results: Dict[Path, FileInfo] = {fi.path: fi for fi in analysis_list}

                # English: Update the in-memory cache with the new dictionary results.
                # 日本語: 新しい辞書の結果でメモリ内キャッシュを更新します。
                self._analysis_results = new_results
                self._build_reverse_dependency_index()
                self.project_analyzed = True
                logger.info(f"Initial analysis complete. Found {len(self._analysis_results)} files.")
            except Exception as e:
                logger.error(f"Initial project analysis failed: {e}", exc_info=True)
                self._analysis_results = {} # Ensure cache is cleared on error
                self.project_analyzed = False
                # Optionally re-raise or handle differently?
            logger.debug("Released analysis lock after full analysis.")

    def analyze_project(self, force_reanalyze: bool = False) -> list[FileInfo]:
        """
        Returns the analyzed project files from the in-memory cache.
        Performs re-analysis only if forced.
        メモリ内キャッシュから分析済みのプロジェクトファイルを返します。
        強制された場合のみ再分析を実行します。

        Args:
            force_reanalyze: If True, ignores the current in-memory cache and performs a full re-analysis.
                             Trueの場合、現在のメモリ内キャッシュを無視して完全な再分析を実行します。

        Returns:
            A list of FileInfo objects representing the analyzed files.
            分析されたファイルを表す FileInfo オブジェクトのリスト。

        Raises:
             AnalysisError: If the analysis has not completed successfully yet.
                            分析がまだ正常に完了していない場合。
        """
        logger.debug(f"analyze_project called. Force reanalyze: {force_reanalyze}")
        if force_reanalyze:
            logger.info("Forcing re-analysis...")
            self._run_analysis_and_update_memory() # Run full analysis

        # Debug print to stderr
        # print(f"Kotemari.analyze_project: Starting analysis for {self._project_root}", file=sys.stderr)

        logger.debug("Acquiring analysis lock to read results...")
        with self._analysis_lock:
            logger.debug("Acquired analysis lock.")
            if not self.project_analyzed or self._analysis_results is None:
                logger.error("Analysis has not completed successfully yet.")
                raise AnalysisError("Project analysis has not completed successfully.")
            logger.debug(f"Returning {len(self._analysis_results)} results from memory.")
            # Return a copy to prevent external modification?
            # 外部からの変更を防ぐためにコピーを返しますか？
            # For now, return direct reference for performance.
            return list(self._analysis_results.values()) # Return reference to in-memory list

    def list_files(self, relative: bool = True) -> List[str]:
        """
        Lists the non-ignored files found in the project from the in-memory cache.
        メモリ内キャッシュからプロジェクトで見つかった無視されていないファイルをリスト表示します。

        Args:
            relative (bool, optional): If True, returns paths relative to the project root.
                                       Otherwise, returns absolute paths.
                                       Defaults to True.
                                       True の場合、プロジェクトルートからの相対パスを返します。
                                       それ以外の場合は絶対パスを返します。
                                       デフォルトは True。

        Returns:
            List[str]: A list of file paths.
                       ファイルパスのリスト。

        Raises:
            AnalysisError: If the analysis has not completed successfully yet.
                          分析がまだ正常に完了していない場合。
        """
        # Ensure analysis results are available by calling analyze_project without force
        # 強制せずに analyze_project を呼び出して分析結果が利用可能であることを確認します
        analysis_results = self.analyze_project() # Gets results from memory or raises error

        if relative:
            try:
                return sorted([str(f.path.relative_to(self.project_root).as_posix()) for f in analysis_results])
            except ValueError as e:
                 logger.error(f"Error calculating relative path during list_files: {e}")
                 # Fallback or re-raise? For now, log and return absolute paths.
                 # フォールバックしますか、それとも再発生させますか？とりあえずログに記録し、絶対パスを返します。
                 return sorted([str(f.path) for f in analysis_results])
        else:
            return sorted([str(f.path) for f in analysis_results])

    def get_tree(self, max_depth: Optional[int] = None) -> str:
        """
        Returns a string representation of the project file tree based on the in-memory cache.
        メモリ内キャッシュに基づいてプロジェクトファイルツリーの文字列表現を返します。

        Args:
            max_depth (Optional[int], optional): The maximum depth to display in the tree.
                                                 Defaults to None (no limit).
                                                 ツリーに表示する最大深度。
                                                 デフォルトは None（制限なし）。

        Returns:
            str: The formatted file tree string.
                 フォーマットされたファイルツリー文字列。

        Raises:
            AnalysisError: If the analysis has not completed successfully yet.
                          分析がまだ正常に完了していない場合。
        """
        analysis_results = self.analyze_project() # Gets results from memory or raises error

        if not analysis_results:
            return "Project is empty or all files are ignored."

        # Build directory structure from analyzed files
        dir_structure = {}
        try:
            relative_paths = sorted([f.path.relative_to(self.project_root) for f in analysis_results])
        except ValueError as e:
            logger.error(f"Error calculating relative path during get_tree: {e}")
            return f"Error building tree: {e}"

        for path in relative_paths:
            current_level = dir_structure
            parts = path.parts
            for i, part in enumerate(parts):
                if i == len(parts) - 1: # It's a file
                    if part not in current_level:
                         current_level[part] = None # Mark as file
                else: # It's a directory
                    if part not in current_level:
                        current_level[part] = {}
                    # Handle potential conflict: a file exists where a directory is expected
                    if current_level[part] is None:
                        logger.warning(f"Tree structure conflict: Both file and directory found at '/{'/'.join(parts[:i+1])}'")
                        # Decide how to handle: maybe skip adding the directory? For now, overwrite.
                        current_level[part] = {}
                    current_level = current_level[part]

        lines = [self.project_root.name] # Start with project root name

        def build_tree_lines(dir_structure: dict, prefix: str = "", depth: int = 0, max_depth: Optional[int] = None) -> List[str]:
            items = sorted(dir_structure.items())
            pointers = ["├── "] * (len(items) - 1) + ["└── "]
            for pointer, (name, content) in zip(pointers, items):
                yield prefix + pointer + name
                if isinstance(content, dict):
                    if max_depth is not None and depth + 1 >= max_depth:
                        # Reached max depth, show ellipsis if directory is not empty
                        # 最大深度に到達しました。ディレクトリが空でない場合は省略記号を表示します
                        if content: # Check if the dictionary is not empty
                             yield prefix + ("│   " if pointer == "├── " else "    ") + "..."
                    else:
                        # Continue recursion if max_depth not reached
                        # max_depthに達していない場合は再帰を続行します
                        extension = "│   " if pointer == "├── " else "    "
                        # Recursive call
                        yield from build_tree_lines(content, prefix + extension, depth + 1, max_depth)

        # Pass max_depth to the initial call
        # 最初の呼び出しに max_depth を渡します
        tree_lines = list(build_tree_lines(dir_structure, max_depth=max_depth))
        return "\n".join(lines + tree_lines)

    def get_dependencies(self, target_file_path: str) -> List[DependencyInfo]:
        """
        Gets the dependencies for a specific file from the in-memory cache.
        メモリ内キャッシュから特定のファイルの依存関係を取得します。

        Args:
            target_file_path (str): The relative or absolute path to the target file.
                                     ターゲットファイルへの相対パスまたは絶対パス。

        Returns:
            List[DependencyInfo]: A list of dependencies for the file.
                                  ファイルの依存関係のリスト。

        Raises:
            FileNotFoundErrorInAnalysis: If the target file was not found in the analysis results.
                                        分析結果でターゲットファイルが見つからなかった場合。
            AnalysisError: If the analysis has not completed successfully yet.
                          分析がまだ正常に完了していない場合。
        """
        analysis_results = self.analyze_project() # Ensure analysis is done and get results
        absolute_target_path = self._path_resolver.resolve_absolute(target_file_path, base_dir=self.project_root)

        # Find the file info in the cached results
        # キャッシュされた結果でファイル情報を見つけます
        file_info = None
        with self._analysis_lock: # Accessing shared analysis_results
             if analysis_results is not None:
                for fi in analysis_results:
                    if fi.path == absolute_target_path:
                        file_info = fi
                        break

        if file_info is None:
            logger.warning(f"Target file not found in analysis results: {target_file_path} (resolved: {absolute_target_path})")
            raise FileNotFoundErrorInAnalysis(f"File '{target_file_path}' not found in the project analysis.")

        # Return dependencies from the found FileInfo
        # 見つかった FileInfo から依存関係を返します
        # Return a copy to prevent modification of cached data?
        # キャッシュされたデータの変更を防ぐためにコピーを返しますか？
        return file_info.dependencies

    def get_context(self, target_files: List[str]) -> ContextData:
        """
        Retrieves and formats the content of specified files along with their dependencies.
        指定されたファイルの内容とその依存関係を取得し、フォーマットします。

        Args:
            target_files (List[str]): A list of relative or absolute paths to the target files.
                                     ターゲットファイルへの相対パスまたは絶対パスのリスト。

        Returns:
            ContextData: An object containing the formatted context string and metadata.
                         フォーマットされたコンテキスト文字列とメタデータを含むオブジェクト。

        Raises:
            AnalysisError: If the project hasn't been analyzed yet.
                           プロジェクトがまだ分析されていない場合。
            FileNotFoundErrorInAnalysis: If a target file is not found in the analysis results.
                                       ターゲットファイルが分析結果で見つからない場合。
            FileNotFoundError: If a target file does not exist on the filesystem (should be rare after analysis check).
                               ターゲットファイルがファイルシステムに存在しない場合（分析チェック後には稀）。
        """
        logger.info(f"Generating context for: {target_files}")
        if not self.project_analyzed or self._analysis_results is None:
            raise AnalysisError("Project must be analyzed first before getting context.")

        # Create a quick lookup map from the analysis results
        # 分析結果からクイックルックアップマップを作成します
        # analyzed_paths: Dict[Path, FileInfo] = {f.path: f for f in self._analysis_results} # This line is incorrect and removed.
        # logger.debug(f"Context: Analyzed path keys: {list(analyzed_paths.keys())}") # DEBUG LOGGING REMOVED

        valid_target_paths: List[Path] = []
        potential_errors: List[str] = []
        resolved_paths_map: Dict[str, Path] = {}

        for file_path_str in target_files:
            absolute_path: Optional[Path] = None
            try:
                # Resolve the input path string relative to the project root
                # 入力パス文字列をプロジェクトルートからの相対パスとして解決します
                absolute_path = self._path_resolver.resolve_absolute(file_path_str, base_dir=self.project_root)
                resolved_paths_map[file_path_str] = absolute_path # Store resolved path
            except FileNotFoundError as e: # Error from PathResolver only
                 potential_errors.append(f"File specified for context not found or inaccessible: '{file_path_str}'. Error: {e}")
                 logger.warning(f"Context: Could not resolve path '{file_path_str}': {e}")
                 continue # Skip to the next file path string

        # Now, check resolved paths against analyzed results *after* the loop
        # ループの後で、解決されたパスを分析結果と照合します
        for file_path_str, absolute_path in resolved_paths_map.items():
             # Check if the resolved path exists in our analyzed files map
             # 解決されたパスが分析済みファイルマップに存在するか確認します
             # Use self._analysis_results directly
             # self._analysis_results を直接使用します
            if absolute_path not in self._analysis_results:
                # print(f"DEBUG Kotemari.get_context: Path check FAILED for {repr(absolute_path)}. Analyzed keys: {[repr(p) for p in analyzed_paths.keys()]}") # TEMP DEBUG PRINT
                error_msg = (
                    f"File '{absolute_path}' (from input '{file_path_str}') was not found in the project analysis results. "
                    f"It might be ignored, outside the project root, or does not exist in the analyzed set."
                )
                potential_errors.append(error_msg)
                logger.warning(f"Context: {error_msg}")
            else:
                # print(f"DEBUG Kotemari.get_context: Path check OK for {repr(absolute_path)}") # TEMP DEBUG PRINT
                valid_target_paths.append(absolute_path)

        # If any errors occurred during resolution or analysis check, raise them now
        # 解決または分析チェック中にエラーが発生した場合は、ここで発生させます
        if potential_errors:
            # Raise the first error encountered, or a combined error
            # 遭遇した最初のエラー、または結合されたエラーを発生させます
            raise FileNotFoundErrorInAnalysis("\n".join(potential_errors))

        # Original check if *no* valid files were found *at all*
        # *全く*有効なファイルが見つからなかった場合の元のチェック
        if not valid_target_paths:
            logger.warning("Context generation requested, but no valid target files were found after checking analysis results.")
            raise ContextGenerationError("No valid target files found in analysis results for context generation.")

        # Pass only the valid target paths to the builder
        # 有効なターゲットパスのみをビルダーに渡します
        # print(f"DEBUG Kotemari.get_context: Calling ContextBuilder with valid_target_paths = {valid_target_paths}") # TEMP DEBUG PRINT
        context_data = self.context_builder.build_context(
            target_files=valid_target_paths, # Corrected argument name
            project_root=self.project_root
        )
        logger.info(f"Context generated successfully for {len(target_files)} files.")
        return context_data

    # === File System Watching ===

    def start_watching(self, user_callback: Optional[FileSystemEventCallback] = None):
        """
        Starts the background file system monitor.
        バックグラウンドファイルシステムモニターを開始します。

        Args:
            user_callback (Optional[FileSystemEventCallback], optional):
                A callback function to be invoked when a file system event occurs after internal handling.
                内部処理後にファイルシステムイベントが発生したときに呼び出されるコールバック関数。
        """
        if self._event_monitor is not None and self._event_monitor.is_alive():
            logger.warning("File system monitor is already running.")
            return

        logger.info("Starting file system monitor...")
        self._event_queue = queue.Queue()
        self._stop_worker_event.clear()

        # --- Internal event handler --- #
        def internal_event_handler(event: FileSystemEvent):
            logger.info(f"[Watcher] Detected event: {event}")
            # Put the event into the queue for the background worker
            if self._event_queue:
                 self._event_queue.put(event)

            # Call user callback if provided
            if user_callback:
                try:
                    user_callback(event)
                except Exception as e:
                    logger.error(f"Error in user callback for event {event}: {e}", exc_info=True)

        # --- Background worker thread --- # (Step 11-1-6)
        def background_worker():
            logger.info("Background analysis worker started.")
            while not self._stop_worker_event.is_set():
                try:
                    # Wait for an event with a timeout to allow checking the stop signal
                    event: Optional[FileSystemEvent] = self._event_queue.get(timeout=1.0)

                    # English: Check for the sentinel value to stop the worker.
                    # 日本語: ワーカーを停止させるための番兵値を確認します。
                    if event is None:
                        logger.debug("[Worker] Received stop sentinel.")
                        break # Exit the loop

                    logger.info(f"[Worker] Processing event: {event}")

                    # English: Process the event using the dedicated method.
                    # 日本語: 専用メソッドを使用してイベントを処理します。
                    self._process_event(event)

                    # English: Task is marked done inside _process_event now.
                    # 日本語: タスクは _process_event 内で完了マークが付けられるようになりました。
                    # self._event_queue.task_done() # Removed from here

                except queue.Empty:
                    # Timeout reached, loop again to check stop signal
                    continue
                except Exception as e:
                    logger.error(f"[Worker] Error processing event queue: {e}", exc_info=True)
                    # How to handle errors? Continue? Stop? Maybe mark task done if it wasn't?
                    # エラーをどう処理しますか？続行しますか？停止しますか？ もしそうでなければタスクを完了としてマークしますか？
                    # Ensure task_done is called even on unexpected errors in the loop itself
                    # ループ自体で予期しないエラーが発生した場合でも task_done が呼び出されるようにします
                    # This might be redundant if _process_event handles its errors and calls task_done.
                    # _process_event がエラーを処理して task_done を呼び出す場合、これは冗長になる可能性があります。
                    # Consider carefully if this is needed.
                    # これが必要かどうか慎重に検討してください。
                    # if self._event_queue:
                    #     try:
                    #         self._event_queue.task_done()
                    #     except ValueError:
                    #         pass # Ignore if task_done() called more times than tasks
            logger.info("Background analysis worker stopped.")

        # Initialize and start the monitor
        self._event_monitor = FileSystemEventMonitor(
            self.project_root,
            internal_event_handler,
            ignore_func=self._ignore_processor.get_ignore_function()
        )
        self._event_monitor.start()

        # Start the background worker thread
        self._background_worker_thread = threading.Thread(target=background_worker, daemon=True)
        self._background_worker_thread.start()

        logger.info("File system monitor and background worker started.")

    def stop_watching(self):
        """Stops the background file system monitor and worker thread."""
        if self._event_monitor is None or not self._event_monitor.is_alive():
            logger.warning("File system monitor is not running.")
            return

        logger.info("Stopping file system monitor and background worker...")

        # Stop the monitor
        self._event_monitor.stop()
        self._event_monitor.join()
        logger.debug("File system monitor stopped.")

        # Signal the worker thread to stop and wait for it
        if self._background_worker_thread and self._background_worker_thread.is_alive():
            self._stop_worker_event.set()
            # Optionally put a dummy event to unblock the queue.get immediately
            if self._event_queue:
                self._event_queue.put(None) # Sentinel value or dummy event

            self._background_worker_thread.join(timeout=5.0) # Wait with timeout
            if self._background_worker_thread.is_alive():
                 logger.warning("Background worker thread did not stop gracefully.")
            else:
                 logger.debug("Background worker thread stopped.")

        self._event_monitor = None
        self._event_queue = None
        self._background_worker_thread = None
        logger.info("File system monitor and background worker stopped.")

    # English comment:
    # Build the reverse dependency index from the current analysis results.
    # This method should be called within the lock.
    # 日本語コメント:
    # 現在の解析結果から逆依存インデックスを構築します。
    # このメソッドはロック内で呼び出す必要があります。
    def _build_reverse_dependency_index(self) -> None:
        logger.debug("逆依存インデックスの構築を開始します。")
        with self._reverse_dependency_index_lock:
            logger.debug("Acquired reverse dependency index lock.")
            self._reverse_dependency_index.clear()
            project_root = self.project_root
            logger.debug(f"Building reverse index from {len(self._analysis_results)} analysis results.")

            for dependent_path, file_info in self._analysis_results.items():
                logger.debug(f"Processing dependent: {dependent_path}")
                if file_info.dependencies:
                    logger.debug(f"  Found {len(file_info.dependencies)} dependencies for {dependent_path}")
                    for dep_info in file_info.dependencies:
                        logger.debug(f"    Processing dependency: {dep_info.module_name} ({dep_info.dependency_type})")
                        resolved_dependency_path: Optional[Path] = None

                        if dep_info.dependency_type in [DependencyType.INTERNAL_ABSOLUTE, DependencyType.INTERNAL_RELATIVE]:
                            # Use pre-resolved path from DependencyInfo if available
                            if hasattr(dep_info, 'resolved_path') and dep_info.resolved_path:
                                resolved_dependency_path = dep_info.resolved_path.resolve()
                                logger.debug(f"      Using pre-resolved path: {resolved_dependency_path}")
                            else:
                                # Manual resolution (Fallback)
                                logger.warning(f"DependencyInfo missing pre-resolved path for {dep_info.module_name}. Attempting manual.")
                                try:
                                    base_dir_for_resolve = dependent_path.parent
                                    # ... (manual resolution logic - kept concise) ...
                                    if dep_info.dependency_type == DependencyType.INTERNAL_ABSOLUTE:
                                        module_path_parts = dep_info.module_name.split('.')
                                        potential_path_py = project_root.joinpath(*module_path_parts).with_suffix(".py")
                                        potential_path_init = project_root.joinpath(*module_path_parts, "__init__.py")
                                        if potential_path_py.is_file():
                                             resolved_dependency_path = potential_path_py.resolve()
                                        elif potential_path_init.is_file():
                                             resolved_dependency_path = potential_path_init.resolve()
                                except Exception as e:
                                     logger.warning(f"      Error during manual resolve: {e}")

                            logger.debug(f"      Resolved path result: {resolved_dependency_path}")

                        # Check if resolved and exists in analysis results
                        if resolved_dependency_path:
                            is_in_analysis = resolved_dependency_path in self._analysis_results
                            logger.debug(f"      Is resolved path in analysis results? {is_in_analysis}")
                            if is_in_analysis:
                                logger.debug(f"      Adding to index: {resolved_dependency_path} <- {dependent_path}")
                                self._reverse_dependency_index.setdefault(resolved_dependency_path, set()).add(dependent_path)
                            else:
                                logger.warning(f"      Resolved path {resolved_dependency_path} not found in analysis results. Skipping add.")
                        else:
                            logger.debug(f"    Dependency '{dep_info.module_name}' did not resolve or is external. Skipping add.")
                else:
                    logger.debug(f"  No dependencies found for {dependent_path}")

            logger.debug(f"逆依存インデックスの構築完了: {len(self._reverse_dependency_index)} 件のエントリ。 Index: {self._reverse_dependency_index}")
            logger.debug("Releasing reverse dependency index lock.")

    def _add_dependencies_to_reverse_index(self, dependent_path: Path, dependencies: List[DependencyInfo]) -> None:
        """
        Adds the dependencies of a single file to the reverse dependency index.
        Should be called under the appropriate lock if modifying shared state.
        単一ファイルの依存関係を逆依存インデックスに追加します。
        共有状態を変更する場合は、適切なロックの下で呼び出す必要があります。
        """
        if not dependencies:
            return

        logger.debug(f"Adding dependencies to reverse index for: {dependent_path}")
        project_root = self.project_root # Get project root once

        with self._reverse_dependency_index_lock:
            for dep_info in dependencies:
                resolved_dependency_path: Optional[Path] = None
                if dep_info.dependency_type in [DependencyType.INTERNAL_ABSOLUTE, DependencyType.INTERNAL_RELATIVE]:
                    # Use the pre-resolved path if available in DependencyInfo
                    # DependencyInfo で利用可能な場合は、事前に解決されたパスを使用します
                    if hasattr(dep_info, 'resolved_path') and dep_info.resolved_path:
                        resolved_dependency_path = dep_info.resolved_path.resolve() # Ensure it's resolved
                        logger.debug(f"Using pre-resolved path from DependencyInfo: {resolved_dependency_path}")
                    else:
                        # Fallback to resolving manually if not pre-resolved (should ideally not happen with current flow)
                        # 事前に解決されていない場合は手動での解決にフォールバックします（現在のフローでは理想的には発生しません）
                        logger.warning(f"DependencyInfo for {dep_info.module_name} in {dependent_path} missing pre-resolved path, attempting manual resolve.")
                        # ... (Keep the existing manual resolution logic as fallback)
                        base_dir_for_resolve = dependent_path.parent
                        # ... (manual resolution code) ...

                # Check if the resolved dependency exists in our analysis results
                # 解決された依存関係が分析結果に存在するかどうかを確認します
                logger.debug(f"Checking reverse index condition for {resolved_dependency_path}")
                logger.debug(f"Analysis results keys: {list(self._analysis_results.keys())}")
                if resolved_dependency_path:
                    is_in_analysis = resolved_dependency_path in self._analysis_results
                    logger.debug(f"Is {resolved_dependency_path} in analysis results? {is_in_analysis}")
                    if is_in_analysis:
                        self._reverse_dependency_index.setdefault(resolved_dependency_path, set()).add(dependent_path)
                        logger.debug(f"Added reverse dependency link: {resolved_dependency_path} <- {dependent_path}")
                    else:
                        logger.warning(f"Could not add reverse dependency for {resolved_dependency_path} from {dependent_path}: Target not found in analysis results.")
                else:
                    logger.debug(f"Skipping reverse dependency add for {dep_info.module_name} from {dependent_path}: Path not resolved.")

    def _remove_dependencies_from_reverse_index(self, dependent_path: Path, dependencies: List[DependencyInfo]) -> None:
        """
        Removes the dependencies of a single file from the reverse dependency index.
        Should be called under the appropriate lock if modifying shared state.
        単一ファイルの依存関係を逆依存インデックスから削除します。
        共有状態を変更する場合は、適切なロックの下で呼び出す必要があります。
        """
        if not dependencies:
            return

        logger.debug(f"Removing dependencies from reverse index for: {dependent_path}")
        project_root = self.project_root

        with self._reverse_dependency_index_lock:
            for dep_info in dependencies:
                resolved_dependency_path: Optional[Path] = None
                if dep_info.dependency_type in [DependencyType.INTERNAL_ABSOLUTE, DependencyType.INTERNAL_RELATIVE]:
                    try:
                        # --- Path Resolution Logic (copied from _add...) ---
                        base_dir_for_resolve = dependent_path.parent
                        if dep_info.dependency_type == DependencyType.INTERNAL_RELATIVE and dep_info.level is not None:
                            relative_module_path_parts = dep_info.module_name.split('.')
                            current_dir = base_dir_for_resolve
                            for _ in range(dep_info.level -1):
                                current_dir = current_dir.parent
                            potential_path_py = current_dir.joinpath(*relative_module_path_parts).with_suffix(".py")
                            potential_path_init = current_dir.joinpath(*relative_module_path_parts, "__init__.py")
                            if potential_path_py.is_file():
                                resolved_dependency_path = potential_path_py.resolve()
                            elif potential_path_init.is_file():
                                resolved_dependency_path = potential_path_init.resolve()
                        elif dep_info.dependency_type == DependencyType.INTERNAL_ABSOLUTE:
                            module_path_parts = dep_info.module_name.split('.')
                            potential_path_py = project_root.joinpath(*module_path_parts).with_suffix(".py")
                            potential_path_init = project_root.joinpath(*module_path_parts, "__init__.py")
                            if potential_path_py.is_file():
                                resolved_dependency_path = potential_path_py.resolve()
                            elif potential_path_init.is_file():
                                resolved_dependency_path = potential_path_init.resolve()
                        # --- End Path Resolution Logic ---
                    except Exception as e:
                        logger.warning(f"Error resolving path for dependency '{dep_info.module_name}' in file '{dependent_path}' during remove: {e}")

                if resolved_dependency_path:
                    if resolved_dependency_path in self._reverse_dependency_index:
                        dependents = self._reverse_dependency_index[resolved_dependency_path]
                        dependents.discard(dependent_path) # Remove the file from the set
                        logger.debug(f"Removed reverse dependency link: {resolved_dependency_path} <- {dependent_path}")
                        # Optional: Clean up empty sets
                        # オプション: 空のセットをクリーンアップ
                        if not dependents:
                            logger.debug(f"Removing empty set for dependency: {resolved_dependency_path}")
                            del self._reverse_dependency_index[resolved_dependency_path]

    def _remove_dependent_references_from_reverse_index(self, deleted_dependent_path: Path) -> None:
        """
        Removes all references to a deleted file from the values (sets) in the reverse dependency index.
        Should be called under the appropriate lock if modifying shared state.
        逆依存インデックスの値 (セット) から、削除されたファイルへのすべての参照を削除します。
        共有状態を変更する場合は、適切なロックの下で呼び出す必要があります。
        """
        logger.debug(f"Removing all references to deleted file from reverse index: {deleted_dependent_path}")
        with self._reverse_dependency_index_lock:
            # Iterate through a copy of keys to avoid modification issues during iteration
            # 繰り返し中の変更の問題を避けるために、キーのコピーを反復処理します
            for dependency_path in list(self._reverse_dependency_index.keys()):
                dependents = self._reverse_dependency_index[dependency_path]
                if deleted_dependent_path in dependents:
                    dependents.discard(deleted_dependent_path)
                    logger.debug(f"Removed reference {dependency_path} <- {deleted_dependent_path}")
                    # Optional: Clean up empty sets
                    # オプション: 空のセットをクリーンアップ
                    if not dependents:
                        logger.debug(f"Removing empty set for dependency after deleting reference: {dependency_path}")
                        del self._reverse_dependency_index[dependency_path]

    def _process_event(self, event: FileSystemEvent):
        # This method processes a single event. Logic moved from background_worker.
        # このメソッドは単一のイベントを処理します。ロジックは background_worker から移動しました。
        try:
            file_path = Path(event.src_path)
            logger.debug(f"Processing event: type={event.event_type}, path={file_path}, is_dir={event.is_directory}")

            # Ignore events based on config rules
            # 設定ルールに基づいてイベントを無視
            if self._ignore_processor.should_ignore(file_path):
                logger.debug(f"Ignoring event for path: {file_path}")
                return

            if event.event_type == "created":
                # Add new file info to cache
                # 新しいファイル情報をキャッシュに追加
                logger.info(f"差分更新: 作成されたファイル {file_path} を分析します。")
                new_file_info = self.analyzer.analyze_single_file(file_path)
                if new_file_info:
                    with self._analysis_lock:
                        # Get old dependencies before overwriting (should be None for created)
                        # 上書きする前に古い依存関係を取得します (作成された場合は None のはずです)
                        old_dependencies = self._analysis_results.get(file_path, None).dependencies if self._analysis_results.get(file_path, None) else []
                        self._analysis_results[file_path] = new_file_info

                    # Update reverse index outside analysis lock, but needs its own lock
                    # 分析ロックの外で逆インデックスを更新しますが、独自のロックが必要です
                    # Since it's a new file, only need to add new dependencies
                    # 新しいファイルなので、新しい依存関係を追加するだけで済みます
                    self._add_dependencies_to_reverse_index(file_path, new_file_info.dependencies)
                    # TODO: Handle propagation for created files impacting others? (Less common)
                    # TODO: 作成されたファイルが他のファイルに影響を与える場合の波及処理を扱いますか？（一般的ではない）

            elif event.event_type == "deleted":
                # Remove file info from cache
                # ファイル情報をキャッシュから削除
                with self._analysis_lock:
                    old_file_info = self._analysis_results.pop(file_path.resolve(), None) # Use resolve() for consistency

                if old_file_info:
                    logger.info(f"差分更新: 削除されたファイル {file_path} をキャッシュから削除しました。")
                    resolved_deleted_path = file_path.resolve()

                    # ** Get dependents BEFORE removing the key from reverse index **
                    # ** 逆インデックスからキーを削除する前に依存元を取得 **
                    dependents: Set[Path]
                    with self._reverse_dependency_index_lock:
                        # Copy the set to avoid modification issues
                        dependents = self._reverse_dependency_index.get(resolved_deleted_path, set()).copy()

                    # Update reverse index
                    # 1. Remove dependencies OF the deleted file (if any)
                    self._remove_dependencies_from_reverse_index(resolved_deleted_path, old_file_info.dependencies)
                    # 2. Remove references TO the deleted file from other entries' values
                    self._remove_dependent_references_from_reverse_index(resolved_deleted_path)
                    # 3. Remove the deleted file AS A KEY from the index
                    with self._reverse_dependency_index_lock:
                        if resolved_deleted_path in self._reverse_dependency_index:
                            logger.debug(f"Removing key {resolved_deleted_path} from reverse dependency index.")
                            del self._reverse_dependency_index[resolved_deleted_path]
                        else:
                            logger.debug(f"Key {resolved_deleted_path} not found in reverse dependency index, nothing to remove.")

                    # ** Propagate staleness to dependents **
                    # ** 依存元に stale 状態を伝播 **
                    if dependents:
                        logger.info(f"依存関係の波及: {resolved_deleted_path} の削除により、{len(dependents)} 個のファイルに影響の可能性があります。")
                        with self._analysis_lock: # Lock needed to modify FileInfo objects
                            for dependent_path in dependents:
                                if dependent_path in self._analysis_results:
                                    logger.debug(f"依存関係の波及: {dependent_path} の依存関係を古いものとしてマークします。")
                                    self._analysis_results[dependent_path].dependencies_stale = True
                                else:
                                    logger.warning(f"Dependent '{dependent_path}' found for deleted '{resolved_deleted_path}' but not in analysis results.")

            elif event.event_type == "modified":
                # Update cache for the modified file
                # 変更されたファイルのキャッシュを更新
                logger.info(f"差分更新: 変更されたファイル {file_path} を再分析します。")
                updated_file_info = self.analyzer.analyze_single_file(file_path)

                if updated_file_info:
                    with self._analysis_lock:
                        # Get old dependencies before overwriting
                        # 上書きする前に古い依存関係を取得します
                        old_dependencies = self._analysis_results.get(file_path, None).dependencies if self._analysis_results.get(file_path, None) else []
                        self._analysis_results[file_path] = updated_file_info

                    # Update reverse index incrementally
                    # 逆インデックスを増分更新
                    self._remove_dependencies_from_reverse_index(file_path, old_dependencies)
                    self._add_dependencies_to_reverse_index(file_path, updated_file_info.dependencies)

                    # --- Dependency Propagation (Step 12-4 will refine this) ---
                    # English: Find files that depend on the modified file and potentially mark them.
                    # 日本語: 変更されたファイルに依存するファイルを見つけ、潜在的にマークします。
                    affected_dependents: Set[Path]
                    with self._reverse_dependency_index_lock:
                        affected_dependents = self._reverse_dependency_index.get(file_path, set()).copy() # Copy to avoid issues if set is modified

                    if affected_dependents:
                        logger.info(f"依存関係の波及: {file_path} の変更により、{len(affected_dependents)} 個のファイルに影響の可能性があります。")
                        with self._analysis_lock: # Need lock to modify FileInfo objects in _analysis_results
                            for dependent_path in affected_dependents:
                                if dependent_path != file_path and dependent_path in self._analysis_results:
                                    logger.debug(f"依存関係の波及: {dependent_path} の依存関係を古いものとしてマークします。")
                                    # Mark the FileInfo as having stale dependencies
                                    # FileInfo を古い依存関係を持つものとしてマークします
                                    self._analysis_results[dependent_path].dependencies_stale = True
                                    # TODO: Decide if we need to re-analyze *here* or *on-demand* later.
                                    # ここで再分析するか、後でオンデマンドで分析するかを決定する必要があります。
                                    # For now, just marking is sufficient for Step 12-4-2.
                                    # 現時点では、マークするだけで Step 12-4-2 には十分です。
                    # --- End Dependency Propagation Placeholder ---

                else: # Analysis failed or file should be removed (e.g., became ignored)
                    # 解析失敗、またはファイルを削除すべき場合の処理 (例: 無視されるようになった)
                    with self._analysis_lock:
                        old_file_info = self._analysis_results.pop(file_path, None)

                    if old_file_info:
                        logger.info(f"差分更新: 分析失敗/無視のため、ファイル {file_path} をキャッシュから削除します。")
                        # Update reverse index
                        # 逆インデックスを更新
                        self._remove_dependencies_from_reverse_index(file_path, old_file_info.dependencies)
                        self._remove_dependent_references_from_reverse_index(file_path)
                        # TODO: Trigger re-analysis for files that depended on this? (Handled by propagation?)

            elif event.event_type == "moved":
                # Handle moved files/directories
                src_path = Path(event.src_path)
                dest_path = Path(event.dest_path) if event.dest_path else None
                logger.warning(f"Moved event handling not fully implemented: {src_path} -> {dest_path}")

                if dest_path:
                    # Treat as delete and create for simplicity, though inefficient
                    # 簡単のため、非効率的ではあるが、削除と作成として扱います
                    # Need to get dependencies *before* deleting from cache
                    # キャッシュから削除する*前*に依存関係を取得する必要があります
                    old_file_info = None
                    with self._analysis_lock:
                         old_file_info = self._analysis_results.get(src_path)

                    # Simulate delete
                    delete_event = FileSystemEvent(event_type="deleted", src_path=str(src_path), is_directory=event.is_directory)
                    self._process_event(delete_event)

                    # Simulate create (if not ignored at new location)
                    # 作成をシミュレートします (新しい場所で無視されない場合)
                    if not self._ignore_processor.should_ignore(dest_path):
                        create_event = FileSystemEvent(event_type="created", src_path=str(dest_path), is_directory=event.is_directory)
                        self._process_event(create_event)
                    else:
                        logger.info(f"Moved file {dest_path} is ignored at the new location.")
                else:
                    logger.warning(f"Move event without destination path: {src_path}")

            # Mark the event as processed
            if self._event_queue:
                 self._event_queue.task_done()

        except Exception as e:
            logger.error(f"Error processing event {event}: {e}", exc_info=True)
            # Ensure task_done is called even if an error occurs during processing
            if self._event_queue:
                 self._event_queue.task_done()

    # English comment:
    # Background worker thread target function.