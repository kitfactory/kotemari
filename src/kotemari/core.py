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
            log_level (Union[int, str], optional): The logging level for the Kotemari instance.
                                                  Defaults to logging.INFO.
                                                  ログレベル。
                                                  デフォルトは logging.INFO。
        """
        # --- Core Components Initialization ---
        self._path_resolver = PathResolver()
        # Use a private variable for storing the resolved project root
        # 解決済みのプロジェクトルートを格納するためにプライベート変数を使用
        self._project_root: Path = project_root.resolve()

        # Debug print to stderr
        print(f"Kotemari.__init__: Initializing for {self._project_root}", file=sys.stderr)

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
        print(f"Kotemari.analyze_project: Starting analysis for {self._project_root}", file=sys.stderr)

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
        self._reverse_dependency_index.clear()
        # English: Get the project root path once.
        # 日本語: プロジェクトルートパスを一度取得します。
        project_root = self.project_root

        # English: Iterate through the analysis results dictionary (path: FileInfo).
        # 日本語: 分析結果の辞書 (path: FileInfo) を反復処理します。
        for dependent_path, file_info in self._analysis_results.items():
            if file_info.dependencies:
                for dep_info in file_info.dependencies:
                    resolved_dependency_path: Optional[Path] = None
                    # English: Process only internal dependencies for the reverse index.
                    # 日本語: 逆インデックスのために内部依存関係のみを処理します。
                    if dep_info.dependency_type in [DependencyType.INTERNAL_ABSOLUTE, DependencyType.INTERNAL_RELATIVE]:
                        try:
                            # English: Attempt to resolve the module name to an absolute path within the project.
                            # 日本語: モジュール名をプロジェクト内の絶対パスに解決しようと試みます。
                            # Note: This resolution might be complex depending on sys.path, __init__.py handling etc.
                            # PathResolver might need enhancement or this logic refined.
                            # 注意: この解決は sys.path、__init__.py の処理などによって複雑になる可能性があります。
                            # PathResolver の強化またはこのロジックの改良が必要になる場合があります。

                            # Use the directory of the *dependent* file as the base for relative imports
                            # *依存元*ファイルのディレクトリを相対インポートの基点として使用します
                            base_dir_for_resolve = dependent_path.parent

                            # For relative imports, use level and module name
                            # 相対インポートの場合、level とモジュール名を使用します
                            if dep_info.dependency_type == DependencyType.INTERNAL_RELATIVE and dep_info.level is not None:
                                # Simple relative path construction (may need refinement for packages)
                                # 単純な相対パス構築（パッケージの場合は改良が必要な場合があります）
                                relative_module_path_parts = dep_info.module_name.split('.')
                                current_dir = base_dir_for_resolve
                                for _ in range(dep_info.level -1): # Go up levels for '..'
                                    current_dir = current_dir.parent

                                potential_path_py = current_dir.joinpath(*relative_module_path_parts).with_suffix(".py")
                                potential_path_init = current_dir.joinpath(*relative_module_path_parts, "__init__.py")

                                if potential_path_py.exists() and potential_path_py.is_file():
                                     resolved_dependency_path = potential_path_py.resolve()
                                elif potential_path_init.exists() and potential_path_init.is_file():
                                    resolved_dependency_path = potential_path_init.resolve()
                                else:
                                     logger.debug(f"Relative import '{dep_info.module_name}' from '{dependent_path}' could not be resolved to an existing file ({potential_path_py} or {potential_path_init}).")


                            # For absolute imports, resolve relative to project root (or configured source roots)
                            # 絶対インポートの場合、プロジェクトルート（または設定されたソースルート）からの相対パスで解決します
                            elif dep_info.dependency_type == DependencyType.INTERNAL_ABSOLUTE:
                                # Assume absolute imports are relative to project root for now
                                # 現時点では、絶対インポートはプロジェクトルートからの相対パスであると仮定します
                                module_path_parts = dep_info.module_name.split('.')
                                potential_path_py = project_root.joinpath(*module_path_parts).with_suffix(".py")
                                potential_path_init = project_root.joinpath(*module_path_parts, "__init__.py")

                                if potential_path_py.exists() and potential_path_py.is_file():
                                     resolved_dependency_path = potential_path_py.resolve()
                                elif potential_path_init.exists() and potential_path_init.is_file():
                                     resolved_dependency_path = potential_path_init.resolve()
                                else:
                                     logger.debug(f"Absolute import '{dep_info.module_name}' could not be resolved within project root ({potential_path_py} or {potential_path_init}).")

                        except Exception as e:
                             logger.warning(f"Error resolving path for dependency '{dep_info.module_name}' in file '{dependent_path}': {e}", exc_info=True)


                    # English: If a path was successfully resolved, add it to the index.
                    # 日本語: パスが正常に解決された場合は、インデックスに追加します。
                    if resolved_dependency_path and resolved_dependency_path in self._analysis_results: # Ensure the resolved dependency is part of our analysis
                         if resolved_dependency_path not in self._reverse_dependency_index:
                            self._reverse_dependency_index[resolved_dependency_path] = set()
                         self._reverse_dependency_index[resolved_dependency_path].add(dependent_path)
                         logger.debug(f"Added reverse dependency: {resolved_dependency_path} <- {dependent_path}")

        logger.debug(f"逆依存インデックスの構築完了: {len(self._reverse_dependency_index)} 件のエントリ。")

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
                        self._analysis_results[file_path] = new_file_info
                        # Rebuild index as dependencies might change
                        # 依存関係が変わる可能性があるためインデックスを再構築
                        self._build_reverse_dependency_index()
                        # TODO: Handle propagation for created files impacting others?

            elif event.event_type == "deleted":
                # Remove file info from cache
                # ファイル情報をキャッシュから削除
                if file_path in self._analysis_results:
                    logger.info(f"差分更新: 削除されたファイル {file_path} をキャッシュから削除します。")
                    with self._analysis_lock:
                        del self._analysis_results[file_path]
                        # Rebuild index as dependencies might change
                        # 依存関係が変わる可能性があるためインデックスを再構築
                        self._build_reverse_dependency_index()
                        # TODO: Handle propagation for deleted dependencies?

            elif event.event_type == "modified":
                # Update cache for the modified file
                # 変更されたファイルのキャッシュを更新
                logger.info(f"差分更新: 変更されたファイル {file_path} を再分析します。")
                updated_file_info = self.analyzer.analyze_single_file(file_path)
                if updated_file_info:
                    with self._analysis_lock:
                        self._analysis_results[file_path] = updated_file_info
                        # English: Rebuild index if dependencies might have changed (safer approach).
                        # 日本語: 依存関係が変わった可能性があるのでインデックスを再構築（安全策）。
                        # TODO: Optimize index update instead of full rebuild.
                        self._build_reverse_dependency_index()

                        # --- Dependency Propagation (Step 12-3) ---
                        # English: Find files that depend on the modified file and mark them for re-analysis.
                        # 日本語: 変更されたファイルに依存するファイルを見つけ、再分析対象としてマークします。
                        affected_dependents = self._reverse_dependency_index.get(file_path, set())
                        if affected_dependents:
                            logger.info(f"依存関係の波及: {file_path} の変更により、{len(affected_dependents)} 個のファイル ({affected_dependents}) に影響があるため、再分析をスケジュールします。")
                            for dependent_path in affected_dependents:
                                # Avoid re-analyzing the file that just got updated
                                # 更新されたばかりのファイルを再分析しないようにする
                                if dependent_path != file_path:
                                    # Re-queue or mark for re-analysis. For simplicity, re-queue a modified event.
                                    # 再度キューに入れるか、再分析マークを付ける。簡単のため、modified イベントを再度キューに入れる。
                                    # Note: This could lead to redundant analysis if multiple dependencies change quickly.
                                    # 注意: 複数の依存関係が素早く変更されると冗長な分析につながる可能性がある。
                                    logger.debug(f"依存関係の波及: {dependent_path} を再分析キューに追加します。")
                                    propagated_event = FileSystemEvent(
                                        event_type="modified", # Treat propagation as a modification
                                        src_path=dependent_path,
                                        is_directory=False # Assuming dependency is always a file
                                    )
                                    self._event_queue.put(propagated_event)
                        # --- End Dependency Propagation ---

                else:
                    # Handle case where analysis failed or file should be removed
                    # 解析失敗、またはファイルを削除すべき場合の処理
                    if file_path in self._analysis_results:
                        logger.info(f"差分更新: 変更/削除されたファイル {file_path} をキャッシュから削除します。")
                        with self._analysis_lock:
                            del self._analysis_results[file_path]
                            # Rebuild index as dependencies might change
                            # 依存関係が変わる可能性があるためインデックスを再構築
                            self._build_reverse_dependency_index()
                            # TODO: Also handle propagation for deleted dependencies?

            elif event.event_type == "moved":
                # Handle moved files/directories
                # TODO: Implement logic for move events, including cache and index updates and propagation.
                src_path = Path(event.src_path)
                dest_path = Path(event.dest_path) if event.dest_path else None
                logger.warning(f"Moved event handling not fully implemented: {src_path} -> {dest_path}")
                # Need to remove old entry, add new entry, update index, and propagate

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