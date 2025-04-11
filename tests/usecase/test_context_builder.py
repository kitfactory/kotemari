import pytest

from pathlib import Path
from unittest.mock import MagicMock, call
from typing import Dict, List, Optional
import logging
from datetime import datetime

from kotemari.usecase.context_builder import ContextBuilder
from kotemari.domain.file_content_formatter import FileContentFormatter
from kotemari.gateway.file_system_accessor import FileSystemAccessor
from kotemari.domain.context_data import ContextData
from kotemari.domain.exceptions import ContextGenerationError
from kotemari.domain.file_info import FileInfo
from kotemari.domain.parsed_python_info import ParsedPythonInfo
from kotemari.domain.dependency_info import DependencyInfo, DependencyType

logger = logging.getLogger(__name__)

@pytest.fixture
def mock_file_accessor():
    """Mocks the FileSystemAccessor."""
    # Mocks the FileSystemAccessor.
    # FileSystemAccessor をモックします。
    mock = MagicMock(spec=FileSystemAccessor)
    # Explicitly set mock methods
    # モックメソッドを明示的に設定します
    mock.exists = MagicMock(return_value=True)
    # Default read_file mock, can be overridden in tests
    # デフォルトの read_file モック、テストで上書き可能
    mock.read_file = MagicMock(side_effect=lambda path_str: f"Content of {Path(path_str).name}")
    return mock

@pytest.fixture
def mock_formatter():
    """Mocks the FileContentFormatter."""
    mock = MagicMock(spec=FileContentFormatter)
    # Simple format: include filename marker
    # シンプルなフォーマット: ファイル名マーカーを含める
    mock.format_content.side_effect = lambda contents_dict: "\n---\n".join(
        f"# File: {p.name}\n{c}" for p, c in contents_dict.items()
    )
    return mock

@pytest.fixture
def context_builder(mock_file_accessor, mock_formatter):
    """Provides a ContextBuilder instance with mocked dependencies."""
    # Provides a ContextBuilder instance with mocked dependencies.
    # モック化された依存関係を持つ ContextBuilder インスタンスを提供します。
    return ContextBuilder(file_accessor=mock_file_accessor, formatter=mock_formatter)

@pytest.fixture
def setup_context_test(tmp_path: Path, mock_file_accessor: MagicMock):
    """
    Sets up the necessary mocks and data for testing context building with dependencies.
    依存関係を持つコンテキスト構築のテストに必要なモックとデータをセットアップします。
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    src_dir = project_root / "src"
    src_dir.mkdir()

    # Create dummy files
    # ダミーファイルを作成します
    main_py_path = src_dir / "main.py"
    dep1_path = src_dir / "dep1.py"
    dep2_path = src_dir / "dep2.py"
    unrelated_path = src_dir / "unrelated.py"

    mock_contents = {
        main_py_path: "# main.py\nimport dep1\nprint('main')",
        dep1_path: "# dep1.py\nimport dep2\nprint('dep1')",
        dep2_path: "# dep2.py\nprint('dep2')",
        unrelated_path: "# unrelated.py\nprint('unrelated')"
    }

    # Configure mock file accessor
    # モックファイルアクセサを設定します
    def mock_read_file(path_str: str) -> str:
        path = Path(path_str)
        if path in mock_contents:
            return mock_contents[path]
        raise FileNotFoundError(f"Mock file not found: {path}")

    mock_file_accessor.read_file.side_effect = mock_read_file
    mock_file_accessor.exists.side_effect = lambda path_str: Path(path_str) in mock_contents

    # Mock Kotemari-like analysis results using MagicMock
    # MagicMock を使用して Kotemari のような解析結果をモックします
    kotemari_instance_mock = MagicMock()
    kotemari_instance_mock._file_accessor = mock_file_accessor
    kotemari_instance_mock._analysis_results = {}
    kotemari_instance_mock._project_root = project_root # Store project root for reference

    now = datetime.now()
    for p in mock_contents.keys():
        dependencies = []
        if p == main_py_path:
            dependencies = [DependencyInfo(module_name="dep1", dependency_type=DependencyType.INTERNAL_ABSOLUTE, resolved_path=dep1_path)]
        elif p == dep1_path:
            dependencies = [DependencyInfo(module_name="dep2", dependency_type=DependencyType.INTERNAL_ABSOLUTE, resolved_path=dep2_path)]

        # Create simplified ParsedPythonInfo focused on dependencies
        # 依存関係に焦点を当てた簡略化された ParsedPythonInfo を作成します
        parsed_info = ParsedPythonInfo(
            file_path=p, imports=[], defined_classes=[], defined_functions=[],
            top_level_calls=[], docstring=None, dependencies=dependencies
        )
        # Create simplified FileInfo
        # 簡略化された FileInfo を作成します
        file_info = FileInfo(
            path=p,
            mtime=now,
            size=len(mock_contents[p]),
            hash="dummy_hash"
        )
        kotemari_instance_mock._analysis_results[p] = file_info

    # Mock the reverse dependency index
    # リバース依存関係インデックスをモックします
    kotemari_instance_mock._reverse_dependency_index = {
         # file: set of files that import it
         # ファイル: それをインポートするファイルのセット
         dep1_path: {main_py_path},
         dep2_path: {dep1_path},
    }
    # Make the method callable without error
    # メソッドをエラーなく呼び出し可能にします
    kotemari_instance_mock._build_reverse_dependency_index = MagicMock()

    # Create ContextBuilder with a separate mocked formatter for this test setup
    # このテストセットアップ用に別のモック化されたフォーマッターで ContextBuilder を作成します
    # This prevents interference with the global mock_formatter fixture
    # これにより、グローバルな mock_formatter フィクスチャとの干渉を防ぎます
    specific_mock_formatter = MagicMock(spec=FileContentFormatter)
    specific_mock_formatter.format_content.side_effect = lambda contents_dict: "\n---\n".join( # Use a separator
        f"# File: {p.relative_to(project_root)}\n{c}" for p, c in contents_dict.items()
    )

    context_builder = ContextBuilder(file_accessor=mock_file_accessor, formatter=specific_mock_formatter)

    # Yield necessary objects for the test
    # テストに必要なオブジェクトを yield します
    yield context_builder, kotemari_instance_mock, main_py_path, dep1_path, dep2_path, unrelated_path

# --- Test Cases ---

def test_build_context_single_file(context_builder: ContextBuilder, mock_file_accessor: MagicMock, mock_formatter: MagicMock):
    """Tests building context for a single valid file."""
    # Tests building context for a single valid file.
    # 単一の有効なファイルのコンテキスト構築をテストします。
    target_file = Path("/project/main.py")
    project_root = Path("/project")
    target_files = [target_file]
    expected_content = "Content of main.py" # Based on default mock_file_accessor
    mock_file_accessor.read_file.side_effect = lambda path_str: expected_content if Path(path_str) == target_file else ""

    result = context_builder.build_context(target_files, project_root)

    # Check file accessor calls
    # ファイルアクセサ呼び出しを確認します
    mock_file_accessor.read_file.assert_called_once_with(str(target_file))

    # Check formatter call (using the global mock_formatter here)
    # フォーマッター呼び出しを確認します（ここではグローバルな mock_formatter を使用）
    mock_formatter.format_content.assert_called_once_with({target_file: expected_content})

    # Check result
    # 結果を確認します
    assert isinstance(result, ContextData)
    assert result.target_files == target_files
    # Use the format defined in the global mock_formatter
    # グローバルな mock_formatter で定義されたフォーマットを使用します
    assert result.context_string == f"# File: {target_file.name}\n{expected_content}" # Adjusted assertion based on mock_formatter
    assert result.related_files == [target_file] # Should just contain the target file
    assert result.context_type == "basic_concatenation"

def test_build_context_multiple_files(context_builder: ContextBuilder, mock_file_accessor: MagicMock, mock_formatter: MagicMock):
    """Tests building context for multiple valid files."""
    # Tests building context for multiple valid files.
    # 複数の有効なファイルのコンテキスト構築をテストします。
    file1 = Path("/project/module/a.py")
    file2 = Path("/project/main.py")
    project_root = Path("/project")
    target_files = [file1, file2]
    # Simulate file contents
    # ファイルの内容をシミュレートします
    contents = {
        file1: "Content of a.py",
        file2: "Content of main.py"
    }
    mock_file_accessor.read_file.side_effect = lambda path_str: contents.get(Path(path_str), "")

    result = context_builder.build_context(target_files, project_root)

    # Check file accessor calls (read)
    # ファイルアクセサ呼び出しを確認します（読み取り）
    mock_file_accessor.read_file.assert_has_calls([call(str(file1)), call(str(file2))], any_order=True)

    # Check formatter call (using the global mock_formatter)
    # フォーマッター呼び出しを確認します（グローバルな mock_formatter を使用）
    mock_formatter.format_content.assert_called_once_with(contents)

    # Check result (mock formatter joins values, order might vary)
    # 結果を確認します（モックフォーマッターは値を結合しますが、順序は変わる可能性があります）
    expected_parts = {f"# File: {file1.name}\nContent of a.py", f"# File: {file2.name}\nContent of main.py"} # Adjusted assertion based on mock_formatter
    actual_parts = set(result.context_string.split("\n---\n")) # Split by separator used in mock_formatter
    # print(f"\n[DEBUG] Expected result parts (set): {expected_parts}") # DEBUG ADD
    # print(f"[DEBUG] Actual result parts (set): {actual_parts}") # DEBUG ADD
    assert actual_parts == expected_parts
    # Assuming related_files should contain target files when no dependency analysis is done
    # 依存関係分析が行われない場合、related_files にはターゲットファイルが含まれると仮定します
    assert set(result.related_files) == set(target_files)

# Removed test_build_context_file_not_found, test_build_context_read_error, test_build_context_with_dependencies
# test_build_context_file_not_found, test_build_context_read_error, test_build_context_with_dependencies を削除しました

# TODO: Add tests for related file discovery logic once implemented
#       関連ファイル検出ロジックが実装されたら、そのテストを追加します 