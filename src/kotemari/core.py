from pathlib import Path
from typing import List, Optional, Callable, Union
import logging
import datetime

from .domain.file_info import FileInfo
from .domain.file_system_event import FileSystemEvent
from .domain.dependency_info import DependencyInfo
from .utility.path_resolver import PathResolver
from .usecase.project_analyzer import ProjectAnalyzer
from .usecase.cache_updater import CacheUpdater
from .usecase.config_manager import ConfigManager
from .gateway.cache_storage import CacheStorage
from .gateway.gitignore_reader import GitignoreReader
from .service.ignore_rule_processor import IgnoreRuleProcessor
from .service.file_system_event_monitor import FileSystemEventMonitor, FileSystemEventCallback
from .usecase.context_builder import ContextBuilder
from .domain.project_config import ProjectConfig
from .domain.context_data import ContextData
from .gateway.file_system_accessor import FileSystemAccessor
from .domain.file_content_formatter import BasicFileContentFormatter
from .domain.cache_metadata import CacheMetadata
from .domain.exceptions import (
    KotemariError,
    AnalysisError,
    FileNotFoundErrorInAnalysis,
    ContextGenerationError,
    DependencyError
)

logger = logging.getLogger(__name__)

class Kotemari:
    """
    The main facade class for the Kotemari library.
    Provides methods to analyze projects, list files, and generate context.
    Kotemari ライブラリのメインファサードクラス。
    プロジェクトの分析、ファイル一覧表示、コンテキスト生成などのメソッドを提供します。
    """

    def __init__(
        self,
        project_root: Union[str, Path],
        config_path: Optional[Union[str, Path]] = None,
        use_cache: bool = True,
        log_level: Union[int, str] = logging.INFO
    ):
        """
        Initializes the Kotemari facade.
        Kotemari ファサードを初期化します。

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
            use_cache (bool, optional): Whether to use caching for analysis results.
                                        Defaults to True.
                                        分析結果にキャッシュを使用するかどうか。
                                        デフォルトは True。
            log_level (Union[int, str], optional): The logging level for the Kotemari instance.
                                                  Defaults to logging.INFO.
                                                  ログレベル。
                                                  デフォルトは logging.INFO。
        """
        self._path_resolver = PathResolver()
        # Initialize FileSystemAccessor and Formatter early
        # FileSystemAccessor と Formatter を早期に初期化します
        self._file_accessor = FileSystemAccessor(self._path_resolver)
        self._formatter = BasicFileContentFormatter()

        self._project_root: Path = self._path_resolver.resolve_absolute(project_root)
        self._config_path: Optional[Path] = None
        if config_path:
            self._config_path = self._path_resolver.resolve_absolute(config_path, base_dir=self._project_root)

        # Initialize components needed by multiple parts (Analyzer, Monitor)
        # 複数の部分（Analyzer、Monitor）で必要なコンポーネントを初期化します
        self._config_manager = ConfigManager(self._path_resolver, self._project_root)
        # GitignoreReader is not instantiated, its static methods are used directly.
        # GitignoreReader はインスタンス化されず、静的メソッドが直接使用されます。
        # self._gitignore_reader = GitignoreReader(self._project_root) # Remove instantiation

        # Pass necessary components to IgnoreRuleProcessor
        # 必要なコンポーネントを IgnoreRuleProcessor に渡します
        self._ignore_processor = IgnoreRuleProcessor(self.project_root, self._config_manager.get_config(), self._path_resolver)

        # Initialize Analyzer (now uses shared components)
        # Analyzer を初期化します（共有コンポーネントを使用）
        # Pass already created instances to avoid re-creation
        # 再作成を避けるために、既に作成されたインスタンスを渡します
        print("[DEBUG] Initializing self.analyzer...") # DEBUG ADD
        print(f"[DEBUG]   project_root={self._project_root}") # DEBUG ADD
        print(f"[DEBUG]   path_resolver={self._path_resolver}") # DEBUG ADD
        print(f"[DEBUG]   config_manager={self._config_manager}") # DEBUG ADD
        print(f"[DEBUG]   ignore_processor={self._ignore_processor}") # DEBUG ADD
        print(f"[DEBUG]   file_accessor={self._file_accessor}") # DEBUG ADD
        self.analyzer: ProjectAnalyzer = ProjectAnalyzer(
            project_root=self._project_root,
            path_resolver=self._path_resolver, # Pass resolver
            config_manager=self._config_manager, # Pass config manager
            ignore_processor=self._ignore_processor, # Pass ignore processor
            fs_accessor=self._file_accessor # CHANGED: Pass file accessor with correct name 'fs_accessor'
            # Let Analyzer create its own hash_calculator, language_detector if needed
            # 必要に応じて、Analyzer に独自の hash_calculator, language_detector を作成させます
        )
        print(f"[DEBUG] self.analyzer initialized: {self.analyzer}") # DEBUG ADD

        self._use_cache = use_cache
        self._cache_storage = CacheStorage(self._project_root) # Create storage directly
        self._cache_updater: Optional[CacheUpdater] = None
        self._analysis_results: Optional[List[FileInfo]] = None # Cache for analysis results
        self.project_analyzed: bool = False # Initialize analysis flag
        self._event_monitor: Optional[FileSystemEventMonitor] = None # Add this

        if self._use_cache:
            # Pass shared storage to updater
            # 共有ストレージをアップデーターに渡します
            self._cache_updater = CacheUpdater(self._project_root, self._cache_storage)
            logger.info("Cache enabled.")
        else:
            logger.info("Cache disabled.")

        logger.info(f"Kotemari initialized for project root: {self._project_root}")
        if self._config_path:
            logger.info(f"Using explicit config path: {self._config_path}")

        # English: Load cache if available, otherwise initialize empty state
        # 日本語: キャッシュが利用可能であればロードし、そうでなければ空の状態で初期化します
        # self._load_cache_or_initialize()

        # ----- REDUNDANT INITIALIZATION TO BE COMMENTED OUT START -----
        # English: Initialize UseCase instances
        # 日本語: ユースケースインスタンスを初期化します
        # Use internal attributes for initialization
        # 初期化には内部属性を使用します
        # Note: ProjectAnalyzer now uses the accessor directly from Kotemari
        # 注意: ProjectAnalyzer は Kotemari から直接アクセサを使用します
        # --- This block is redundant and incorrect, commenting out ---
        # self.analyzer = ProjectAnalyzer(
        #     project_root=self._project_root,
        #     cache_storage=self._cache_storage if self._use_cache else None, # INCORRECT: Analyzer doesn't take cache_storage
        #     config_manager=self._config_manager, # Pass config manager instead of raw config
        #     file_accessor=self._file_accessor, # Use internal accessor
        #     path_resolver=self._path_resolver, # Pass shared path resolver
        #     ignore_processor=self._ignore_processor # Pass shared ignore processor
        # )
        # ----- REDUNDANT INITIALIZATION COMMENTED OUT END -----

        print("[DEBUG] Initializing self.context_builder...") # DEBUG ADD
        print(f"[DEBUG]   file_accessor={self._file_accessor}") # DEBUG ADD
        print(f"[DEBUG]   formatter={self._formatter}") # DEBUG ADD
        self.context_builder = ContextBuilder(
            file_accessor=self._file_accessor, # Use internal accessor
            formatter=self._formatter # Use internal formatter instance
        )
        print(f"[DEBUG] self.context_builder initialized: {self.context_builder}") # DEBUG ADD
        # CacheUpdater is initialized in start_watching

    @property
    def project_root(self) -> Path:
        """
        Returns the absolute path to the project root directory.
        プロジェクトルートディレクトリへの絶対パスを返します。
        """
        return self._project_root

    def analyze_project(self, force_reanalyze: bool = False) -> list[FileInfo]:
        """
        Analyzes the project files, utilizing cache if enabled and valid.
        キャッシュが有効で有効な場合はキャッシュを利用して、プロジェクトファイルを分析します。

        Args:
            force_reanalyze: If True, ignores the cache and performs a full re-analysis.
                             Trueの場合、キャッシュを無視して完全な再分析を実行します。

        Returns:
            A list of FileInfo objects representing the analyzed files.
            分析されたファイルを表す FileInfo オブジェクトのリスト。
        """
        logger.info(f"Starting project analysis for: {self.project_root}")
        logger.debug(f"Cache enabled: {self._use_cache}, Force reanalyze: {force_reanalyze}")

        # Return in-memory cache if available and analysis already done and not forcing reanalyze
        # メモリ内キャッシュが利用可能で、分析が完了しており、再分析を強制しない場合はそれを返します
        if self.project_analyzed and self._analysis_results is not None and not force_reanalyze:
            logger.info("Returning in-memory cached analysis results.")
            return self._analysis_results

        # --- Cache Handling Logic (slightly adjusted) ---
        if self._use_cache and self._cache_updater and not force_reanalyze:
            logger.info("Cache enabled. Checking cache validity...")
            # Try to load from disk cache first
            cached_data = self._cache_storage.load_cache()
            if cached_data:
                analysis_results, metadata = cached_data
                # Validate cache (example: check config hash or file mtimes)
                # ここでキャッシュの妥当性検証ロジックを追加する（例：設定ハッシュやファイル更新時刻）
                # For now, assume loaded cache is valid if it exists
                logger.info(f"Valid cache found from disk. Returning {len(analysis_results)} cached results.")
                self._analysis_results = analysis_results
                self.project_analyzed = True # Mark as analyzed
                return self._analysis_results
            else:
                logger.info("No valid disk cache found. Performing analysis.")
        # --- End Cache Handling --- #

        # Perform analysis if no cache hit or cache disabled/forced
        # キャッシュヒットがない場合、またはキャッシュが無効/強制の場合に分析を実行します
        logger.info("Performing project analysis...")
        self._analysis_results = self.analyzer.analyze()
        self.project_analyzed = True # Mark as analyzed after analysis
        logger.info(f"Analysis complete. Found {len(self._analysis_results)} files.")

        # Update cache if enabled
        # 有効な場合はキャッシュを更新します
        if self._use_cache and self._cache_updater:
            logger.info("Updating cache with new analysis results...")
            # Let CacheUpdater handle metadata creation and saving
            # CacheUpdater にメタデータの作成と保存を処理させます
            self._cache_updater.update_cache(self._analysis_results) # Pass only analysis_results
            logger.info("Cache updated successfully.")

        return self._analysis_results

    def list_files(self, relative: bool = True) -> List[str]:
        """
        Lists the non-ignored files found in the project.
        プロジェクトで見つかった無視されていないファイルをリスト表示します。

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
            AnalysisError: If the project has not been analyzed yet.
                          プロジェクトがまだ分析されていない場合。
        """
        if self._analysis_results is None:
             # Optionally, call analyze_project automatically?
             # オプションで、analyze_project を自動的に呼び出しますか？
             # For now, require explicit analysis first.
             # 今のところ、最初に明示的な分析が必要です。
            # self.analyze_project()
             raise AnalysisError("Project must be analyzed before listing files. Call analyze_project() first.")
             # logger.warning("Project not analyzed yet. Call analyze_project() first for complete results.")
             # return []

        if not self._analysis_results:
            return []

        if relative:
            return [str(fi.path.relative_to(self.project_root).as_posix()) for fi in self._analysis_results]
        else:
            return [str(fi.path) for fi in self._analysis_results]

    def get_tree(self, max_depth: Optional[int] = None) -> str:
        """
        Generates a string representation of the project's file tree.
        プロジェクトのファイルツリーの文字列表現を生成します。

        Args:
            max_depth (Optional[int], optional): The maximum depth to display in the tree.
                                                Defaults to None (no limit).
                                                ツリーに表示する最大深度。
                                                デフォルトは None (制限なし)。

        Returns:
            str: The file tree string.
                 ファイルツリー文字列。

        Raises:
            AnalysisError: If the project has not been analyzed yet.
                          プロジェクトがまだ分析されていない場合。
        """
        if self._analysis_results is None:
            raise AnalysisError("Project must be analyzed before generating tree. Call analyze_project() first.")

        if not self._analysis_results:
            return "(Project is empty or all files were ignored)"

        tree_str = f"{self.project_root.name}/\n"
        paths = sorted([fi.path.relative_to(self.project_root) for fi in self._analysis_results])

        # Simple tree building logic (can be improved)
        # 簡単なツリー構築ロジック（改善可能）
        # This is a basic implementation. Libraries like `dirtree` could do this better.
        # これは基本的な実装です。`dirtree`のようなライブラリは、これをより良く行うことができます。
        structure = {}
        for path in paths:
            current_level = structure
            parts = list(path.parts)
            for i, part in enumerate(parts):
                if i == len(parts) - 1: # It's a file
                    current_level[part] = "file"
                else: # It's a directory
                    if part not in current_level:
                        current_level[part] = {}
                    if current_level[part] == "file": # Should not happen if scan is correct
                         pass # Or log warning
                    current_level = current_level[part]

        def build_tree_lines(dir_structure: dict, prefix: str = "", depth: int = 0) -> List[str]:
            lines = []
            entries = sorted(dir_structure.keys())
            if max_depth is not None and depth >= max_depth:
                if entries: lines.append(f"{prefix}└── ...")
                return lines

            for i, name in enumerate(entries):
                connector = "└── " if i == len(entries) - 1 else "├── "
                lines.append(f"{prefix}{connector}{name}")
                if isinstance(dir_structure[name], dict):
                    extension = "│   " if i < len(entries) - 1 else "    "
                    lines.extend(build_tree_lines(dir_structure[name], prefix + extension, depth + 1))
            return lines

        tree_lines = build_tree_lines(structure)
        return tree_str + "\n".join(tree_lines)

    def start_watching(self, user_callback: Optional[FileSystemEventCallback] = None):
        """
        Starts monitoring the project directory for file changes in a background thread.
        When a change occurs (and is not ignored), the cache is invalidated,
        and an optional user-provided callback is executed.
        バックグラウンドスレッドでプロジェクトディレクトリのファイル変更の監視を開始します。
        変更が発生し（そして無視されなかった場合）、キャッシュが無効になり、
        オプションでユーザー指定のコールバックが実行されます。

        Args:
            user_callback (Optional[FileSystemEventCallback], optional):
                A function to call when a file system event is detected.
                Receives the FileSystemEvent object as an argument.
                Defaults to None.
                ファイルシステムイベントが検出されたときに呼び出す関数。
                引数として FileSystemEvent オブジェクトを受け取ります。
                デフォルトは None。
        """
        if not self._use_cache or not self._cache_updater:
            logger.warning("Cannot start watching: Caching is disabled.")
            return

        if self._event_monitor and self._event_monitor.is_alive():
            logger.warning("File watcher is already running.")
            return

        # Initialize monitor on first use
        # 初回使用時にモニターを初期化します
        if self._event_monitor is None:
            logger.info("Initializing FileSystemEventMonitor...")
            self._event_monitor = FileSystemEventMonitor(self._project_root, self._ignore_processor)

        # Define the combined callback
        # 結合されたコールバックを定義します
        def combined_callback(event: FileSystemEvent):
            # Always invalidate cache first
            # 常に最初にキャッシュを無効化します
            if self._cache_updater:
                 try:
                    self._cache_updater.invalidate_cache_on_event(event)
                 except Exception as e:
                     logger.error(f"Error during cache invalidation callback: {e}", exc_info=True)

            # Then call the user callback if provided
            # 次に、提供されていればユーザーコールバックを呼び出します
            if user_callback:
                try:
                    user_callback(event)
                except Exception as e:
                    logger.error(f"Error in user-provided file watcher callback: {e}", exc_info=True)

        logger.info("Starting file watcher...")
        self._event_monitor.start(callback=combined_callback)

    def stop_watching(self):
        """
        Stops the file system monitoring thread if it is running.
        実行中の場合、ファイルシステム監視スレッドを停止します。
        """
        if self._event_monitor and self._event_monitor.is_alive():
            logger.info("Stopping file watcher...")
            self._event_monitor.stop()
        elif self._event_monitor:
             logger.info("File watcher was initialized but not running.")
        else:
            logger.info("File watcher was never started.")

    def clear_cache(self):
        """
        Clears the disk cache associated with this project instance.
        このプロジェクトインスタンスに関連付けられたディスクキャッシュをクリアします。
        """
        # Use the shared cache storage instance
        # 共有キャッシュストレージインスタンスを使用します
        logger.info("Clearing disk cache...")
        self._cache_storage.clear_cache() # Clear all types
        logger.info("Disk cache cleared.")

        # Also clear in-memory cache
        # インメモリキャッシュもクリアします
        self._analysis_results = None
        logger.info("In-memory cache cleared.")

        # Clear cache state in CacheUpdater if it exists
        # CacheUpdater が存在する場合、そのキャッシュ状態もクリアします
        if self._use_cache and self._cache_updater:
            self._cache_updater.clear_cache_state()
            logger.info("CacheUpdater state cleared.")

        logger.info(f"Cache cleared successfully for project: {self.project_root}")

    def get_dependencies(self, file_path: str | Path) -> List[DependencyInfo]:
        """
        Gets the list of dependencies for a specific file identified during analysis.
        分析中に特定された特定のファイルの依存関係リストを取得します。

        This method relies on the results of the last `analyze_project` call.
        It currently only extracts dependencies for Python files.
        このメソッドは、最後の `analyze_project` 呼び出しの結果に依存します。
        現在は Python ファイルの依存関係のみを抽出します。

        Args:
            file_path (str | Path): The path to the file (absolute or relative to project root).
                                    ファイルへのパス（絶対パスまたはプロジェクトルートからの相対パス）。

        Returns:
            List[DependencyInfo]: A list of dependencies found in the file. Returns an empty
                                  list if the file was not analyzed, not found, or has no dependencies.
                                  ファイルで見つかった依存関係のリスト。ファイルが分析されなかった、
                                  見つからなかった、または依存関係がない場合は空のリストを返します。

        Raises:
            AnalysisError: If the project has not been analyzed yet (`analyze_project` was not called).
                          プロジェクトがまだ分析されていない場合（`analyze_project` が呼び出されていない場合）。
        """
        if self._analysis_results is None:
            raise AnalysisError("Project must be analyzed before getting dependencies. Call analyze_project() first.")

        # Resolve the input path to an absolute path
        # 入力パスを絶対パスに解決します
        try:
            absolute_path = self._path_resolver.resolve_absolute(file_path, base_dir=self.project_root)
        except FileNotFoundError as e:
            # This happens if the input path itself doesn't exist on the filesystem
            # これは、入力パス自体がファイルシステムに存在しない場合に発生します
            logger.warning(f"Path {file_path} not found on filesystem.")
            # Propagate as a specific KotemariError
            # 特定の KotemariError として伝播させます
            raise DependencyError(f"Path {file_path} not found on filesystem.") from e
        except Exception as e:
            logger.warning(f"Error resolving path {file_path} for dependency lookup: {e}")
            return []

        # Find the FileInfo object for the given path
        # 指定されたパスの FileInfo オブジェクトを検索します
        target_file_info: Optional[FileInfo] = None
        for fi in self._analysis_results:
            if fi.path == absolute_path:
                target_file_info = fi
                break

        if target_file_info:
            logger.debug(f"Found {len(target_file_info.dependencies)} dependencies for {absolute_path.name}.")
            return target_file_info.dependencies
        else:
            # File was not found within the analyzed files (might exist but be ignored)
            # 分析されたファイル内にファイルが見つかりませんでした（存在するが無視されている可能性があります）
            raise FileNotFoundErrorInAnalysis(
                f"File '{absolute_path.name}' not found in analysis results (it might be ignored or outside the project scope)."
            )

    def get_context(self, target_paths: List[str]) -> str:
        """
        Generates a context string from the content of the specified target files.
        指定されたターゲットファイルの内容からコンテキスト文字列を生成します。

        Args:
            target_paths: A list of paths (relative to project root or absolute)
                          to the target files.
                          ターゲットファイルへのパス（プロジェクトルートからの相対パスまたは絶対パス）のリスト。

        Returns:
            str: The generated context string.
                 生成されたコンテキスト文字列。

        Raises:
            AnalysisError: If the project has not been analyzed yet.
                          プロジェクトがまだ分析されていない場合。
            FileNotFoundErrorInAnalysis: If any target file is not found within the analyzed project scope.
                                       分析されたプロジェクトスコープ内でターゲットファイルが見つからない場合。
            ContextGenerationError: If there is an error during context generation (e.g., reading files).
                                    コンテキスト生成中にエラーが発生した場合（例：ファイルの読み取り）。
        """
        self._ensure_analyzed()

        # English: Resolve target paths to absolute paths
        # 日本語: ターゲットパスを絶対パスに解決します
        absolute_target_paths = [self._path_resolver.resolve_absolute(p) for p in target_paths]

        # English: Verify that target files are known from the analysis (optional but good practice)
        # 日本語: ターゲットファイルが分析から既知であることを確認します（オプションですが、良い習慣です）
        # This check prevents trying to build context for files outside the project or ignored files.
        # このチェックにより、プロジェクト外のファイルや無視されたファイルに対してコンテキストを構築しようとするのを防ぎます。
        for p in absolute_target_paths:
            # Check against the in-memory analysis results
            # メモリ内の分析結果に対してチェックします
            if not any(fi.path == p for fi in self._analysis_results):
                 raise FileNotFoundErrorInAnalysis(
                     f"Target file {p.relative_to(self.project_root)} not found in analyzed project data (it might be ignored or outside the project scope)."
                 )

        try:
            # English: Use the ContextBuilder use case
            # 日本語: ContextBuilder ユースケースを使用します
            context_data: ContextData = self.context_builder.build_context(
                target_files=absolute_target_paths,
                project_root=Path(self.project_root)
            )
            return context_data.context_string
        except FileNotFoundError as e: # Should theoretically not happen due to checks above
            logger.error(f"Filesystem error during context generation (should have been caught earlier): {e}")
            raise ContextGenerationError(f"File system error: {e}") from e
        except IOError as e:
            logger.error(f"Error during context generation: {e}")
            raise ContextGenerationError(f"Error reading file content: {e}") from e
        except KotemariError as e: # Catch other Kotemari specific errors from ContextBuilder
            logger.error(f"Kotemari error during context generation: {e}")
            raise # Re-raise KotemariError subclasses
        except Exception as e: # Catch unexpected errors
            logger.exception(f"Unexpected error during context generation: {e}")
            # Raise a more generic error or handle differently
            # より一般的なエラーを発生させるか、異なる方法で処理します
            raise ContextGenerationError(f"An unexpected error occurred: {e}") from e

    def _ensure_analyzed(self) -> None:
        """
        Ensures that the project analysis has been performed.
        プロジェクト分析が実行されたことを確認します。

        Raises:
            AnalysisError: If analysis has not been performed.
                          分析が実行されていない場合。
        """
        if not self.project_analyzed:
            logger.error("Project must be analyzed first. Call analyze_project() first.")
            raise AnalysisError("Project must be analyzed first. Call analyze_project() first.")

    def _resolve_path(self, path_str: str) -> Path:
        """
        Resolves a path string to a Path object.
        パス文字列を Path オブジェクトに解決します。

        Args:
            path_str (str): The path string to resolve.
                            解決するパス文字列。

        Returns:
            Path: The resolved path object.
                 解決されたパスオブジェクト。
        """
        # English: Simply return the path object.
        # 日本語: 単にパスオブジェクトを返します。
        return Path(path_str)