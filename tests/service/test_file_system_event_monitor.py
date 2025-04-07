import time
import pytest
import logging
from pathlib import Path
from unittest.mock import MagicMock, call

from kotemari.domain.file_system_event import FileSystemEvent
from kotemari.service.file_system_event_monitor import FileSystemEventMonitor, FileSystemEventCallback
from kotemari.service.ignore_rule_processor import IgnoreRuleProcessor

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def monitor_setup(tmp_path: Path, mocker):
    """Fixture to set up the FileSystemEventMonitor and test directory."""
    # """FileSystemEventMonitor とテストディレクトリをセットアップするフィクスチャ。"""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / ".gitignore").write_text("ignored_file.txt\nignored_dir/\n")

    # Mock IgnoreRuleProcessor to control ignore behavior
    # 無視の動作を制御するために IgnoreRuleProcessor をモックします
    mock_ignore_processor = MagicMock(spec=IgnoreRuleProcessor)

    # Define the mock check function based on the fixture's rules
    # フィクスチャのルールに基づいてモックチェック関数を定義します
    def mock_check_ignore(abs_path: Path) -> bool:
        # Simulate the behavior: check relative path
        # 動作をシミュレートします: 相対パスをチェックします
        try:
            relative_path = abs_path.relative_to(project_root)
            path_str = relative_path.as_posix()
            # Check exact file match or if path starts with ignored directory name
            # 正確なファイル一致、またはパスが無視されたディレクトリ名で始まるかチェックします
            if path_str == "ignored_file.txt" or path_str == "ignored_dir" or path_str.startswith("ignored_dir/"):
                logger.debug(f"Mock check: {abs_path} (rel: {path_str}) -> Ignored")
                return True
            logger.debug(f"Mock check: {abs_path} (rel: {path_str}) -> Not Ignored")
            return False
        except ValueError:
             logger.debug(f"Mock check: {abs_path} -> Outside project, Not Ignored")
             return False # Path outside project root

    # Configure the mock object's get_ignore_function to return our mock checker
    # モックオブジェクトの get_ignore_function がモックチェッカーを返すように設定します
    mock_ignore_processor.get_ignore_function.return_value = mock_check_ignore

    monitor = FileSystemEventMonitor(project_root, mock_ignore_processor)
    mock_callback = MagicMock(spec=FileSystemEventCallback)

    yield project_root, monitor, mock_callback, mock_ignore_processor

    # Teardown: stop the monitor if it's running
    # ティアダウン: モニターが実行中の場合は停止します
    if monitor.is_alive():
        monitor.stop()

def wait_for_event(timeout=1.5):
    """Wait for a short period to allow watchdog to detect the event."""
    # """watchdog がイベントを検出できるように短時間待機します。"""
    time.sleep(timeout)

# --- Test Cases --- #

def test_monitor_start_stop(monitor_setup):
    """Test starting and stopping the monitor."""
    # """モニターの開始と停止をテストします。"""
    _, monitor, _, _ = monitor_setup
    assert not monitor.is_alive()
    monitor.start()
    assert monitor.is_alive()
    monitor.stop()
    assert not monitor.is_alive()

def test_detect_file_creation(monitor_setup):
    """Test detecting file creation."""
    # """ファイル作成の検出をテストします。"""
    project_root, monitor, mock_callback, _ = monitor_setup
    monitor.start(callback=mock_callback)
    wait_for_event(0.1) # Ensure observer is ready

    file_path = project_root / "new_file.txt"
    file_path.write_text("hello")
    logger.debug(f"Created file: {file_path}")
    wait_for_event()

    monitor.stop()

    # Check if callback was called with the correct event
    # コールバックが正しいイベントで呼び出されたかチェックします
    assert mock_callback.call_count >= 1
    # The exact call might be preceded by DirModified, check the last relevant call
    # 正確な呼び出しの前に DirModified がある可能性があります。最後の関連する呼び出しを確認します
    found = False
    for args, _ in mock_callback.call_args_list:
        event: FileSystemEvent = args[0]
        if event.event_type == 'created' and event.src_path == file_path and not event.is_directory:
             found = True
             break
    assert found, f"Callback not called for file creation: {mock_callback.call_args_list}"

def test_detect_file_modification(monitor_setup):
    """Test detecting file modification."""
    # """ファイル変更の検出をテストします。"""
    project_root, monitor, mock_callback, _ = monitor_setup
    file_path = project_root / "modify_me.txt"
    file_path.write_text("initial")

    monitor.start(callback=mock_callback)
    wait_for_event(0.1)

    file_path.write_text("modified")
    logger.debug(f"Modified file: {file_path}")
    wait_for_event()

    monitor.stop()

    assert mock_callback.call_count >= 1
    found = False
    for args, _ in mock_callback.call_args_list:
        event: FileSystemEvent = args[0]
        if event.event_type == 'modified' and event.src_path == file_path and not event.is_directory:
            found = True
            break
    assert found, f"Callback not called for file modification: {mock_callback.call_args_list}"

def test_detect_file_deletion(monitor_setup):
    """Test detecting file deletion."""
    # """ファイル削除の検出をテストします。"""
    project_root, monitor, mock_callback, _ = monitor_setup
    file_path = project_root / "delete_me.txt"
    file_path.write_text("delete")

    monitor.start(callback=mock_callback)
    wait_for_event(0.1)

    file_path.unlink()
    logger.debug(f"Deleted file: {file_path}")
    wait_for_event()

    monitor.stop()

    assert mock_callback.call_count >= 1
    found = False
    for args, _ in mock_callback.call_args_list:
        event: FileSystemEvent = args[0]
        if event.event_type == 'deleted' and event.src_path == file_path and not event.is_directory:
            found = True
            break
    assert found, f"Callback not called for file deletion: {mock_callback.call_args_list}"

def test_detect_file_move(monitor_setup):
    """Test detecting file move/rename."""
    # """ファイル移動/名前変更の検出をテストします。"""
    project_root, monitor, mock_callback, _ = monitor_setup
    src_path = project_root / "move_src.txt"
    dest_path = project_root / "move_dest.txt"
    src_path.write_text("move me")

    monitor.start(callback=mock_callback)
    wait_for_event(0.1)

    src_path.rename(dest_path)
    logger.debug(f"Moved file: {src_path} to {dest_path}")
    wait_for_event()

    monitor.stop()

    assert mock_callback.call_count >= 1
    found = False
    for args, _ in mock_callback.call_args_list:
        event: FileSystemEvent = args[0]
        # Watchdog often detects move as delete+create on some platforms/scenarios
        # watchdog は、一部のプラットフォーム/シナリオでは移動を delete+create として検出することがよくあります
        # We primarily check if the 'moved' event was captured
        # 主に 'moved' イベントがキャプチャされたかどうかを確認します
        if event.event_type == 'moved' and event.src_path == src_path and event.dest_path == dest_path:
            found = True
            break
    # If not found as 'moved', check if delete+create occurred for the paths
    # 'moved' として見つからない場合、パスに対して delete+create が発生したか確認します
    if not found:
         deleted = any(e.args[0].event_type == 'deleted' and e.args[0].src_path == src_path for e in mock_callback.call_args_list)
         created = any(e.args[0].event_type == 'created' and e.args[0].src_path == dest_path for e in mock_callback.call_args_list)
         assert deleted and created, f"Callback not called for file move (neither moved nor delete/create): {mock_callback.call_args_list}"
         logger.warning("File move detected as delete/create, which is acceptable.") # Log this variation
    else:
        assert found, f"Callback not called for file move: {mock_callback.call_args_list}"


def test_ignore_file_creation(monitor_setup):
    """Test that creating an ignored file does not trigger the callback."""
    # """無視されたファイルの作成がコールバックをトリガーしないことをテストします。"""
    project_root, monitor, mock_callback, mock_ignore_processor = monitor_setup
    monitor.start(callback=mock_callback)
    wait_for_event(0.1)

    ignored_file_path = project_root / "ignored_file.txt"
    ignored_file_path.write_text("ignored")
    logger.debug(f"Created ignored file: {ignored_file_path}")
    wait_for_event()

    monitor.stop()

    # Ensure ignore_processor.get_ignore_function was called (usually during EventHandler init)
    # ignore_processor.get_ignore_function が呼び出されたことを確認します（通常は EventHandler 初期化時）
    mock_ignore_processor.get_ignore_function.assert_called()

    # Ensure the internal check function was called with the absolute path
    # 内部チェック関数が絶対パスで呼び出されたことを確認します
    # Note: We can't directly assert calls on the local 'mock_check_ignore' function returned by the mock.
    # Instead, we rely on the fact that if the check function returned True, the event callback shouldn't be called.
    # 注意: モックによって返されたローカルな 'mock_check_ignore' 関数に対する呼び出しを直接表明することはできません。
    # 代わりに、チェック関数が True を返した場合、イベントコールバックは呼び出されないという事実に依存します。

    # Callback should not have been called for this specific event
    # この特定のイベントに対してコールバックが呼び出されていないはずです
    called_for_ignored = False
    for args_list in mock_callback.call_args_list:
        args = args_list[0]
        if not args: continue
        event: FileSystemEvent = args[0]
        if event.src_path == ignored_file_path:
            called_for_ignored = True
            break
    assert not called_for_ignored, f"Callback was called for an ignored file: {mock_callback.call_args_list}"

def test_ignore_directory_creation(monitor_setup):
    """Test that creating an ignored directory does not trigger the callback."""
    # """無視されたディレクトリの作成がコールバックをトリガーしないことをテストします。"""
    project_root, monitor, mock_callback, mock_ignore_processor = monitor_setup
    monitor.start(callback=mock_callback)
    wait_for_event(0.1)

    ignored_dir_path = project_root / "ignored_dir"
    ignored_dir_path.mkdir()
    file_inside = ignored_dir_path / "file.txt"
    file_inside.write_text("inside ignored") # Also create a file inside
    logger.debug(f"Created ignored directory and file inside: {ignored_dir_path}")
    wait_for_event()

    monitor.stop()

    # Ensure ignore_processor.get_ignore_function was called
    # ignore_processor.get_ignore_function が呼び出されたことを確認します
    mock_ignore_processor.get_ignore_function.assert_called()

    # Callback should not have been called for events within the ignored directory
    # 無視されたディレクトリ内のイベントに対してコールバックが呼び出されていないはずです
    called_for_ignored = False
    for args_list in mock_callback.call_args_list:
        args = args_list[0]
        if not args: continue
        event: FileSystemEvent = args[0]
        # Check if the event path starts with the ignored directory path
        # イベントパスが無視されたディレクトリパスで始まるかチェックします
        if event.src_path == ignored_dir_path or event.src_path == file_inside:
             called_for_ignored = True
             break
    assert not called_for_ignored, f"Callback was called for an event in ignored directory: {mock_callback.call_args_list}" 