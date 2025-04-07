import pytest
from pathlib import Path
import pickle
import datetime
import os

from kotemari.gateway.cache_storage import CacheStorage, DEFAULT_CACHE_DIR_NAME, DEFAULT_CACHE_FILE_NAME
from kotemari.domain.file_info import FileInfo
from kotemari.domain.cache_metadata import CacheMetadata

# Helper function to create dummy FileInfo and CacheMetadata
@pytest.fixture
def dummy_cache_data(tmp_path: Path):
    now = datetime.datetime.now(datetime.timezone.utc)
    files = [
        FileInfo(path=tmp_path / "file1.py", mtime=now, size=100, hash="h1", language="Python"),
        FileInfo(path=tmp_path / "data" / "file2.txt", mtime=now, size=50, hash="h2", language="Text"),
    ]
    metadata = CacheMetadata(
        cache_time=now - datetime.timedelta(minutes=5),
        source_hash="state_hash_123"
    )
    return files, metadata

# Fixture for CacheStorage instance pointing to tmp_path
@pytest.fixture
def cache_storage(tmp_path: Path) -> CacheStorage:
    # Use tmp_path directly as the "project root" for cache location
    # キャッシュ場所の「プロジェクトルート」として tmp_path を直接使用します
    return CacheStorage(tmp_path)

# --- Test Initialization --- #

def test_cache_storage_init(tmp_path: Path):
    """
    Tests CacheStorage initialization sets the correct cache path.
    CacheStorage の初期化が正しいキャッシュパスを設定するかをテストします。
    """
    storage = CacheStorage(tmp_path)
    expected_cache_dir = tmp_path.resolve() / DEFAULT_CACHE_DIR_NAME
    expected_cache_file = expected_cache_dir / DEFAULT_CACHE_FILE_NAME
    assert storage.cache_dir == expected_cache_dir
    assert storage.cache_file == expected_cache_file

# --- Test _ensure_cache_dir_exists --- #

def test_ensure_cache_dir_exists_creates_dir(cache_storage: CacheStorage):
    """
    Tests that the cache directory is created if it doesn't exist.
    キャッシュディレクトリが存在しない場合に作成されることをテストします。
    """
    assert not cache_storage.cache_dir.exists()
    cache_storage._ensure_cache_dir_exists()
    assert cache_storage.cache_dir.is_dir()

def test_ensure_cache_dir_exists_already_exists(cache_storage: CacheStorage):
    """
    Tests that no error occurs if the cache directory already exists.
    キャッシュディレクトリが既に存在する場合にエラーが発生しないことをテストします。
    """
    cache_storage.cache_dir.mkdir()
    assert cache_storage.cache_dir.is_dir()
    cache_storage._ensure_cache_dir_exists() # Should not raise error
    assert cache_storage.cache_dir.is_dir()

# --- Test save_cache --- #

def test_save_cache_creates_file(cache_storage: CacheStorage, dummy_cache_data):
    """
    Tests that save_cache successfully creates the cache file with correct data.
    save_cache が正しいデータでキャッシュファイルを正常に作成することをテストします。
    """
    files, metadata = dummy_cache_data
    assert not cache_storage.cache_file.exists()
    cache_storage.save_cache(files, metadata)
    assert cache_storage.cache_file.is_file()

    # Verify content by loading it back using pickle directly
    # pickle を直接使用して再度読み込むことで内容を確認します
    with cache_storage.cache_file.open('rb') as f:
        loaded_data = pickle.load(f)

    assert isinstance(loaded_data, tuple)
    assert len(loaded_data) == 2
    loaded_files, loaded_metadata = loaded_data
    assert loaded_files == files # Check dataclass equality
    assert loaded_metadata == metadata

# --- Test load_cache --- #

def test_load_cache_success(cache_storage: CacheStorage, dummy_cache_data):
    """
    Tests loading a valid cache file created by save_cache.
    save_cache によって作成された有効なキャッシュファイルの読み込みをテストします。
    """
    files, metadata = dummy_cache_data
    cache_storage.save_cache(files, metadata) # Save it first

    loaded_result = cache_storage.load_cache()
    assert loaded_result is not None
    loaded_files, loaded_metadata = loaded_result
    assert loaded_files == files
    assert loaded_metadata == metadata

def test_load_cache_file_not_found(cache_storage: CacheStorage):
    """
    Tests loading when the cache file does not exist.
    キャッシュファイルが存在しない場合の読み込みをテストします。
    """
    assert not cache_storage.cache_file.exists()
    loaded_result = cache_storage.load_cache()
    assert loaded_result is None

def test_load_cache_corrupted_file(cache_storage: CacheStorage):
    """
    Tests loading a corrupted or invalid pickle file.
    破損した、または無効な pickle ファイルの読み込みをテストします。
    """
    cache_storage._ensure_cache_dir_exists()
    cache_storage.cache_file.write_text("this is not pickle data", encoding='utf-8')

    loaded_result = cache_storage.load_cache()
    assert loaded_result is None
    # Check if the corrupted file was deleted
    # 破損したファイルが削除されたか確認します
    assert not cache_storage.cache_file.exists()

def test_load_cache_invalid_format(cache_storage: CacheStorage):
    """
    Tests loading a file with valid pickle data but incorrect format (not tuple).
    有効な pickle データだが形式が正しくない（タプルではない）ファイルの読み込みをテストします。
    """
    cache_storage._ensure_cache_dir_exists()
    invalid_data = ["just", "a", "list"]
    with cache_storage.cache_file.open('wb') as f:
        pickle.dump(invalid_data, f)

    loaded_result = cache_storage.load_cache()
    assert loaded_result is None
    assert not cache_storage.cache_file.exists() # Should be cleared

# --- Test clear_cache --- #

def test_clear_cache_deletes_file(cache_storage: CacheStorage, dummy_cache_data):
    """
    Tests that clear_cache deletes an existing cache file.
    clear_cache が既存のキャッシュファイルを削除することをテストします。
    """
    files, metadata = dummy_cache_data
    cache_storage.save_cache(files, metadata)
    assert cache_storage.cache_file.is_file()

    result = cache_storage.clear_cache()
    assert result is True
    assert not cache_storage.cache_file.exists()

def test_clear_cache_file_not_found(cache_storage: CacheStorage):
    """
    Tests that clear_cache handles non-existent cache file gracefully.
    clear_cache が存在しないキャッシュファイルを正常に処理することをテストします。
    """
    assert not cache_storage.cache_file.exists()
    result = cache_storage.clear_cache()
    assert result is True # Success even if not found 