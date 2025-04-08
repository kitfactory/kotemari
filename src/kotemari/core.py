from pathlib import Path
from typing import List, Optional, Callable, Union, Dict
import logging
import datetime
import hashlib
import importlib.metadata
import threading
import queue

from .domain.file_info import FileInfo
from .domain.file_system_event import FileSystemEvent
from .domain.dependency_info import DependencyInfo
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
        self._project_root: Path = self._path_resolver.resolve_absolute(project_root)
        self._config_path: Optional[Path] = None
        if config_path:
            self._config_path = self._path_resolver.resolve_absolute(config_path, base_dir=self._project_root)

        self._config_manager = ConfigManager(self._path_resolver, self._project_root)
        self._config = self._config_manager.get_config()

        # --- Service and Gateway Instances ---
        self._file_accessor = FileSystemAccessor(self._path_resolver)
        self._gitignore_reader = GitignoreReader(self._project_root)
        self._ignore_processor = IgnoreRuleProcessor(self.project_root, self._config, self._path_resolver)
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
        self._analysis_results: Optional[List[FileInfo]] = None
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

        self.cache_file_path = Path(".kotemari") / "analysis_cache.pkl"

        # --- Try loading from cache first (Step 11-1-7) ---
        logger.info("Attempting to load analysis results from cache...")
        cached_data = self._file_accessor.read_pickle(self.cache_file_path, self.project_root)
        if cached_data is not None and isinstance(cached_data, list): # Basic validation
             # TODO: Add more robust cache validation (e.g., based on config changes, schema version)
             logger.info(f"Successfully loaded {len(cached_data)} items from cache: {self.project_root / self.cache_file_path}")
             with self._analysis_lock:
                 self._analysis_results = cached_data
                 self.project_analyzed = True
        else:
             logger.info("Cache not found or invalid. Performing initial project analysis...")
             # --- Perform initial analysis (Step 11-1-2 cont.) ---
             self._run_analysis_and_update_memory() # Perform initial full analysis

    @property
    def project_root(self) -> Path:
        """
        Returns the absolute path to the project root directory.
        プロジェクトルートディレクトリへの絶対パスを返します。
        """
        return self._project_root

    def _run_analysis_and_update_memory(self):
        """Runs the analysis and updates the in-memory cache atomically."""
        logger.debug("Acquiring analysis lock for full analysis...")
        with self._analysis_lock:
            logger.info("Running full project analysis...")
            try:
                self._analysis_results = self.analyzer.analyze()
                self.project_analyzed = True
                logger.info(f"Initial analysis complete. Found {len(self._analysis_results)} files.")
                # --- Save results to cache (Step 11-1-7) ---
                if self._analysis_results is not None:
                    try:
                        self._file_accessor.write_pickle(self._analysis_results, self.cache_file_path, self.project_root)
                        logger.info(f"Analysis results saved to cache: {self.project_root / self.cache_file_path}")
                    except IOError as e:
                        logger.warning(f"Failed to save analysis results to cache: {e}")
            except Exception as e:
                logger.error(f"Initial project analysis failed: {e}", exc_info=True)
                self._analysis_results = None # Ensure cache is cleared on error
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
            return self._analysis_results # Return reference to in-memory list

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
        analyzed_paths: Dict[Path, FileInfo] = {f.path: f for f in self._analysis_results}
        # logger.debug(f\"Context: Analyzed path keys: {list(analyzed_paths.keys())}\") # DEBUG LOGGING REMOVED

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
            if absolute_path not in analyzed_paths:
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
                event: Optional[FileSystemEvent] = None # Initialize event
                try:
                    # Wait for an event with a timeout to allow checking the stop signal
                    # タイムアウト付きでイベントを待機し、停止シグナルを確認できるようにします
                    event = self._event_queue.get(timeout=1.0)

                    if event is None: # Sentinel value to stop the worker
                        logger.debug("[Worker] Received stop signal (sentinel).")
                        break

                    logger.info(f"[Worker] Processing event: {event}")

                    # Resolve path and check if ignored BEFORE checking event type
                    # イベントタイプを確認する前にパスを解決し、無視されるかどうかを確認します
                    absolute_path = Path(event.src_path).resolve()
                    if self._ignore_processor.is_ignored(absolute_path):
                        logger.debug(f"[Worker] Ignoring event for path: {absolute_path}")
                        self._event_queue.task_done()
                        continue # Skip ignored paths

                    # --- Differential Update Logic (Step 11-2-1) ---
                    event_processed_differentially = False
                    if not event.is_directory: # Only process file events differentially for now
                        # Ensure thread-safe access to analysis results
                        # 分析結果へのスレッドセーフなアクセスを保証します
                        with self._analysis_lock:
                            if event.event_type == EVENT_TYPE_CREATED:
                                try:
                                    logger.info(f"[Worker] Analyzing created file: {absolute_path}")
                                    # Analyze the single created file
                                    # 作成された単一ファイルを分析します
                                    new_file_info_list = self.analyzer.analyze([absolute_path]) # Analyze only the new file
                                    if new_file_info_list:
                                        new_file_info = new_file_info_list[0]
                                        # Update the in-memory cache
                                        # メモリ内キャッシュを更新します
                                        # Remove existing entry if any (e.g., if created shortly after deletion)
                                        # 既存のエントリがあれば削除します（例：削除直後に作成された場合）
                                        self._analysis_results = [fi for fi in self._analysis_results if fi.path != absolute_path]
                                        self._analysis_results.append(new_file_info)
                                        logger.info(f"[Worker] Added/Updated analysis for {absolute_path} in memory cache.")
                                        self.project_analyzed = True # Mark as analyzed if not already
                                    else:
                                         logger.warning(f"[Worker] Analysis of created file {absolute_path} returned no info (possibly empty or fully ignored content).")
                                    event_processed_differentially = True
                                except Exception as e:
                                    logger.error(f"[Worker] Error analyzing created file {absolute_path}: {e}", exc_info=True)
                                    # Fallback handled below

                            elif event.event_type == EVENT_TYPE_DELETED:
                                logger.info(f"[Worker] Removing deleted file from cache: {absolute_path}")
                                initial_count = len(self._analysis_results)
                                # Remove the FileInfo corresponding to the deleted file path
                                # 削除されたファイルパスに対応する FileInfo を削除します
                                self._analysis_results = [fi for fi in self._analysis_results if fi.path != absolute_path]
                                final_count = len(self._analysis_results)
                                if final_count < initial_count:
                                    logger.info(f"[Worker] Removed analysis for {absolute_path} from memory cache.")
                                else:
                                    logger.warning(f"[Worker] Deleted file {absolute_path} was not found in memory cache.")
                                event_processed_differentially = True
                                # No need to trigger full analysis if file wasn't tracked
                                # ファイルが追跡されていなかった場合、完全な分析をトリガーする必要はありません

                            elif event.event_type == EVENT_TYPE_MODIFIED: # (Step 11-2-2)
                                try:
                                    logger.info(f"[Worker] Re-analyzing modified file: {absolute_path}")
                                    # Re-analyze the single modified file
                                    # 変更された単一ファイルを再分析します
                                    modified_file_info_list = self.analyzer.analyze([absolute_path])
                                    if modified_file_info_list:
                                        modified_file_info = modified_file_info_list[0]
                                        # Update the in-memory cache by replacing the old entry
                                        # 古いエントリを置き換えてメモリ内キャッシュを更新します
                                        self._analysis_results = [fi for fi in self._analysis_results if fi.path != absolute_path]
                                        self._analysis_results.append(modified_file_info)
                                        logger.info(f"[Worker] Updated analysis for {absolute_path} in memory cache.")
                                    else:
                                        # If analysis returns nothing (e.g., file became empty or fully ignored), remove it
                                        # 分析が何も返さない場合（例：ファイルが空になったか完全に無視されるようになった）、削除します
                                        logger.warning(f"[Worker] Re-analysis of {absolute_path} returned no info. Removing from cache.")
                                        self._analysis_results = [fi for fi in self._analysis_results if fi.path != absolute_path]
                                    event_processed_differentially = True
                                except Exception as e:
                                     logger.error(f"[Worker] Error re-analyzing modified file {absolute_path}: {e}", exc_info=True)
                                     # Fallback handled below

                    # --- Fallback to Full Re-analysis ---
                    # If the event wasn't handled differentially (e.g., MOVED, directory event, or error during diff update)
                    # イベントが差分的に処理されなかった場合（例：移動、ディレクトリイベント、差分更新中のエラー）
                    if not event_processed_differentially:
                        # Log the specific event type that triggers the fallback
                        # フォールバックをトリガーする特定のイベントタイプをログに記録します
                        trigger_reason = f"event type '{event.event_type}'" if hasattr(event, 'event_type') else "unknown event or error"
                        if event and event.is_directory:
                            trigger_reason += " (directory event)"
                        elif not event_processed_differentially:
                            trigger_reason += " (error during differential update or unhandled file event)"

                        logger.info(f"[Worker] {trigger_reason.capitalize()} triggers full re-analysis.")
                        self._run_analysis_and_update_memory() # This handles locking internally
                        logger.info("[Worker] Background full re-analysis complete.")
                    # ---------------------------------------------------- #

                    self._event_queue.task_done()
                except queue.Empty:
                    # Timeout reached, loop again to check stop signal
                    # タイムアウトに達しました。再度ループして停止シグナルを確認します
                    continue
                except Exception as e:
                    # Catch potential errors resolving path or other unexpected issues
                    # パス解決中の潜在的なエラーやその他の予期しない問題をキャッチします
                    event_path = event.src_path if event else "N/A"
                    logger.error(f"[Worker] Error processing event for path '{event_path}': {e}", exc_info=True)
                    # Avoid getting stuck in a loop; mark task as done if possible
                    # ループに陥るのを避けます。可能であればタスクを完了としてマークします
                    try:
                        if self._event_queue and not self._event_queue.empty(): # Check if queue exists and is not empty
                             self._event_queue.task_done()
                    except Exception as qe:
                         logger.error(f"[Worker] Error marking task done after outer exception: {qe}")
            logger.info("Background analysis worker stopped.")
        # --- End of background worker thread --- # (Make sure this marker helps identify the end)

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