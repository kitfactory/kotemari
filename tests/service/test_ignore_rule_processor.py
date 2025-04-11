import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import pathspec # Import pathspec

from kotemari.domain.project_config import ProjectConfig
from kotemari.gateway.gitignore_reader import GitignoreReader
from kotemari.service.ignore_rule_processor import IgnoreRuleProcessor
from kotemari.utility.path_resolver import PathResolver

# Fixture for PathResolver
@pytest.fixture
def path_resolver() -> PathResolver:
    return PathResolver() # Remove dummy root argument

# Fixture to set up a directory structure with .gitignore files
@pytest.fixture
def setup_ignore_test_structure(tmp_path: Path):
    # Structure similar to GitignoreReader tests, but focused on IgnoreRuleProcessor usage
    # GitignoreReader テストと似た構造ですが、IgnoreRuleProcessor の使用に焦点を当てています
    # tmp_path/
    #   .gitignore (root: *.log, build/)
    #   project/
    #     .gitignore (project: *.tmp, /src/generated/)
    #     src/
    #       main.py
    #       generated/
    #         code.py
    #       helper.tmp
    #     build/
    #       output.o
    #     README.md
    #   other.log

    root_gitignore = tmp_path / ".gitignore"
    root_gitignore.write_text("*.log\nbuild/\n")

    project_root = tmp_path / "project"
    project_root.mkdir()

    project_gitignore = project_root / ".gitignore"
    project_gitignore.write_text("*.tmp\n/src/generated/\n")

    src_dir = project_root / "src"
    src_dir.mkdir()
    (src_dir / "main.py").touch()
    generated_dir = src_dir / "generated"
    generated_dir.mkdir()
    (generated_dir / "code.py").touch()
    (src_dir / "helper.tmp").touch()

    build_dir_project = project_root / "build"
    build_dir_project.mkdir()
    (build_dir_project / "output.o").touch()

    (project_root / "README.md").touch()

    # File outside project, but under tmp_path
    # プロジェクト外だが、tmp_path 配下のファイル
    (tmp_path / "other.log").touch()

    return {"root": tmp_path, "project": project_root}

# --- Test Initialization and Loading --- #

def test_ignore_processor_initialization(setup_ignore_test_structure, path_resolver, monkeypatch):
    """
    Tests if the processor correctly finds and loads .gitignore specs on init.
    プロセッサが初期化時に .gitignore スペックを正しく見つけて読み込むかをテストします。
    """
    project_root = setup_ignore_test_structure["project"]
    # Mock GitignoreReader to verify it's called correctly
    # GitignoreReader をモックして、正しく呼び出されることを確認します

    # Create a mock object that looks like a PathSpec instance
    # PathSpec インスタンスのように見えるモックオブジェクトを作成します
    mock_spec = MagicMock(spec=pathspec.PathSpec)
    mock_spec.patterns = ["*.mock"] # Give it some dummy pattern attribute

    mock_find_all = MagicMock(return_value=[mock_spec]) # Return a list containing the mock spec
    monkeypatch.setattr(GitignoreReader, "find_and_read_all", mock_find_all)

    # Use an empty ProjectConfig for now
    # 現時点では空の ProjectConfig を使用します
    config = ProjectConfig()
    processor = IgnoreRuleProcessor(project_root, config, path_resolver)

    # Assert find_and_read_all was called with the correct project root
    # find_and_read_all が正しいプロジェクトルートで呼び出されたことを表明します
    mock_find_all.assert_called_once_with(project_root)
    # Now assert that the spec was *actually* added
    # スペックが *実際に* 追加されたことを表明します
    assert len(processor._gitignore_specs) == 1
    assert processor._gitignore_specs[0] is mock_spec # Check if the correct object was stored

# --- Test get_ignore_function --- #

@pytest.fixture
def ignore_func(setup_ignore_test_structure, path_resolver):
    """
    Provides the ignore function generated by the processor for the test structure.
    テスト構造に対してプロセッサによって生成された無視関数を提供します。
    """
    project_root = setup_ignore_test_structure["project"]
    config = ProjectConfig() # Empty config
    processor = IgnoreRuleProcessor(project_root, config, path_resolver)
    return processor.get_ignore_function()

@pytest.mark.parametrize(
    "file_path_relative, should_be_ignored",
    [
        ("src/main.py", False),            # Not ignored
        ("README.md", False),              # Not ignored
        ("src/helper.tmp", True),         # Ignored by project .gitignore (*.tmp)
        ("build/output.o", True),         # Ignored by root .gitignore (build/)
        ("src/generated/code.py", True),  # Ignored by project .gitignore (/src/generated/)
        ("../other.log", False),           # Outside project root, checked relative to root, ignored by root spec
                                          # プロジェクトルート外、ルートからの相対でチェック、ルートスペックで無視される
                                          # Let's refine this: pathspec matches relative to the gitignore's location
                                          # これを洗練させましょう：pathspec は gitignore の場所からの相対でマッチングします
                                          # The root ignore file applies to files *within* its directory (tmp_path)
                                          # ルートの無視ファイルは、そのディレクトリ内（tmp_path）のファイルに適用されます
                                          # Files outside the project_root given to the processor are not checked by default.
                                          # プロセッサに渡された project_root 外のファイルはデフォルトではチェックされません。
        # Correct expectation for file outside project root:
        ("../other.log", False),          # Path is outside the processor's project_root, so not ignored by it.
    ]
)
def test_ignore_function_gitignores(setup_ignore_test_structure, ignore_func, file_path_relative, should_be_ignored):
    """
    Tests the ignore function with various paths based on .gitignore rules.
    .gitignore ルールに基づいて、様々なパスで無視関数をテストします。
    """
    project_root = setup_ignore_test_structure["project"]
    abs_path = (project_root / file_path_relative).resolve() # Create absolute path

    # For the path outside the root, create it directly
    # ルート外のパスについては、直接作成します
    if ".." in file_path_relative:
        abs_path = (setup_ignore_test_structure["root"] / "other.log").resolve()

    assert ignore_func(abs_path) == should_be_ignored

def test_ignore_function_non_absolute_path(setup_ignore_test_structure, ignore_func, path_resolver, caplog):
    """
    Tests that a warning is logged if a non-absolute path is passed.
    非絶対パスが渡された場合に警告がログに記録されることをテストします。
    """
    project_root = setup_ignore_test_structure["project"]
    relative_path_str = "src/main.py"
    # Should resolve relative to project root and return False
    # プロジェクトルートからの相対で解決し、False を返すはず
    assert not ignore_func(Path(relative_path_str))
    assert "Received non-absolute path" in caplog.text
    # Check if the resolving phrase is present, not exact match
    # 解決フレーズが存在するかを確認し、完全一致ではない
    assert "Resolving relative to project root" in caplog.text

# TODO: Add tests for ignore rules from ProjectConfig when implemented
# TODO: ProjectConfig からの無視ルールが実装されたらテストを追加する 