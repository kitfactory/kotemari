import pytest
from pathlib import Path
import datetime
import os

from kotemari.utility.path_resolver import PathResolver
from kotemari.gateway.file_system_accessor import FileSystemAccessor
from kotemari.domain.file_info import FileInfo

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
    with pytest.raises(FileNotFoundError):
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
    with pytest.raises((IOError, OSError)):
        accessor.read_file(dir_path)

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
    with pytest.raises(FileNotFoundError):
        list(accessor.scan_directory("./non_existent_dir_xyz")) 