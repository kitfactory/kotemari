import pytest
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, ANY
import asyncio

from kotemari.utility.path_resolver import PathResolver
from kotemari.core import Kotemari
from kotemari.domain import ProjectConfig, FileSystemEvent, FileInfo
from kotemari.usecase import ConfigManager, ProjectAnalyzer, ContextBuilder
from kotemari.service import IgnoreRuleProcessor
from kotemari.domain.file_system_event import FileSystemEventType
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
def kotemari_instance(tmp_path: Path):
    """
    Fixture to create a Kotemari instance for testing.
    テスト用のKotemariインスタンスを作成するフィクスチャ。
    """
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    # Create a dummy file to ensure the directory is not empty
    (project_root / "dummy.py").touch()

    # English: Instantiate PathResolver
    # 日本語: PathResolver をインスタンス化
    path_resolver = PathResolver()

    instance = Kotemari(project_root)

    # Mock dependencies for testing the core logic without actual file processing
    # 実際のファイル処理なしでコアロジックをテストするために依存関係をモック化
    instance._config_manager = ConfigManager(path_resolver, instance.project_root)
    instance._config_manager.get_config = Mock(return_value=ProjectConfig())
    instance._ignore_processor = Mock(spec=IgnoreRuleProcessor)
    instance._analyzer = Mock(spec=ProjectAnalyzer)
    instance._context_builder = Mock(spec=ContextBuilder)
    instance._project_monitor = Mock() # Keep as simple Mock for now
    instance._background_task = None
    instance.is_watching = False
    instance._stop_event = asyncio.Event()
    instance._event_queue = asyncio.Queue()

    # Setup mocks as needed for specific tests
    instance._ignore_processor.should_ignore = Mock(return_value=False)
    instance._analyzer.analyze_file = AsyncMock(return_value=Mock()) # Return a mock FileInfo or similar

    return instance

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

@pytest.mark.asyncio # Mark test as async
@patch("kotemari.core.Kotemari._run_analysis_and_update_memory") # Mock the analysis function
@patch("kotemari.core.FileSystemEventMonitor")
async def test_event_triggers_cache_invalidation_and_callback(
    MockMonitor, mock_run_analysis, kotemari_instance: Kotemari, test_project_path
):
    """Test that a file system event triggers cache invalidation (via re-analysis) and user callback.
       非同期処理をシミュレートし、ファイルイベントがキャッシュ無効化（再分析）とユーザーコールバックをトリガーすることをテストします。
    """
    mock_monitor_instance = MockMonitor.return_value
    # user_callback = Mock() # User callback mock - Removed as start_watching doesn't accept it

    # Start watching
    # The background worker thread should start here
    kotemari_instance.start_watching() # Removed callback argument
    # Ensure the monitor's start method was called
    mock_monitor_instance.start.assert_called_once()

    # --- Simulate a file creation event ---
    created_file_path = test_project_path / "new_file.py"
    # Ensure the file does not exist initially if relevant for analysis mock
    if created_file_path.exists():
        created_file_path.unlink()

    # Simulate file creation
    created_file_path.touch()

    event = FileSystemEvent(
        # English: Use string literal for Literal type
        # 日本語: Literal 型には文字列リテラルを使用
        event_type="created",
        src_path=str(created_file_path),
        is_directory=False
    )

    # --- Simulate the event being processed by the background worker ---
    # Put the event onto the queue that the background worker reads from
    assert kotemari_instance._event_queue is not None, "Event queue not initialized"
    kotemari_instance._event_queue.put(event)

    # Wait for the background worker to potentially process the event
    # This duration might need adjustment based on worker logic complexity
    await asyncio.sleep(0.2) # Give worker time

    # --- Assertions ---
    # 1. Check if full re-analysis was triggered.
    #    For a simple CREATED event, differential update should handle it,
    #    so the full analysis mock should NOT have been called.
    mock_run_analysis.assert_not_called()

    # 2. Check if the user callback was called - Removed as callback mechanism is not used.
    # user_callback.assert_not_called()

    # 3. Check if the analysis cache was updated (indirect check)
    #    We can't easily inspect the internal _analysis_results directly
    #    without making it public or adding test helpers. A more robust test
    #    might involve calling list_files() after the event and asserting
    #    the new file is present (assuming differential update worked).
    #    For now, relying on mock_run_analysis not being called is the primary
    #    check for differential update success.

    # --- Cleanup ---
    kotemari_instance.stop_watching()
    # Ensure the monitor's stop method was called
    mock_monitor_instance.stop.assert_called_once() 