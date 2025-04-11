import pytest
from pathlib import Path
import pathspec
from unittest.mock import patch, mock_open, MagicMock
import io

from kotemari.gateway.gitignore_reader import GitignoreReader

# Fixture to create temporary .gitignore files
@pytest.fixture
def setup_gitignore_files(tmp_path: Path):
    # Structure:
    # tmp_path/
    #   .gitignore (root)
    #   project/
    #     .gitignore (project)
    #     subdir/
    #       file.txt
    #       ignored_by_proj.dat
    #     another.py
    #     ignored_by_root.log
    #   outer_file.txt

    root_ignore = tmp_path / ".gitignore"
    root_ignore.write_text("*.log\n/outer_file.txt\n", encoding='utf-8')

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_ignore = project_dir / ".gitignore"
    project_ignore.write_text("*.dat\n/subdir/another_ignored.tmp\n", encoding='utf-8')

    subdir = project_dir / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").touch()
    (subdir / "ignored_by_proj.dat").touch()
    (subdir / "another_ignored.tmp").touch()

    (project_dir / "another.py").touch()
    (project_dir / "ignored_by_root.log").touch()

    (tmp_path / "outer_file.txt").touch()
    (tmp_path / "not_ignored.txt").touch()

    return {
        "root": tmp_path,
        "project": project_dir,
        "subdir": subdir,
        "root_ignore": root_ignore,
        "project_ignore": project_ignore
    }

# --- Tests for read --- #

def test_read_gitignore_success(setup_gitignore_files):
    """
    Tests reading an existing, non-empty .gitignore file.
    既存の空でない .gitignore ファイルの読み取りをテストします。
    """
    spec = GitignoreReader.read(setup_gitignore_files["root_ignore"])
    assert isinstance(spec, pathspec.PathSpec)
    # Test a pattern from the file
    # ファイルからのパターンをテストします
    assert spec.match_file("some.log")
    assert spec.match_file("outer_file.txt") # Matches file in the same dir
    assert not spec.match_file("project/outer_file.txt") # Does not match file in subdir
    assert not spec.match_file("some.txt")

def test_read_gitignore_not_found(tmp_path: Path):
    """
    Tests reading a non-existent .gitignore file.
    存在しない .gitignore ファイルの読み取りをテストします。
    """
    spec = GitignoreReader.read(tmp_path / ".nonexistent_ignore")
    assert spec is None

def test_read_gitignore_empty(tmp_path: Path):
    """
    Tests reading an empty .gitignore file.
    空の .gitignore ファイルの読み取りをテストします。
    """
    empty_ignore = tmp_path / ".empty_ignore"
    empty_ignore.touch()
    spec = GitignoreReader.read(empty_ignore)
    assert spec is None

def test_read_gitignore_only_comments(tmp_path: Path):
    """
    Tests reading a .gitignore file containing only comments and blank lines.
    コメントと空行のみを含む .gitignore ファイルの読み取りをテストします。
    """
    comment_ignore = tmp_path / ".comment_ignore"
    comment_ignore.write_text("# This is a comment\n\n   # Another comment \n", encoding='utf-8')
    spec = GitignoreReader.read(comment_ignore)
    assert spec is None

# --- Tests for find_and_read_all --- #

def test_find_and_read_all_finds_both(setup_gitignore_files):
    """
    Tests finding .gitignore files from a subdirectory upwards.
    サブディレクトリから上方向に .gitignore ファイルを検索するテスト。
    """
    specs = GitignoreReader.find_and_read_all(setup_gitignore_files["subdir"])
    assert len(specs) == 2 # Should find project and root .gitignore
    # The order should be deepest first (project, then root)
    # 順序は最も深いものが最初（プロジェクト、次にルート）である必要があります
    project_spec = specs[0]
    root_spec = specs[1]

    assert isinstance(project_spec, pathspec.PathSpec)
    assert isinstance(root_spec, pathspec.PathSpec)

    # Check patterns specific to each file
    # 各ファイルに固有のパターンを確認します
    assert project_spec.match_file("ignored_by_proj.dat")
    assert not project_spec.match_file("ignored_by_root.log")
    assert root_spec.match_file("ignored_by_root.log")
    assert not root_spec.match_file("ignored_by_proj.dat")

def test_find_and_read_all_start_from_root(setup_gitignore_files):
    """
    Tests finding .gitignore starting from the root directory.
    ルートディレクトリから開始して .gitignore を検索するテスト。
    """
    specs = GitignoreReader.find_and_read_all(setup_gitignore_files["root"])
    assert len(specs) == 1 # Should only find the root .gitignore
    assert isinstance(specs[0], pathspec.PathSpec)
    assert specs[0].match_file("some.log")

def test_find_and_read_all_no_gitignore(tmp_path: Path):
    """
    Tests searching in a directory hierarchy with no .gitignore files.
    .gitignore ファイルがないディレクトリ階層を検索するテスト。
    """
    (tmp_path / "subdir").mkdir()
    specs = GitignoreReader.find_and_read_all(tmp_path / "subdir")
    assert len(specs) == 0

# --- Tests for find_gitignore_files (Instance Method) ---

def test_find_gitignore_files_finds_hierarchy(setup_gitignore_files):
    """Tests finding .gitignore files up the hierarchy using the instance method."""
    reader = GitignoreReader(project_root=setup_gitignore_files["project"])
    # Start from project dir, should find project and root .gitignore
    # プロジェクトディレクトリから開始し、プロジェクトとルートの .gitignore を見つけるはず
    found_files = reader.find_gitignore_files()
    assert sorted(found_files) == sorted([
        setup_gitignore_files["project_ignore"],
        setup_gitignore_files["root_ignore"]
    ])

def test_find_gitignore_files_finds_git_info_exclude(setup_gitignore_files, tmp_path):
    """Tests finding .git/info/exclude using the instance method."""
    project_root = setup_gitignore_files["project"]
    git_dir = project_root / ".git"
    git_dir.mkdir()
    info_dir = git_dir / "info"
    info_dir.mkdir()
    exclude_file = info_dir / "exclude"
    exclude_file.write_text("*.tmp\n", encoding='utf-8')

    reader = GitignoreReader(project_root=project_root)
    found_files = reader.find_gitignore_files()

    assert sorted(found_files) == sorted([
        setup_gitignore_files["project_ignore"],
        setup_gitignore_files["root_ignore"],
        exclude_file
    ])

def test_find_gitignore_files_no_files(tmp_path: Path):
    """Tests find_gitignore_files when no .gitignore files exist."""
    project_root = tmp_path / "empty_project"
    project_root.mkdir()
    reader = GitignoreReader(project_root=project_root)
    found_files = reader.find_gitignore_files()
    assert found_files == []

# test_find_gitignore_files_stops_at_root は環境依存性が高く、
# 安定したテストを作成するのが難しいため、ここでは省略します。
# while ループの基本的な停止条件は他のテストで間接的にカバーされます。

# --- Tests for read_gitignore_patterns ---

def test_read_gitignore_patterns_success(setup_gitignore_files):
    """Tests reading patterns successfully."""
    patterns = GitignoreReader.read_gitignore_patterns(setup_gitignore_files["root_ignore"])
    assert patterns == ["*.log", "/outer_file.txt"]

def test_read_gitignore_patterns_not_a_file(tmp_path, caplog):
    """Tests reading patterns from a path that is not a file."""
    non_file_path = tmp_path / "not_a_file.txt" # Does not exist
    patterns = GitignoreReader.read_gitignore_patterns(non_file_path)
    assert patterns == []
    assert f"Attempted to read non-existent gitignore file: {non_file_path}" in caplog.text

    dir_path = tmp_path / "a_directory"
    dir_path.mkdir()
    patterns_dir = GitignoreReader.read_gitignore_patterns(dir_path)
    assert patterns_dir == []
    assert f"Attempted to read non-existent gitignore file: {dir_path}" in caplog.text


@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.open")
def test_read_gitignore_patterns_io_error(mock_path_open, mock_is_file, tmp_path, caplog):
    """Tests IOError handling during pattern reading."""
    gitignore_path = tmp_path / "error.gitignore"
    # Mock the file handle returned by Path.open to raise IOError on iteration
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value = mock_file_handle # For context manager
    # Raise error when iterating over the file handle
    mock_file_handle.__iter__.side_effect = IOError("Disk read error")

    mock_path_open.return_value = mock_file_handle # Path.open returns our mocked handle

    patterns = GitignoreReader.read_gitignore_patterns(gitignore_path)
    assert patterns == []
    assert f"Error reading gitignore file {gitignore_path}: Disk read error" in caplog.text
    mock_is_file.assert_called_once()
    mock_path_open.assert_called_once_with('r', encoding='utf-8')


@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.open")
def test_read_gitignore_patterns_encoding_error(mock_path_open, mock_is_file, tmp_path, caplog):
    """Tests UnicodeDecodeError handling during pattern reading."""
    gitignore_path = tmp_path / "encoding_error.gitignore"
    # Mock the file handle to raise UnicodeDecodeError on iteration
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value = mock_file_handle
    # Simulate error during iteration
    mock_file_handle.__iter__.side_effect = UnicodeDecodeError("utf-8", b"invalid\\xff", 0, 1, "invalid start byte")

    mock_path_open.return_value = mock_file_handle

    patterns = GitignoreReader.read_gitignore_patterns(gitignore_path)
    assert patterns == []
    assert f"Encoding error reading gitignore file {gitignore_path}" in caplog.text
    assert "invalid start byte" in caplog.text # More specific check
    mock_is_file.assert_called_once()
    mock_path_open.assert_called_once_with('r', encoding='utf-8')

# --- Tests for read (Error Handling) ---

@patch("pathlib.Path.is_file", return_value=True)
@patch("pathlib.Path.open") # Patch Path.open
@patch("pathspec.PathSpec.from_lines")
def test_read_exception_handling(mock_from_lines, mock_path_open, mock_is_file, tmp_path, caplog):
    """Tests generic exception handling during read (e.g., pathspec error)."""
    gitignore_path = tmp_path / "compile_error.gitignore"

    # Mock Path.open to return a handle that simulates successful readlines
    mock_file_handle = MagicMock()
    mock_file_handle.__enter__.return_value = mock_file_handle
    mock_file_handle.readlines.return_value = ["*.py\n", "# comment\n", " "]
    mock_path_open.return_value = mock_file_handle

    # Simulate an error during pathspec compilation
    mock_from_lines.side_effect = ValueError("Invalid pattern")

    spec = GitignoreReader.read(gitignore_path)
    assert spec is None
    assert f"Error reading or parsing .gitignore file at {gitignore_path}" in caplog.text
    # Check that the original ValueError is mentioned in the log (due to exc_info=True)
    assert "ValueError: Invalid pattern" in caplog.text
    mock_is_file.assert_called_once()
    mock_path_open.assert_called_once_with('r', encoding='utf-8')
    mock_file_handle.readlines.assert_called_once()
    mock_from_lines.assert_called_once_with('gitwildmatch', ["*.py"]) # Ensure only valid patterns are passed 