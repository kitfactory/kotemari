import pytest
from pathlib import Path
import datetime
import os
from unittest.mock import patch, MagicMock, mock_open
import pickle
import io
import logging
import sys # Import sys for debug print

from kotemari.utility.path_resolver import PathResolver
from kotemari.gateway.file_system_accessor import FileSystemAccessor
from kotemari.domain.file_info import FileInfo
from kotemari.domain.exceptions import FileSystemError

# Helper to create a file structure for testing scan_directory
# scan_directory テスト用のファイル構造を作成するヘルパー
@pytest.fixture
def setup_test_directory(tmp_path: Path) -> Path:
    base = tmp_path / "project_root"
    base.mkdir() # Create the base directory first
    (base / "src").mkdir()
    (base / "tests").mkdir()
    (base / "docs").mkdir()
    (base / ".git").mkdir() # Typically ignored
    (base / "src" / "main.py").write_text("print('hello')", encoding='utf-8')
    (base / "src" / "utils.py").write_text("def helper(): pass", encoding='utf-8')
    (base / "tests" / "test_main.py").write_text("assert True", encoding='utf-8')
    (base / "docs" / "readme.md").write_text("# Project", encoding='utf-8')
    (base / "ignored_file.tmp").touch()
    (base / ".hidden_dir").mkdir()
    (base / ".hidden_dir" / "secret.txt").touch()
    # Set known modification times (optional, makes tests more deterministic)
    # 既知の更新時刻を設定する（オプション、テストの決定性を高める）
    # os.utime(base / "src" / "main.py", (1678886400, 1678886400)) # Example timestamp
    return base

@pytest.fixture
def accessor() -> FileSystemAccessor:
    # PathResolver itself doesn't have state, so we can instantiate it directly
    # PathResolver自体は状態を持たないので、直接インスタンス化できる
    return FileSystemAccessor(PathResolver())

# --- Tests for read_file --- #

def test_read_file_success(setup_test_directory: Path, accessor: FileSystemAccessor):
    """
    Tests reading an existing file successfully.
    既存のファイルを正常に読み取るテスト。
    """
    file_path = setup_test_directory / "src" / "main.py"
    content = accessor.read_file(file_path)
    assert content == "print('hello')"

def test_read_file_not_found(setup_test_directory: Path, accessor: FileSystemAccessor):
    """
    Tests reading a non-existent file, expecting FileNotFoundError.
    存在しないファイルを読み取り、FileNotFoundErrorを期待するテスト。
    """
    file_path = setup_test_directory / "non_existent.txt"
    with pytest.raises(FileSystemError, match="File not found"):
        accessor.read_file(file_path)

def test_read_file_io_error(setup_test_directory: Path, accessor: FileSystemAccessor):
    """
    Tests reading a directory as a file, expecting an IOError (or similar OS-specific error).
    ディレクトリをファイルとして読み取り、IOError（または類似のOS固有エラー）を期待するテスト。
    """
    dir_path = setup_test_directory / "src"
    # The specific exception might vary (e.g., IsADirectoryError on Linux, PermissionError on Windows)
    # 具体的な例外は異なる場合がある（例: LinuxではIsADirectoryError、WindowsではPermissionError）
    # We expect *some* kind of IOError or OSError during the open/read attempt.
    # open/read試行中に *何らかの* IOErrorまたはOSErrorが発生することを期待する。
    with pytest.raises(FileSystemError, match="Error reading file.*?Permission denied"):
        accessor.read_file(dir_path)

# --- Tests for read_file (Error Handling) ---

@patch("builtins.open", new_callable=mock_open)
def test_read_file_unexpected_error(mock_file, setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests that FileSystemError is raised for unexpected errors during read."""
    file_path = setup_test_directory / "src" / "main.py"
    # Simulate an unexpected error (e.g., a custom exception or maybe MemoryError)
    mock_file.side_effect = RuntimeError("Something really unexpected happened")

    with pytest.raises(FileSystemError, match="Unexpected error reading file"):
        accessor.read_file(file_path)

    assert f"Unexpected error reading file {file_path.resolve()}" in caplog.text
    assert "RuntimeError: Something really unexpected happened" in caplog.text # Check original error

# --- Tests for scan_directory --- #

def test_scan_directory_no_ignore(setup_test_directory: Path, accessor: FileSystemAccessor):
    """
    Tests scanning a directory without any ignore function.
    無視関数なしでディレクトリをスキャンするテスト。
    """
    found_files = list(accessor.scan_directory(setup_test_directory))
    found_paths = {f.path.relative_to(setup_test_directory).as_posix() for f in found_files}

    expected_paths = {
        "src/main.py",
        "src/utils.py",
        "tests/test_main.py",
        "docs/readme.md",
        "ignored_file.tmp",
        ".hidden_dir/secret.txt",
    }
    assert found_paths == expected_paths
    assert len(found_files) == len(expected_paths)
    # Check if FileInfo objects have correct attributes (basic check)
    # FileInfoオブジェクトが正しい属性を持っているか確認（基本チェック）
    for file_info in found_files:
        assert isinstance(file_info, FileInfo)
        assert file_info.path.is_absolute()
        assert file_info.path.exists()
        assert isinstance(file_info.mtime, datetime.datetime)
        assert isinstance(file_info.size, int)
        assert file_info.size >= 0

def test_scan_directory_with_ignore_func(setup_test_directory: Path, accessor: FileSystemAccessor):
    """
    Tests scanning with a function that ignores specific patterns (like .git, .tmp).
    特定のパターン（.git、.tmpなど）を無視する関数でスキャンするテスト。
    """
    def ignore_rule(path: Path) -> bool:
        # Simple ignore: .git dir, .tmp files, hidden dirs/files starting with '.'
        # 簡単な無視: .gitディレクトリ、.tmpファイル、'.'で始まる隠しディレクトリ/ファイル
        return (
            ".git" in path.parts or
            path.name.endswith(".tmp") or
            any(part.startswith('.') for part in path.relative_to(setup_test_directory).parts if part != ".")
            # Ensure we don't ignore the base dir itself if it starts with '.'
            # ベースディレクトリ自体が '.' で始まる場合に無視しないようにする
        )

    found_files = list(accessor.scan_directory(setup_test_directory, ignore_func=ignore_rule))
    found_paths = {f.path.relative_to(setup_test_directory).as_posix() for f in found_files}

    expected_paths = {
        "src/main.py",
        "src/utils.py",
        "tests/test_main.py",
        "docs/readme.md",
    }
    assert found_paths == expected_paths
    assert len(found_files) == len(expected_paths)

def test_scan_directory_ignore_subdirectory(setup_test_directory: Path, accessor: FileSystemAccessor):
    """
    Tests scanning while ignoring an entire subdirectory.
    サブディレクトリ全体を無視してスキャンするテスト。
    """
    def ignore_tests_dir(path: Path) -> bool:
        # Ignore the 'tests' directory and everything inside it
        # 'tests' ディレクトリとその中のすべてを無視する
        return "tests" in path.relative_to(setup_test_directory).parts

    found_files = list(accessor.scan_directory(setup_test_directory, ignore_func=ignore_tests_dir))
    found_paths = {f.path.relative_to(setup_test_directory).as_posix() for f in found_files}

    expected_paths = {
        "src/main.py",
        "src/utils.py",
        "docs/readme.md",
        "ignored_file.tmp",
        ".hidden_dir/secret.txt", # Assuming ignore_tests_dir doesn't ignore hidden dirs
    }
    assert found_paths == expected_paths

def test_scan_non_existent_directory(accessor: FileSystemAccessor):
    """
    Tests scanning a non-existent directory.
    存在しないディレクトリをスキャンするテスト。
    """
    with pytest.raises(FileSystemError, match="Directory not found"):
        # Need to consume the iterator to trigger the exception
        # 例外をトリガーするにはイテレータを消費する必要があります
        list(accessor.scan_directory("./non_existent_dir_xyz"))

# --- Tests for scan_directory (Error Handling) ---

@patch("os.stat") # Patch os.stat instead of Path.stat
def test_scan_directory_stat_error(mock_os_stat, setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests that files causing OSError during stat are skipped and logged."""
    file_to_error = setup_test_directory / "src" / "main.py"
    file_ok = setup_test_directory / "src" / "utils.py"
    another_ok_file = setup_test_directory / "docs" / "readme.md"

    # Keep track of original os.stat if needed for non-mocked calls (though not strictly necessary here)
    # original_os_stat = os.stat

    def stat_side_effect(path, *args, **kwargs):
        # path argument will be a string here
        print(f"DEBUG: stat_side_effect called with path: {repr(path)} (type: {type(path)})", file=sys.stderr) # Debug log
        # Ensure comparison is string vs string
        if str(path) == str(file_to_error):
            print(f"DEBUG: Raising OSError for {path}", file=sys.stderr)
            raise OSError("Permission denied on stat")
        else:
            mock_stat_result = MagicMock()
            # Avoid Path(path).is_file() to prevent recursion
            # Determine if it's a file based on known test paths
            known_files = {str(file_ok), str(another_ok_file)}
            # Use str(path) for comparison here as well
            if str(path) in known_files:
                 # It's a known file
                 mock_stat_result.st_mode = 0o100644 # Regular file mode
                 mock_stat_result.st_size = 100
            else:
                 # Assume it's a directory otherwise (e.g., project_root, src, docs)
                 # This simplification works for this specific test setup
                 mock_stat_result.st_mode = 0o40755 # Directory mode
                 mock_stat_result.st_size = 4096

            mock_stat_result.st_mtime = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
            print(f"DEBUG: Returning mock os.stat for {path} (mode: {oct(mock_stat_result.st_mode)})", file=sys.stderr)
            return mock_stat_result

    mock_os_stat.side_effect = stat_side_effect

    with caplog.at_level(logging.WARNING):
        try:
            print("DEBUG: Starting scan_directory", file=sys.stderr)
            found_files = list(accessor.scan_directory(setup_test_directory))
            print(f"DEBUG: scan_directory finished. Found: {[f.path for f in found_files]}", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Error during scan_directory: {e}", file=sys.stderr)
            raise

    found_paths = {f.path for f in found_files}
    print(f"DEBUG: Found paths set: {found_paths}", file=sys.stderr)

    assert file_to_error not in found_paths, f"{file_to_error} should not be in found_paths"
    assert file_ok in found_paths, f"{file_ok} should be in found_paths"
    assert another_ok_file in found_paths, f"{another_ok_file} should be in found_paths"
    assert f"Could not access file info for {file_to_error}" in caplog.text, "Warning log for stat error not found"
    assert "Permission denied on stat" in caplog.text, "Original error message not in log"

# --- Tests for exists ---

def test_exists_true(setup_test_directory: Path, accessor: FileSystemAccessor):
    """Tests exists returns True for an existing file and directory."""
    assert accessor.exists(setup_test_directory / "src" / "main.py") is True
    assert accessor.exists(setup_test_directory / "src") is True

def test_exists_false(setup_test_directory: Path, accessor: FileSystemAccessor):
    """Tests exists returns False for a non-existent path."""
    assert accessor.exists(setup_test_directory / "non_existent.file") is False
    assert accessor.exists(setup_test_directory / "non_existent_dir" / "file") is False

# --- Tests for write_pickle ---

def test_write_pickle_success(setup_test_directory: Path, accessor: FileSystemAccessor):
    """Tests writing a pickle file successfully."""
    obj_to_pickle = {"a": 1, "b": [1, 2, 3]}
    relative_path = "cache/data.pkl"
    pickle_file = setup_test_directory / relative_path

    accessor.write_pickle(obj_to_pickle, relative_path, setup_test_directory)

    assert pickle_file.exists()
    # Verify content
    with open(pickle_file, 'rb') as f:
        loaded_obj = pickle.load(f)
    assert loaded_obj == obj_to_pickle

@patch("pickle.dump")
def test_write_pickle_pickling_error(mock_pickle_dump, setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests that IOError is raised if pickling fails."""
    obj_to_pickle = {"a": 1}
    relative_path = "cache/error.pkl"
    pickle_file = setup_test_directory / relative_path
    mock_pickle_dump.side_effect = pickle.PicklingError("Cannot pickle object")

    with pytest.raises(IOError, match="Failed to write cache file"):
        accessor.write_pickle(obj_to_pickle, relative_path, setup_test_directory)

    assert f"Error writing pickle file {pickle_file}" in caplog.text
    assert "Cannot pickle object" in caplog.text

@patch("builtins.open", new_callable=mock_open)
# Also mock mkdir to avoid interfering with the open mock
@patch("pathlib.Path.mkdir")
def test_write_pickle_io_error(mock_mkdir, mock_file, setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests that IOError is raised if file open/write fails."""
    obj_to_pickle = {"a": 1}
    relative_path = "cache/io_error.pkl"
    pickle_file = setup_test_directory / relative_path
    # Simulate IOError during open/write
    mock_file.side_effect = IOError("Disk full")

    with pytest.raises(IOError, match="Failed to write cache file"):
        accessor.write_pickle(obj_to_pickle, relative_path, setup_test_directory)

    assert f"Error writing pickle file {pickle_file}" in caplog.text
    assert "Disk full" in caplog.text
    # Check that mkdir was called to ensure the directory structure
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

# --- Tests for read_pickle ---

def test_read_pickle_success(setup_test_directory: Path, accessor: FileSystemAccessor):
    """Tests reading a valid pickle file."""
    obj_to_pickle = {"data": "test"}
    relative_path = "cache/valid.pkl"
    pickle_file = setup_test_directory / relative_path
    pickle_file.parent.mkdir(exist_ok=True)
    with open(pickle_file, 'wb') as f:
        pickle.dump(obj_to_pickle, f)

    loaded_obj = accessor.read_pickle(relative_path, setup_test_directory)
    assert loaded_obj == obj_to_pickle

def test_read_pickle_file_not_found(setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests reading a non-existent pickle file returns None."""
    relative_path = "cache/not_found.pkl"
    pickle_file = setup_test_directory / relative_path

    with caplog.at_level(logging.DEBUG):
        loaded_obj = accessor.read_pickle(relative_path, setup_test_directory)

    assert loaded_obj is None
    assert f"Pickle file not found: {pickle_file}" in caplog.text

@patch("builtins.open", new_callable=mock_open)
def test_read_pickle_io_error(mock_file, setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests IOError during pickle reading returns None."""
    relative_path = "cache/read_io_error.pkl"
    pickle_file = setup_test_directory / relative_path

    # Need to mock exists check first
    with patch.object(accessor, 'exists', return_value=True):
        # Simulate IOError when opening the file
        mock_file.side_effect = IOError("Cannot open file")
        with caplog.at_level(logging.WARNING):
             loaded_obj = accessor.read_pickle(relative_path, setup_test_directory)

    assert loaded_obj is None
    assert f"Error reading or unpickling file {pickle_file}" in caplog.text
    assert "Cannot open file" in caplog.text

@patch("pickle.load")
def test_read_pickle_unpickling_error(mock_pickle_load, setup_test_directory: Path, accessor: FileSystemAccessor, caplog):
    """Tests UnpicklingError during pickle reading returns None."""
    relative_path = "cache/corrupt.pkl"
    pickle_file = setup_test_directory / relative_path

    with patch.object(accessor, 'exists', return_value=True):
        # Simulate UnpicklingError
        mock_pickle_load.side_effect = pickle.UnpicklingError("Invalid pickle data")
        # Mock open to succeed
        with patch("builtins.open", new_callable=mock_open) as mock_file:
            with caplog.at_level(logging.WARNING):
                loaded_obj = accessor.read_pickle(relative_path, setup_test_directory)

    assert loaded_obj is None
    mock_file.assert_called_once_with(pickle_file, 'rb') # Check correct mode
    assert f"Error reading or unpickling file {pickle_file}" in caplog.text
    assert "Invalid pickle data" in caplog.text 