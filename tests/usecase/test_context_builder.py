import pytest
from pathlib import Path
from unittest.mock import MagicMock, call
from typing import Dict
import logging

from kotemari.usecase.context_builder import ContextBuilder
from kotemari.domain.file_content_formatter import FileContentFormatter
from kotemari.gateway.file_system_accessor import FileSystemAccessor
from kotemari.domain.context_data import ContextData
from kotemari.domain.exceptions import ContextGenerationError

logger = logging.getLogger(__name__)

@pytest.fixture
def mock_file_accessor():
    """Mocks the FileSystemAccessor."""
    # Mocks the FileSystemAccessor.
    # FileSystemAccessor をモックします。
    mock = MagicMock(spec=FileSystemAccessor) # Remove autospec=True
    # Explicitly set mock methods
    # モックメソッドを明示的に設定します
    mock.exists = MagicMock(return_value=True)
    mock.read_file = MagicMock(side_effect=lambda path, project_root=None: f"Content of {Path(path).name}")
    return mock

@pytest.fixture
def mock_formatter():
    """Mocks the FileContentFormatter."""
    mock = MagicMock(spec=FileContentFormatter)
    # Simple format: just join contents with newline
    mock.format_content.side_effect = lambda contents: "\n".join(contents.values())
    return mock

@pytest.fixture
def context_builder(mock_file_accessor, mock_formatter):
    """Provides a ContextBuilder instance with mocked dependencies."""
    return ContextBuilder(file_accessor=mock_file_accessor, formatter=mock_formatter)

# --- Test Cases ---

def test_build_context_single_file(context_builder: ContextBuilder, mock_file_accessor: MagicMock, mock_formatter: MagicMock):
    """Tests building context for a single valid file."""
    target_file = Path("/project/main.py")
    project_root = Path("/project")
    target_files = [target_file]

    result = context_builder.build_context(target_files, project_root)

    # Check file accessor calls
    # mock_file_accessor.exists.assert_called_once_with(str(target_file)) # Removed exists check
    mock_file_accessor.read_file.assert_called_once_with(str(target_file))

    # Check formatter call
    mock_formatter.format_content.assert_called_once_with({target_file: "Content of main.py"})

    # Check result
    assert isinstance(result, ContextData)
    assert result.target_files == target_files
    assert result.context_string == "Content of main.py" # Based on mock formatter
    assert result.related_files is None
    assert result.context_type == "basic_concatenation"

def test_build_context_multiple_files(context_builder: ContextBuilder, mock_file_accessor: MagicMock, mock_formatter: MagicMock):
    """Tests building context for multiple valid files."""
    file1 = Path("/project/module/a.py")
    file2 = Path("/project/main.py")
    project_root = Path("/project")
    target_files = [file1, file2]
    # Simulate file contents
    contents = {
        file1: "Content of a.py",
        file2: "Content of main.py"
    }
    mock_file_accessor.read_file.side_effect = lambda path, project_root=None: contents[Path(path)]

    result = context_builder.build_context(target_files, project_root)

    # Check file accessor calls (existence and read)
    # mock_file_accessor.exists.assert_has_calls([call(str(file1)), call(str(file2))], any_order=True) # Removed exists check
    mock_file_accessor.read_file.assert_has_calls([call(str(file1)), call(str(file2))], any_order=True)

    # Check formatter call
    expected_content_dict = {file1: "Content of a.py", file2: "Content of main.py"}
    mock_formatter.format_content.assert_called_once_with(expected_content_dict)

    # Check result (mock formatter joins values, order might vary)
    # 結果を確認します（モックフォーマッターは値を結合しますが、順序は変わる可能性があります）
    expected_parts = {"Content of a.py", "Content of main.py"}
    actual_parts = set(result.context_string.split('\n'))
    print(f"\n[DEBUG] Expected result parts (set): {expected_parts}") # DEBUG ADD
    print(f"[DEBUG] Actual result parts (set): {actual_parts}") # DEBUG ADD
    assert actual_parts == expected_parts
    # assert result.context_string == "Content of a.py\nContent of main.py" # Order depends on dict iteration in mock

def test_build_context_file_not_found(context_builder: ContextBuilder, mock_file_accessor: MagicMock):
    """Tests building context when a target file does not exist."""
    target_file = Path("/project/nonexistent.py")
    project_root = Path("/project")
    target_files = [target_file]
    # Simulate read_file raising FileNotFoundError (wrapped in ContextGenerationError)
    # read_file が FileNotFoundError (ContextGenerationErrorでラップされる) を発生させるのをシミュレートします
    mock_file_accessor.read_file.side_effect = FileNotFoundError("Mock file not found during read")

    # Expect ContextGenerationError because the file couldn't be read (even if exists check was removed)
    # ファイルが読み取れなかったため ContextGenerationError を期待します（exists チェックが削除されたとしても）
    with pytest.raises(ContextGenerationError, match="Error accessing file content: Mock file not found"):
        context_builder.build_context(target_files, project_root)

def test_build_context_read_error(context_builder: ContextBuilder, mock_file_accessor: MagicMock):
    """Tests building context when reading a file fails."""
    target_file = Path("/project/readable.py")
    project_root = Path("/project")
    target_files = [target_file]
    mock_file_accessor.exists.return_value = True
    mock_file_accessor.read_file.side_effect = IOError("Permission denied") # Simulate read error

    # Expect ContextGenerationError wrapping the IOError
    # IOError をラップする ContextGenerationError を期待します
    with pytest.raises(ContextGenerationError, match="Error reading file content: Permission denied"):
        context_builder.build_context(target_files, project_root)

    mock_file_accessor.read_file.assert_called_once_with(str(target_file))


# TODO: Add tests for related file discovery logic once implemented
#       関連ファイル検出ロジックが実装されたら、そのテストを追加します 