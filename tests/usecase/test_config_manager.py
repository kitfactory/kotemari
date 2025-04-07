import pytest
from pathlib import Path
import yaml

from kotemari.usecase.config_manager import ConfigManager, DEFAULT_CONFIG_FILENAME
from kotemari.utility.path_resolver import PathResolver
from kotemari.domain.project_config import ProjectConfig

# Fixture for PathResolver
@pytest.fixture
def path_resolver() -> PathResolver:
    return PathResolver()

# Fixture to create a directory structure with potential config files
@pytest.fixture
def setup_config_files(tmp_path: Path):
    # Structure:
    # tmp_path/
    #   outer_dir/
    #     project_root/
    #       .kotemari.yml (valid)
    #       src/
    #         main.py
    #   another_project/
    #     .kotemari.yml (empty)
    #   project_with_no_config/
    #     file.txt
    #   project_with_invalid_config/
    #     .kotemari.yml (invalid yaml)

    outer_dir = tmp_path / "outer_dir"
    project_root = outer_dir / "project_root"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "main.py").touch()
    valid_config_path = project_root / DEFAULT_CONFIG_FILENAME
    valid_config_content = {
        "exclude": ["*.log", "__pycache__/"],
        "llm_model": "gpt-4"
    }
    with valid_config_path.open('w', encoding='utf-8') as f:
        yaml.dump(valid_config_content, f)

    another_project = tmp_path / "another_project"
    another_project.mkdir()
    empty_config_path = another_project / DEFAULT_CONFIG_FILENAME
    empty_config_path.touch()

    project_no_config = tmp_path / "project_with_no_config"
    project_no_config.mkdir()
    (project_no_config / "file.txt").touch()

    project_invalid_config = tmp_path / "project_with_invalid_config"
    project_invalid_config.mkdir()
    invalid_config_path = project_invalid_config / DEFAULT_CONFIG_FILENAME
    invalid_config_path.write_text("key: value: nested_error", encoding='utf-8') # Invalid YAML

    return {
        "project_root": project_root,
        "valid_config": valid_config_path,
        "another_project": another_project,
        "empty_config": empty_config_path,
        "project_no_config": project_no_config,
        "project_invalid_config": project_invalid_config,
        "invalid_config": invalid_config_path
    }

# --- Tests for find_config_file --- #

def test_find_config_file_found_in_root(setup_config_files, path_resolver):
    """
    Tests finding the config file directly in the project root.
    プロジェクトルートで直接設定ファイルを見つけるテスト。
    """
    manager = ConfigManager(path_resolver, setup_config_files["project_root"])
    found_path = manager.find_config_file()
    assert found_path == setup_config_files["valid_config"]

def test_find_config_file_found_in_parent(setup_config_files, path_resolver):
    """
    Tests finding the config file in a parent directory of the starting directory.
    開始ディレクトリの親ディレクトリで設定ファイルを見つけるテスト。
    """
    # Start search from src_dir, should find config in project_root
    # src_dir から検索を開始し、project_root で設定を見つけるはず
    start_dir = setup_config_files["project_root"] / "src"
    manager = ConfigManager(path_resolver, start_dir) # project_root is still the logical root for find
    found_path = manager.find_config_file() # find searches upwards from the *initial* project_root
    assert found_path == setup_config_files["valid_config"]

def test_find_config_file_not_found(setup_config_files, path_resolver):
    """
    Tests when the config file does not exist in the hierarchy.
    階層内に設定ファイルが存在しない場合のテスト。
    """
    manager = ConfigManager(path_resolver, setup_config_files["project_no_config"])
    found_path = manager.find_config_file()
    assert found_path is None

# --- Tests for load_config / get_config --- #

def test_load_config_success(setup_config_files, path_resolver):
    """
    Tests loading a valid configuration file.
    有効な設定ファイルを読み込むテスト。
    """
    manager = ConfigManager(path_resolver, setup_config_files["project_root"])
    config = manager.load_config()
    assert isinstance(config, ProjectConfig)
    # TODO: Update this assertion when ProjectConfig has attributes
    # ProjectConfig に属性が追加されたら、このアサーションを更新する
    # assert config.exclude == ["*.log", "__pycache__/"]
    # assert config.llm_model == "gpt-4"
    assert manager.get_config_path() == setup_config_files["valid_config"]
    # Test caching
    # キャッシュのテスト
    config_again = manager.get_config()
    assert config is config_again # Should be the same object

def test_load_config_empty_file(setup_config_files, path_resolver):
    """
    Tests loading an empty configuration file.
    空の設定ファイルを読み込むテスト。
    """
    manager = ConfigManager(path_resolver, setup_config_files["another_project"])
    config = manager.load_config()
    assert isinstance(config, ProjectConfig)
    # Should be an empty ProjectConfig
    # 空の ProjectConfig である必要があります
    assert len(vars(config)) == 0 # Check if it has no attributes set
    assert manager.get_config_path() == setup_config_files["empty_config"]

def test_load_config_not_found_returns_default(setup_config_files, path_resolver):
    """
    Tests that a default ProjectConfig is returned when no file is found.
    ファイルが見つからない場合にデフォルトの ProjectConfig が返されるテスト。
    """
    manager = ConfigManager(path_resolver, setup_config_files["project_no_config"])
    config = manager.load_config()
    assert isinstance(config, ProjectConfig)
    assert len(vars(config)) == 0
    assert manager.get_config_path() is None

def test_load_config_invalid_yaml(setup_config_files, path_resolver, caplog):
    """
    Tests loading an invalid YAML file, expecting a default config and a warning.
    無効な YAML ファイルを読み込み、デフォルト設定と警告を期待するテスト。
    """
    # caplog fixture captures logging output
    # caplog フィクスチャはロギング出力をキャプチャします
    manager = ConfigManager(path_resolver, setup_config_files["project_invalid_config"])
    config = manager.load_config()
    assert isinstance(config, ProjectConfig)
    assert len(vars(config)) == 0 # Should fall back to default
    assert manager.get_config_path() == setup_config_files["invalid_config"]
    # Check for warning log message
    # 警告ログメッセージを確認します
    assert "Error loading configuration file" in caplog.text
    assert "Using default configuration" in caplog.text

def test_get_config_loads_if_needed(setup_config_files, path_resolver):
    """
    Tests that get_config() triggers loading if config hasn't been loaded.
    設定が読み込まれていない場合に get_config() が読み込みをトリガーするテスト。
    """
    manager = ConfigManager(path_resolver, setup_config_files["project_root"])
    assert manager._config is None # Initially not loaded
    config = manager.get_config() # Trigger loading
    assert manager._config is not None
    assert isinstance(config, ProjectConfig)
    assert manager._config_path is not None 