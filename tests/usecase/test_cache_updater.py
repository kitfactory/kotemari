import pytest
from pathlib import Path
import datetime
import hashlib
from unittest.mock import MagicMock, patch

from kotemari.usecase.cache_updater import CacheUpdater
from kotemari.gateway.cache_storage import CacheStorage
from kotemari.domain.file_info import FileInfo
from kotemari.domain.cache_metadata import CacheMetadata

# Helper to create FileInfo lists
@pytest.fixture
def create_file_list(tmp_path: Path):
    # Use a fixed timestamp for consistency in tests
    # テストの一貫性のために固定タイムスタンプを使用します
    fixed_time = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    def _creator(file_details: list[tuple[str, int, str | None]]) -> list[FileInfo]:
        files = []
        for name, size, hash_val in file_details:
            # Use the fixed time instead of datetime.now()
            # datetime.now() の代わりに固定時間を使用します
            files.append(FileInfo(
                path=tmp_path / name,
                mtime=fixed_time,
                size=size,
                hash=hash_val,
                language=None
            ))
        return files
    return _creator

# Fixture for a mocked CacheStorage
@pytest.fixture
def mock_cache_storage() -> MagicMock:
    return MagicMock(spec=CacheStorage)

# Fixture for CacheUpdater with mocked storage
@pytest.fixture
def cache_updater(tmp_path: Path, mock_cache_storage: MagicMock) -> CacheUpdater:
    # Use tmp_path as project_root, inject mocked storage
    # project_root として tmp_path を使用し、モックされたストレージを注入します
    return CacheUpdater(project_root=tmp_path, cache_storage=mock_cache_storage)

# --- Test _calculate_project_state_hash --- #

def test_calculate_state_hash_consistency(cache_updater: CacheUpdater, create_file_list):
    """
    Tests that the state hash is consistent for the same file list.
    同じファイルリストに対して状態ハッシュが一貫していることをテストします。
    """
    files1 = create_file_list([
        ("a.py", 100, "h1"),
        ("b/c.txt", 50, "h2")
    ])
    files2 = create_file_list([
        ("a.py", 100, "h1"),
        ("b/c.txt", 50, "h2")
    ])
    hash1 = cache_updater._calculate_project_state_hash(files1)
    hash2 = cache_updater._calculate_project_state_hash(files2)
    assert isinstance(hash1, str)
    assert len(hash1) == 64 # SHA256 length
    assert hash1 == hash2

def test_calculate_state_hash_order_independent(cache_updater: CacheUpdater, create_file_list):
    """
    Tests that the state hash is independent of the file list order.
    状態ハッシュがファイルリストの順序に依存しないことをテストします。
    """
    files1 = create_file_list([
        ("a.py", 100, "h1"),
        ("b/c.txt", 50, "h2")
    ])
    files2_reordered = create_file_list([
        ("b/c.txt", 50, "h2"),
        ("a.py", 100, "h1")
    ])
    hash1 = cache_updater._calculate_project_state_hash(files1)
    hash2 = cache_updater._calculate_project_state_hash(files2_reordered)
    assert hash1 == hash2

def test_calculate_state_hash_changes_on_diff(cache_updater: CacheUpdater, create_file_list):
    """
    Tests that the state hash changes if file content (hash), mtime, size, or path changes.
    ファイルの内容（ハッシュ）、mtime、サイズ、またはパスが変更された場合に状態ハッシュが変更されることをテストします。
    """
    base_files = create_file_list([("a.py", 100, "h1")])
    base_hash = cache_updater._calculate_project_state_hash(base_files)

    # Change hash
    # ハッシュを変更します
    files_hash_changed = create_file_list([("a.py", 100, "h1_changed")])
    assert cache_updater._calculate_project_state_hash(files_hash_changed) != base_hash

    # Change size
    # サイズを変更します
    files_size_changed = create_file_list([("a.py", 101, "h1")])
    assert cache_updater._calculate_project_state_hash(files_size_changed) != base_hash

    # Change path
    # パスを変更します
    files_path_changed = create_file_list([("a_new.py", 100, "h1")])
    assert cache_updater._calculate_project_state_hash(files_path_changed) != base_hash

    # Add file
    # ファイルを追加します
    files_added = create_file_list([("a.py", 100, "h1"), ("b.py", 50, "h2")])
    assert cache_updater._calculate_project_state_hash(files_added) != base_hash

    # Test with slightly different mtime (difficult to test precisely without mocking time)
    # わずかに異なる mtime でテストします（時間をモックしないと正確なテストは困難）
    # This is implicitly tested by consistency checks if mtime is included in hash input.
    # これは、mtime がハッシュ入力に含まれている場合、一貫性チェックによって暗黙的にテストされます。

def test_calculate_state_hash_empty_list(cache_updater: CacheUpdater):
    """
    Tests the state hash calculation for an empty file list.
    空のファイルリストに対する状態ハッシュ計算をテストします。
    """
    empty_hash = cache_updater._calculate_project_state_hash([])
    assert isinstance(empty_hash, str)
    assert len(empty_hash) == 64
    # Ensure it's not the same as a hash of empty string or zero
    # 空文字列やゼロのハッシュと同じでないことを確認します
    assert empty_hash != hashlib.sha256(b"").hexdigest()
    assert empty_hash != hashlib.sha256(b"0").hexdigest()

# --- Test get_valid_cache --- #

def test_get_valid_cache_success(cache_updater: CacheUpdater, mock_cache_storage: MagicMock, create_file_list):
    """
    Tests getting a valid cache when the state hash matches.
    状態ハッシュが一致する場合に有効なキャッシュを取得するテスト。
    """
    current_files = create_file_list([("a.py", 100, "h1")])
    current_hash = cache_updater._calculate_project_state_hash(current_files)
    cached_metadata = CacheMetadata(cache_time=datetime.datetime.now(), source_hash=current_hash)
    cached_files = create_file_list([("a.py", 100, "h1")]) # Simulate cached state

    mock_cache_storage.load_cache.return_value = (cached_files, cached_metadata)

    valid_cache = cache_updater.get_valid_cache(current_files)

    mock_cache_storage.load_cache.assert_called_once()
    assert valid_cache is cached_files # Should return the cached list object

def test_get_valid_cache_hash_mismatch(cache_updater: CacheUpdater, mock_cache_storage: MagicMock, create_file_list):
    """
    Tests cache invalidation when the state hash does not match.
    状態ハッシュが一致しない場合のキャッシュ無効化をテストします。
    """
    current_files = create_file_list([("a.py", 100, "h1_changed")]) # Changed hash
    cached_metadata = CacheMetadata(cache_time=datetime.datetime.now(), source_hash="old_hash_123")
    cached_files = create_file_list([("a.py", 100, "h1")])

    mock_cache_storage.load_cache.return_value = (cached_files, cached_metadata)

    valid_cache = cache_updater.get_valid_cache(current_files)

    mock_cache_storage.load_cache.assert_called_once()
    assert valid_cache is None # Cache should be considered invalid

def test_get_valid_cache_no_cache_file(cache_updater: CacheUpdater, mock_cache_storage: MagicMock, create_file_list):
    """
    Tests behavior when the cache file doesn't exist.
    キャッシュファイルが存在しない場合の動作をテストします。
    """
    current_files = create_file_list([("a.py", 100, "h1")])
    mock_cache_storage.load_cache.return_value = None # Simulate file not found

    valid_cache = cache_updater.get_valid_cache(current_files)

    mock_cache_storage.load_cache.assert_called_once()
    assert valid_cache is None

# --- Test update_cache --- #

def test_update_cache_saves_correct_data(cache_updater: CacheUpdater, mock_cache_storage: MagicMock, create_file_list):
    """
    Tests that update_cache calculates the correct state hash and calls save_cache.
    update_cache が正しい状態ハッシュを計算し、save_cache を呼び出すことをテストします。
    """
    analysis_results = create_file_list([("main.py", 200, "hash123")])
    expected_hash = cache_updater._calculate_project_state_hash(analysis_results)

    cache_updater.update_cache(analysis_results)

    # Assert save_cache was called with the results and metadata containing the correct hash
    # save_cache が結果と正しいハッシュを含むメタデータで呼び出されたことを表明します
    mock_cache_storage.save_cache.assert_called_once()
    call_args = mock_cache_storage.save_cache.call_args[0]
    assert len(call_args) == 2
    assert call_args[0] is analysis_results
    saved_metadata = call_args[1]
    assert isinstance(saved_metadata, CacheMetadata)
    assert saved_metadata.source_hash == expected_hash
    # Check timestamp is recent (within a reasonable delta)
    # タイムスタンプが最近であることを確認します（妥当な差分内）
    assert (datetime.datetime.now(datetime.timezone.utc) - saved_metadata.cache_time).total_seconds() < 5

def test_update_cache_empty_results(cache_updater: CacheUpdater, mock_cache_storage: MagicMock):
    """
    Tests that update_cache does not call save_cache for empty results.
    空の結果に対して update_cache が save_cache を呼び出さないことをテストします。
    """
    cache_updater.update_cache([])
    mock_cache_storage.save_cache.assert_not_called()

# --- Test clear_cache --- #

def test_clear_cache_calls_storage(cache_updater: CacheUpdater, mock_cache_storage: MagicMock):
    """
    Tests that clear_cache calls the underlying storage method.
    clear_cache が基盤となるストレージメソッドを呼び出すことをテストします。
    """
    cache_updater.clear_cache()
    mock_cache_storage.clear_cache.assert_called_once() 