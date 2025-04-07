from pathlib import Path
import yaml
import logging
from typing import Optional

from ..domain.project_config import ProjectConfig
from ..utility.path_resolver import PathResolver

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = ".kotemari.yml"

class ConfigManager:
    """
    Manages loading and accessing the project configuration.
    Searches for a configuration file (default: .kotemari.yml) in the project root or parent directories.
    プロジェクト設定の読み込みとアクセスを管理します。
    設定ファイル（デフォルト: .kotemari.yml）をプロジェクトルートまたは親ディレクトリで検索します。
    """

    def __init__(self, path_resolver: PathResolver, project_root: Path | str):
        """
        Initializes the ConfigManager.
        ConfigManager を初期化します。

        Args:
            path_resolver (PathResolver): An instance of PathResolver.
                                          PathResolver のインスタンス。
            project_root (Path | str): The root directory of the project being analyzed.
                                       解析対象プロジェクトのルートディレクトリ。
        """
        self.path_resolver = path_resolver
        self.project_root = self.path_resolver.resolve_absolute(project_root)
        self._config: Optional[ProjectConfig] = None
        self._config_path: Optional[Path] = None

    def find_config_file(self) -> Optional[Path]:
        """
        Searches for the configuration file upwards from the project root.
        プロジェクトルートから上方向に設定ファイルを検索します。

        Returns:
            Optional[Path]: The path to the found configuration file, or None if not found.
                            見つかった設定ファイルのパス。見つからない場合は None。
        """
        current_dir = self.project_root
        while True:
            potential_path = current_dir / DEFAULT_CONFIG_FILENAME
            if potential_path.is_file():
                logger.info(f"Configuration file found at: {potential_path}")
                return potential_path

            if current_dir.parent == current_dir: # Reached the root
                logger.info(f"{DEFAULT_CONFIG_FILENAME} not found in project hierarchy starting from {self.project_root}.")
                return None
            current_dir = current_dir.parent

    def load_config(self) -> ProjectConfig:
        """
        Loads the configuration from the found file or returns a default config.
        Caches the loaded configuration.
        見つかったファイルから設定を読み込むか、デフォルト設定を返します。
        読み込んだ設定はキャッシュします。

        Returns:
            ProjectConfig: The loaded or default project configuration.
                           読み込まれた、またはデフォルトのプロジェクト設定。
        """
        if self._config is not None:
            return self._config

        self._config_path = self.find_config_file()
        loaded_data = {}
        if self._config_path:
            try:
                with self._config_path.open('r', encoding='utf-8') as f:
                    loaded_data = yaml.safe_load(f) or {}
                logger.info(f"Successfully loaded configuration from {self._config_path}")
            except Exception as e:
                logger.warning(f"Error loading configuration file {self._config_path}: {e}. Using default configuration.", exc_info=True)
                loaded_data = {}
        else:
            logger.info("Using default configuration as no config file was found.")

        # TODO: Populate ProjectConfig attributes based on loaded_data
        # 将来的に、loaded_data から ProjectConfig の属性を設定する
        # self._config = ProjectConfig(**loaded_data) # Currently empty
        # For now, ignore loaded data and create an empty config
        # 現時点では、読み込んだデータを無視して空の設定を作成する
        self._config = ProjectConfig() # Pass no arguments

        return self._config

    def get_config(self) -> ProjectConfig:
        """
        Returns the cached configuration, loading it if necessary.
        キャッシュされた設定を返します。必要に応じて読み込みます。

        Returns:
            ProjectConfig: The project configuration.
                           プロジェクト設定。
        """
        if self._config is None:
            self.load_config()
        # We can assert self._config is not None here because load_config ensures it's set.
        # load_config が設定を保証するため、ここでは self._config が None でないことを表明できます。
        assert self._config is not None
        return self._config

    def get_config_path(self) -> Optional[Path]:
        """
        Returns the path of the loaded configuration file, if found.
        読み込まれた設定ファイルのパスを返します（見つかった場合）。

        Returns:
            Optional[Path]: The path to the configuration file or None.
                            設定ファイルへのパス、または None。
        """
        if self._config is None:
             self.load_config() # Ensure config search has happened
        return self._config_path 