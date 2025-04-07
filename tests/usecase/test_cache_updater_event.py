import pytest
from pathlib import Path
from unittest.mock import MagicMock, call
from typing import Tuple

from kotemari.domain.file_system_event import FileSystemEvent, FileSystemEventType
from kotemari.usecase.cache_updater import CacheUpdater
from kotemari.gateway.cache_storage import CacheStorage

@pytest.fixture
def cache_updater_with_mock_storage(tmp_path: Path, mocker) -> Tuple[CacheUpdater, MagicMock]:
    """Fixture to provide CacheUpdater with mocked CacheStorage."""
    # """モックされた CacheStorage を持つ CacheUpdater を提供するフィクスチャ。"""
    project_root = tmp_path
    mock_storage = mocker.MagicMock(spec=CacheStorage)
    updater = CacheUpdater(project_root, cache_storage=mock_storage)
    return updater, mock_storage

# Define some common event properties
# いくつかの共通イベントプロパティを定義します
TEST_FILE_PATH = Path("src/some_file.py")
TEST_DIR_PATH = Path("src/some_dir")

@pytest.mark.parametrize("event_type", ["created", "modified", "deleted"])
def test_invalidate_on_file_event(cache_updater_with_mock_storage, event_type: FileSystemEventType):
    """Test cache invalidation on file create, modify, delete events."""
    # """ファイルの作成、変更、削除イベント時のキャッシュ無効化をテストします。"""
    updater, mock_storage = cache_updater_with_mock_storage
    event = FileSystemEvent(
        event_type=event_type,
        src_path=updater.project_root / TEST_FILE_PATH,
        is_directory=False
    )

    updater.invalidate_cache_on_event(event)

    # Check that clear_cache was called for both analysis and context
    # analysis と context の両方で clear_cache が呼び出されたことを確認します
    expected_calls = [
        call(target="analysis"),
        call(target="context")
    ]
    mock_storage.clear_cache.assert_has_calls(expected_calls, any_order=True)
    assert mock_storage.clear_cache.call_count == 2

def test_invalidate_on_file_move_event(cache_updater_with_mock_storage):
    """Test cache invalidation on file move event."""
    # """ファイル移動イベント時のキャッシュ無効化をテストします。"""
    updater, mock_storage = cache_updater_with_mock_storage
    event = FileSystemEvent(
        event_type="moved",
        src_path=updater.project_root / "src/old_name.py",
        is_directory=False,
        dest_path=updater.project_root / "src/new_name.py"
    )

    updater.invalidate_cache_on_event(event)

    # Check calls are the same as other events
    # 呼び出しが他のイベントと同じであることを確認します
    expected_calls = [
        call(target="analysis"),
        call(target="context")
    ]
    mock_storage.clear_cache.assert_has_calls(expected_calls, any_order=True)
    assert mock_storage.clear_cache.call_count == 2


@pytest.mark.parametrize("event_type", ["created", "deleted"])
def test_invalidate_on_dir_event(cache_updater_with_mock_storage, event_type: FileSystemEventType):
    """Test cache invalidation on directory create, delete events."""
    # """ディレクトリの作成、削除イベント時のキャッシュ無効化をテストします。"""
    updater, mock_storage = cache_updater_with_mock_storage
    event = FileSystemEvent(
        event_type=event_type,
        src_path=updater.project_root / TEST_DIR_PATH,
        is_directory=True
    )

    updater.invalidate_cache_on_event(event)

    # Check calls are the same
    # 呼び出しが同じであることを確認します
    expected_calls = [
        call(target="analysis"),
        call(target="context")
    ]
    mock_storage.clear_cache.assert_has_calls(expected_calls, any_order=True)
    assert mock_storage.clear_cache.call_count == 2

def test_invalidate_handles_filenotfound(cache_updater_with_mock_storage, mocker):
    """Test that FileNotFoundError during context clear is handled gracefully."""
    # """コンテキストクリア中の FileNotFoundError が適切に処理されることをテストします。"""
    updater, mock_storage = cache_updater_with_mock_storage

    # Configure mock to raise FileNotFoundError only for context target
    # context ターゲットに対してのみ FileNotFoundError を発生させるようにモックを設定します
    def clear_cache_side_effect(target):
        if target == "context":
            raise FileNotFoundError("Context cache not found")
        else:
            # For 'analysis' or 'all', return normally (or MagicMock default)
            # 'analysis' または 'all' の場合、通常通り返します（または MagicMock のデフォルト）
            return MagicMock()

    mock_storage.clear_cache.side_effect = clear_cache_side_effect

    event = FileSystemEvent(
        event_type="modified",
        src_path=updater.project_root / TEST_FILE_PATH,
        is_directory=False
    )

    # Should not raise an exception
    # 例外を発生させないはずです
    updater.invalidate_cache_on_event(event)

    # Check that clear_cache was still called for analysis and context
    # analysis と context の両方で clear_cache が呼び出されたことを確認します
    expected_calls = [
        call(target="analysis"),
        call(target="context")
    ]
    mock_storage.clear_cache.assert_has_calls(expected_calls, any_order=True)
    assert mock_storage.clear_cache.call_count == 2 