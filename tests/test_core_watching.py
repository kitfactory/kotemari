import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

from kotemari.core import Kotemari
from kotemari.domain.file_system_event import FileSystemEvent, FileSystemEventType
from kotemari.service.file_system_event_monitor import FileSystemEventMonitor, FileSystemEventCallback
from kotemari.domain.exceptions import AnalysisError

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
    return Kotemari(project_root=test_project_path)

# --- Test Cases --- #

@patch("kotemari.core.FileSystemEventMonitor")
def test_start_watching_initializes_and_starts_monitor(MockMonitor, kotemari_instance: Kotemari):
    """Test that start_watching initializes and starts the monitor correctly."""
    # This test now implicitly uses the Kotemari instance created by the fixture
    # It assumes the fixture correctly initializes Kotemari without use_cache
    mock_monitor_instance = MockMonitor.return_value

    kotemari_instance.start_watching()

    MockMonitor.assert_called_once_with(
        kotemari_instance.project_root,
        ANY, # internal_event_handler
        ignore_func=ANY # ignore_func from ignore_processor
    )
    mock_monitor_instance.start.assert_called_once()
    assert kotemari_instance._event_monitor is mock_monitor_instance
    assert kotemari_instance._background_worker_thread.is_alive() # Check worker thread started

    # Clean up
    kotemari_instance.stop_watching()

@patch("kotemari.core.FileSystemEventMonitor")
def test_start_watching_already_running(MockMonitor, kotemari_instance: Kotemari, caplog):
    """Test that calling start_watching again when already running logs a warning."""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = True

    kotemari_instance.start_watching() # First call
    mock_monitor_instance.start.assert_called_once() # Should be called once
    kotemari_instance.start_watching() # Second call

    mock_monitor_instance.start.assert_called_once() # Should still be called only once
    assert "File system monitor is already running." in caplog.text

    # Clean up
    mock_monitor_instance.is_alive.return_value = False # Allow stop
    kotemari_instance.stop_watching()

@patch("kotemari.core.FileSystemEventMonitor")
def test_stop_watching_stops_monitor(MockMonitor, kotemari_instance: Kotemari):
    """Test that stop_watching stops the monitor and worker thread."""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = True

    kotemari_instance.start_watching()

    # Mock the worker thread join for faster test
    with patch.object(kotemari_instance._background_worker_thread, 'join') as mock_join:
        kotemari_instance.stop_watching()

    mock_monitor_instance.stop.assert_called_once()
    mock_monitor_instance.join.assert_called_once()
    assert kotemari_instance._stop_worker_event.is_set()
    mock_join.assert_called_once()
    assert kotemari_instance._event_monitor is None
    assert kotemari_instance._background_worker_thread is None

@patch("kotemari.core.FileSystemEventMonitor")
def test_stop_watching_not_running(MockMonitor, kotemari_instance: Kotemari, caplog):
    """Test that stop_watching logs a warning if the monitor is not running."""
    mock_monitor_instance = MockMonitor.return_value
    mock_monitor_instance.is_alive.return_value = False # Simulate not running

    kotemari_instance.stop_watching()

    mock_monitor_instance.stop.assert_not_called()
    assert "File system monitor is not running." in caplog.text

@patch("kotemari.core.Kotemari._run_analysis_and_update_memory") # Mock the analysis function
@patch("kotemari.core.FileSystemEventMonitor")
def test_event_triggers_cache_invalidation_and_callback(MockMonitor, mock_run_analysis, kotemari_instance: Kotemari, test_project_path):
    """Test that a file system event triggers cache invalidation (via re-analysis) and user callback."""
    mock_monitor_instance = MockMonitor.return_value
    user_callback = MagicMock()

    # Capture the internal event handler passed to the monitor
    internal_event_handler = None
    def capture_handler(*args, **kwargs):
        nonlocal internal_event_handler
        # The handler is the second argument (index 1)
        internal_event_handler = args[1]
        return mock_monitor_instance

    MockMonitor.side_effect = capture_handler

    kotemari_instance.start_watching(user_callback=user_callback)

    assert internal_event_handler is not None

    # Simulate an event
    # Use dictionary access for Enum member based on the AttributeError observed
    test_event = FileSystemEvent(event_type="modified", src_path=test_project_path / "some_file.py", is_directory=False)
    internal_event_handler(test_event)

    # Wait briefly for the background worker to process the event
    time.sleep(1.5) # Adjust if needed

    # Assertions
    user_callback.assert_called_once_with(test_event)
    mock_run_analysis.assert_called() # Check if re-analysis was triggered

    # Clean up
    kotemari_instance.stop_watching() 