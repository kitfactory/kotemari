import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

from kotemari.core import Kotemari
from kotemari.domain.file_system_event import FileSystemEvent
from kotemari.service.file_system_event_monitor import FileSystemEventMonitor, FileSystemEventCallback
from kotemari.usecase.cache_updater import CacheUpdater

# Use a real path for the test project root
# テストプロジェクトルートには実際のパスを使用します
@pytest.fixture
def test_project_path(tmp_path: Path) -> Path:
    project_dir = tmp_path / "watch_project"
    project_dir.mkdir()
    (project_dir / "file1.txt").write_text("content1")
    return project_dir

@pytest.fixture
def kotemari_instance(test_project_path: Path) -> Kotemari:
    """Fixture to provide a Kotemari instance for testing watching."""
    # """監視テスト用の Kotemari インスタンスを提供するフィクスチャ。"""
    # Enable cache for watching tests
    # 監視テストのためにキャッシュを有効にします
    return Kotemari(project_root=test_project_path, use_cache=True)

# --- Test Cases --- #

@patch("kotemari.core.FileSystemEventMonitor") # Patch the class in the core module
def test_start_watching_initializes_and_starts_monitor(MockMonitor, kotemari_instance: Kotemari):
    """Test that start_watching initializes and starts the monitor."""
    # """start_watching がモニターを初期化して開始することをテストします。"""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = False

    kotemari_instance.start_watching()

    # Check that monitor was initialized with project root and ignore processor
    # モニターがプロジェクトルートと無視プロセッサで初期化されたことを確認します
    MockMonitor.assert_called_once_with(kotemari_instance.project_root, kotemari_instance._ignore_processor)
    # Check that start was called on the instance with a callback
    # インスタンスで start がコールバック付きで呼び出されたことを確認します
    mock_monitor_instance.start.assert_called_once_with(callback=ANY) # ANY checks for any function/method

@patch("kotemari.core.FileSystemEventMonitor")
def test_start_watching_already_running(MockMonitor, kotemari_instance: Kotemari):
    """Test that start_watching does nothing if already running."""
    # """既に実行中の場合、start_watching が何もしないことをテストします。"""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = True # Simulate running

    # Initialize the internal monitor reference first
    # 最初に内部モニター参照を初期化します
    kotemari_instance._event_monitor = mock_monitor_instance

    kotemari_instance.start_watching()

    # Monitor should not be initialized again, start should not be called again
    # モニターは再初期化されず、start は再呼び出しされません
    mock_monitor_instance.start.assert_not_called()

@patch("kotemari.core.FileSystemEventMonitor")
def test_stop_watching_stops_monitor(MockMonitor, kotemari_instance: Kotemari):
    """Test that stop_watching stops the monitor if it's alive."""
    # """生存している場合、stop_watching がモニターを停止することをテストします。"""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = True
    kotemari_instance._event_monitor = mock_monitor_instance # Set the internal reference

    kotemari_instance.stop_watching()

    mock_monitor_instance.stop.assert_called_once()

@patch("kotemari.core.FileSystemEventMonitor")
def test_stop_watching_not_running(MockMonitor, kotemari_instance: Kotemari):
    """Test that stop_watching does nothing if monitor is not alive."""
    # """モニターが生存していない場合、stop_watching が何もしないことをテストします。"""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = False
    kotemari_instance._event_monitor = mock_monitor_instance

    kotemari_instance.stop_watching()

    mock_monitor_instance.stop.assert_not_called()

@patch("kotemari.core.FileSystemEventMonitor")
@patch("kotemari.core.CacheUpdater") # Also mock CacheUpdater
def test_event_triggers_cache_invalidation_and_callback(MockUpdater, MockMonitor, kotemari_instance: Kotemari, test_project_path):
    """Test that a file event triggers cache invalidation and user callback."""
    # """ファイルイベントがキャッシュ無効化とユーザーコールバックをトリガーすることをテストします。"""
    mock_monitor_instance = MockMonitor.return_value
    mock_updater_instance = MockUpdater.return_value
    kotemari_instance._cache_updater = mock_updater_instance # Inject mock updater

    # Mock the monitor's start to capture the internal callback
    # 内部コールバックをキャプチャするためにモニターの start をモックします
    internal_callback: Optional[FileSystemEventCallback] = None
    def capture_callback(*args, **kwargs):
        nonlocal internal_callback
        internal_callback = kwargs.get('callback')
    mock_monitor_instance.start.side_effect = capture_callback

    mock_user_callback = MagicMock()
    kotemari_instance.start_watching(user_callback=mock_user_callback)

    # Ensure the callback was captured
    # コールバックがキャプチャされたことを確認します
    assert internal_callback is not None

    # Simulate an event being triggered by the monitor
    # モニターによってトリガーされたイベントをシミュレートします
    test_event = FileSystemEvent(
        event_type="modified",
        src_path=test_project_path / "file1.txt",
        is_directory=False
    )
    internal_callback(test_event) # Manually call the captured callback

    # Check that CacheUpdater.invalidate_cache_on_event was called
    # CacheUpdater.invalidate_cache_on_event が呼び出されたことを確認します
    mock_updater_instance.invalidate_cache_on_event.assert_called_once_with(test_event)

    # Check that the user callback was called
    # ユーザーコールバックが呼び出されたことを確認します
    mock_user_callback.assert_called_once_with(test_event)

@patch("kotemari.core.FileSystemEventMonitor")
def test_start_watching_cache_disabled(MockMonitor, test_project_path):
    """Test that watching cannot be started if cache is disabled."""
    # """キャッシュが無効な場合、監視を開始できないことをテストします。"""
    kotemari_no_cache = Kotemari(project_root=test_project_path, use_cache=False)
    mock_monitor_instance = MockMonitor.return_value

    kotemari_no_cache.start_watching()

    # Monitor should not be initialized or started
    # モニターは初期化または開始されません
    MockMonitor.assert_not_called()
    mock_monitor_instance.start.assert_not_called() 