from pathlib import Path
from typing import List, Optional, Callable
import logging

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

logger = logging.getLogger(__name__)

class Kotemari:
    """
    The main facade class for the Kotemari library.
    Provides methods to analyze projects, list files, and generate context.
    Kotemari ライブラリのメインファサードクラス。
    プロジェクトの分析、ファイル一覧表示、コンテキスト生成などのメソッドを提供します。
    """

    def __init__(self, project_root: Path | str, config_path: Optional[Path | str] = None, use_cache: bool = True):
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
        """
        self._path_resolver = PathResolver()
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
        self._project_analyzer: ProjectAnalyzer = ProjectAnalyzer(
            project_root=self._project_root,
            path_resolver=self._path_resolver, # Pass resolver
            config_manager=self._config_manager, # Pass config manager
            ignore_processor=self._ignore_processor # Pass ignore processor
            # Let Analyzer create its own fs_accessor, hash_calculator, language_detector if needed
            # 必要に応じて、Analyzer に独自の fs_accessor, hash_calculator, language_detector を作成させます
        )

        self._use_cache = use_cache
        self._cache_storage = CacheStorage(self._project_root) # Create storage directly
        self._cache_updater: Optional[CacheUpdater] = None
        self._analysis_results: Optional[List[FileInfo]] = None # Cache for analysis results
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

        # Return in-memory cache if available and not forcing reanalyze
        # メモリ内キャッシュが利用可能で、再分析を強制しない場合はそれを返します
        if self._analysis_results is not None and not force_reanalyze:
            logger.info("Returning in-memory cached analysis results.")
            return self._analysis_results

        if self._use_cache and self._cache_updater and not force_reanalyze:
            logger.info("Cache enabled. Checking cache validity...")
            # 1. Perform analysis to get current state for validation
            # 1. 検証のために現在の状態を取得するための分析を実行します
            # This is needed to calculate the current state hash.
            # これは現在の状態ハッシュを計算するために必要です。
            logger.debug("Performing preliminary analysis to determine current project state...")
            current_files = self._project_analyzer.analyze()
            logger.debug(f"Preliminary analysis complete. Found {len(current_files)} files.")

            # 2. Try to load and validate the cache using the current state
            # 2. 現在の状態を使用してキャッシュの読み込みと検証を試みます
            cached_results = self._cache_updater.get_valid_cache(current_files)

            if cached_results is not None:
                # Cache is valid, use it
                # キャッシュは有効です、それを使用します
                logger.info(f"Valid cache found. Returning {len(cached_results)} cached results.")
                self._analysis_results = cached_results # Store in memory
                return self._analysis_results
            else:
                # Cache was invalid or not found, use the results from the preliminary analysis
                # キャッシュが無効または見つかりませんでした。予備分析の結果を使用します
                logger.info("Cache invalid or not found. Using preliminary analysis results.")
                self._analysis_results = current_files # Store in memory
                # Update the cache with the results we just computed
                # 計算したばかりの結果でキャッシュを更新します
                logger.info("Updating cache with new analysis results...")
                self._cache_updater.update_cache(self._analysis_results)
                logger.info("Cache updated successfully.")
                return self._analysis_results

        # Cache disabled, or force_reanalyze=True, or CacheUpdater not available
        # キャッシュが無効、または force_reanalyze=True、または CacheUpdater が利用不可
        logger.info("Performing full project analysis (cache disabled, forced, or updater missing)...")
        self._analysis_results = self._project_analyzer.analyze()
        logger.info(f"Full analysis complete. Found {len(self._analysis_results)} files.")

        # If cache is enabled, update it even if analysis was forced (to store the latest)
        # キャッシュが有効な場合、分析が強制された場合でも更新します（最新のものを保存するため）
        if self._use_cache and self._cache_updater:
            logger.info("Updating cache with forced analysis results...")
            self._cache_updater.update_cache(self._analysis_results)
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
            RuntimeError: If the project has not been analyzed yet.
                          プロジェクトがまだ分析されていない場合。
        """
        if self._analysis_results is None:
             # Optionally, call analyze_project automatically?
             # オプションで、analyze_project を自動的に呼び出しますか？
             # For now, require explicit analysis first.
             # 今のところ、最初に明示的な分析が必要です。
            # self.analyze_project()
             raise RuntimeError("Project must be analyzed before listing files. Call analyze_project() first.")
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
            RuntimeError: If the project has not been analyzed yet.
                          プロジェクトがまだ分析されていない場合。
        """
        if self._analysis_results is None:
            raise RuntimeError("Project must be analyzed before generating tree. Call analyze_project() first.")

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
            RuntimeError: If the project has not been analyzed yet (`analyze_project` was not called).
                          プロジェクトがまだ分析されていない場合（`analyze_project` が呼び出されていない場合）。
        """
        if self._analysis_results is None:
            raise RuntimeError("Project must be analyzed before getting dependencies. Call analyze_project() first.")

        # Resolve the input path to an absolute path
        # 入力パスを絶対パスに解決します
        try:
            absolute_path = self._path_resolver.resolve_absolute(file_path, base_dir=self.project_root)
        except FileNotFoundError:
             logger.warning(f"Cannot resolve path for dependency lookup: {file_path}. It might not exist.")
             return []
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
            # File might exist but was ignored or not part of the analysis scope
            # ファイルは存在するかもしれませんが、無視されたか分析範囲に含まれていませんでした
            logger.warning(f"File '{absolute_path}' not found in analysis results. Cannot retrieve dependencies.")
            return []