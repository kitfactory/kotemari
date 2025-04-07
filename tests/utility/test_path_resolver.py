import pytest
from pathlib import Path
import os

# Import the class to be tested relative to the 'src' directory
# If your tests are outside 'src', you might need to adjust sys.path or use a different import strategy.
# テスト対象のクラスを 'src' ディレクトリからの相対パスでインポートします。
# テストが 'src' の外にある場合、sys.path の調整や別のインポート戦略が必要になることがあります。
# Assuming tests run from the project root where 'src' is a subdirectory.
# テストがプロジェクトルートから実行され、'src' がサブディレクトリであると仮定します。
from kotemari.utility.path_resolver import PathResolver

# Helper function to create dummy files/dirs for testing resolve_absolute
# resolve_absolute テスト用のダミーファイル/ディレクトリを作成するヘルパー関数
def create_dummy_structure(base_path: Path):
    (base_path / "subdir").mkdir(parents=True, exist_ok=True)
    (base_path / "subdir" / "file.txt").touch()
    (base_path / "another_file.log").touch()

@pytest.fixture
def dummy_fs(tmp_path: Path) -> Path:
    create_dummy_structure(tmp_path)
    return tmp_path

# --- Tests for normalize --- #

@pytest.mark.parametrize(
    "input_path, expected_path_str",
    [
        ("foo/bar", "foo/bar"),
        ("foo\\bar", "foo/bar"), # Windows style path
        ("foo/./bar", "foo/bar"),
        ("foo/../bar", "bar"),
        ("./foo", "foo"),
        ("../foo", "../foo"), # Cannot go above root implicitly
        ("foo/.", "foo"),
        ("foo/..", "."), # Represents current dir
        (Path("foo/bar"), "foo/bar"),
        ("/foo/bar", "/foo/bar"), # Absolute path (Unix style)
        ("C:/foo/bar", "C:/foo/bar"), # Absolute path (Windows style)
        ("C:\\foo\\bar", "C:/foo/bar"), # Absolute path (Windows style mixed)
        ("C:/foo/./../bar", "C:/bar"),
    ]
)
def test_normalize(input_path: Path | str, expected_path_str: str):
    """
    Tests the normalize static method with various path formats.
    normalize 静的メソッドを様々なパス形式でテストします。
    """
    normalized = PathResolver.normalize(input_path)
    # Compare as strings after converting expected to Path and back to str with forward slashes
    # 期待値をPathに変換し、スラッシュ区切りで文字列に戻してから文字列として比較します
    expected_path = Path(expected_path_str)
    assert str(normalized.as_posix()) == str(expected_path.as_posix())
    assert isinstance(normalized, Path)

# --- Tests for resolve_absolute --- #

# Note: These tests depend on the current working directory or tmp_path fixture.
# 注意: これらのテストは現在の作業ディレクトリまたはtmp_pathフィクスチャに依存します。

def test_resolve_absolute_relative_path_no_base(dummy_fs: Path):
    """
    Tests resolving a relative path without a base_dir (should use cwd).
    base_dirなしで相対パスを解決するテスト (cwdを使用するはず)。
    """
    # We need to change CWD to the temp dir for this test
    # このテストのためにCWDを一時ディレクトリに変更する必要があります
    original_cwd = Path.cwd()
    os.chdir(dummy_fs)
    try:
        resolved = PathResolver.resolve_absolute("subdir/file.txt")
        expected = (dummy_fs / "subdir" / "file.txt").resolve()
        assert resolved == PathResolver.normalize(expected)
        assert resolved.is_absolute()
    finally:
        os.chdir(original_cwd)

def test_resolve_absolute_relative_path_with_base(dummy_fs: Path):
    """
    Tests resolving a relative path with a base_dir.
    base_dir付きで相対パスを解決するテスト。
    """
    resolved = PathResolver.resolve_absolute("file.txt", base_dir=dummy_fs / "subdir")
    expected = (dummy_fs / "subdir" / "file.txt").resolve()
    assert resolved == PathResolver.normalize(expected)
    assert resolved.is_absolute()

def test_resolve_absolute_absolute_path(dummy_fs: Path):
    """
    Tests resolving an already absolute path.
    既に絶対パスであるパスを解決するテスト。
    """
    abs_path_obj = (dummy_fs / "another_file.log").resolve()
    resolved = PathResolver.resolve_absolute(abs_path_obj)
    # Should just normalize the absolute path
    # 絶対パスを正規化するだけのはず
    assert resolved == PathResolver.normalize(abs_path_obj)
    assert resolved.is_absolute()

def test_resolve_absolute_with_dot_dot(dummy_fs: Path):
    """
    Tests resolving a path containing '..' components.
    '..' コンポーネントを含むパスを解決するテスト。
    """
    resolved = PathResolver.resolve_absolute("../another_file.log", base_dir=dummy_fs / "subdir")
    expected = (dummy_fs / "another_file.log").resolve()
    assert resolved == PathResolver.normalize(expected)
    assert resolved.is_absolute()

def test_resolve_absolute_nonexistent_base_dir():
    """
    Tests resolving with a non-existent base_dir (should still work based on cwd if path is relative).
    存在しないbase_dirで解決するテスト (パスが相対ならcwdに基づいて動作するはず)。
    Note: This behavior depends on Path.resolve() logic.
    注意: この動作は Path.resolve() のロジックに依存します。
    """
    # This test might be less robust depending on the exact CWD state
    # このテストは正確なCWDの状態によっては堅牢性が低いかもしれません
    non_existent_base = Path("./non_existent_dir_12345")
    relative_path = "some_file.txt"
    resolved = PathResolver.resolve_absolute(relative_path, base_dir=non_existent_base)
    # Instead, construct the expected absolute path without calling resolve() on the final part
    # resolve() を final part で呼び出さずに期待される絶対パスを構築する
    # expected_absolute = Path.cwd().resolve() / relative_path # Old incorrect expectation
    expected_absolute = (Path.cwd() / non_existent_base).resolve() / relative_path
    assert resolved == PathResolver.normalize(expected_absolute)
    assert resolved.is_absolute() 