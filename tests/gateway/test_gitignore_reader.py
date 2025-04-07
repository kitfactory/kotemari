import pytest
from pathlib import Path
import pathspec

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