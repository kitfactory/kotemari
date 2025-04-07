import logging
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import (DirCreatedEvent, DirDeletedEvent,
                             DirModifiedEvent, DirMovedEvent, FileCreatedEvent,
                             FileDeletedEvent, FileModifiedEvent,
                             FileMovedEvent, FileSystemEventHandler)
from watchdog.observers import Observer

from ..domain.file_system_event import FileSystemEvent, FileSystemEventType
from .ignore_rule_processor import IgnoreRuleProcessor

logger = logging.getLogger(__name__)

# English comment:
# Callback function type that receives a FileSystemEvent when a change is detected.
# 日本語コメント:
# 変更が検出されたときに FileSystemEvent を受け取るコールバック関数の型。
FileSystemEventCallback = Callable[[FileSystemEvent], None]

# English comment:
# Event handler class for watchdog that translates watchdog events into FileSystemEvent
# objects and calls the provided callback, considering ignore rules.
# 日本語コメント:
# watchdog イベントを FileSystemEvent オブジェクトに変換し、
# 無視ルールを考慮して提供されたコールバックを呼び出す watchdog 用のイベントハンドラクラス。
class _EventHandler(FileSystemEventHandler):
    def __init__(self,
                 callback: FileSystemEventCallback,
                 ignore_processor: IgnoreRuleProcessor,
                 project_root: Path):
        self.callback = callback
        # Get the ignore check function once during initialization
        # 初期化中に一度だけ無視チェック関数を取得します
        self.is_path_ignored: Callable[[Path], bool] = ignore_processor.get_ignore_function()
        self.project_root = project_root

    # English comment:
    # Generic event dispatcher that checks ignore rules before calling the callback.
    # 日本語コメント:
    # コールバックを呼び出す前に無視ルールをチェックする汎用イベントディスパッチャ。
    def dispatch(self, event):
        # Use watchdog event types directly for checking
        # チェックには watchdog イベントタイプを直接使用します
        if event.event_type in {'created', 'modified', 'deleted', 'moved'}:
            # For DirModifiedEvent, we often don't need to act directly
            # DirModifiedEvent の場合、直接対応する必要はほとんどありません
            if isinstance(event, DirModifiedEvent):
                return

            path_to_check = Path(event.src_path)

            # Check if the absolute path should be ignored using the function obtained earlier
            # 以前取得した関数を使用して絶対パスが無視されるべきかチェックします
            if self.is_path_ignored(path_to_check):
                logger.debug(f"Ignoring event for ignored path: {path_to_check}")
                return

            # For move events, also check the destination path
            # 移動イベントの場合、移動先のパスもチェックします
            dest_path: Optional[Path] = None
            event_type: FileSystemEventType = event.event_type # type: ignore because watchdog types differ slightly

            if event.event_type == 'moved':
                dest_path_abs = Path(event.dest_path)
                if self.is_path_ignored(dest_path_abs):
                    logger.debug(f"Ignoring move event due to ignored destination: {dest_path_abs}")
                    return
                dest_path = dest_path_abs
            elif event.event_type not in {'created', 'modified', 'deleted'}:
                 # Should not happen based on outer if, but good for safety
                 # 外側のifに基づけば発生しないはずですが、安全のため
                 logger.warning(f"Unhandled event type in dispatch: {event.event_type}")
                 return

            # Create our domain event object
            # ドメインイベントオブジェクトを作成します
            fs_event = FileSystemEvent(
                event_type=event_type,
                src_path=path_to_check,
                is_directory=event.is_directory,
                dest_path=dest_path
            )
            logger.info(f"Detected file system event: {fs_event}")
            self.callback(fs_event)
        else:
            # Pass through other event types (like DirModified which we explicitly ignore above)
            # 他のイベントタイプを通過させます（上で明示的に無視した DirModified など）
            super().dispatch(event)

# English comment:
# Service class responsible for monitoring file system changes using watchdog.
# It initializes and manages the watchdog observer and event handler,
# filtering events based on ignore rules.
# 日本語コメント:
# watchdog を使用してファイルシステムの変更を監視するサービスクラス。
# watchdog オブザーバーとイベントハンドラを初期化および管理し、
# 無視ルールに基づいてイベントをフィルタリングします。
class FileSystemEventMonitor:
    def __init__(self, project_root: Path, ignore_processor: IgnoreRuleProcessor):
        self.project_root = project_root
        self.ignore_processor = ignore_processor
        self._observer: Optional[Observer] = None
        self._event_handler: Optional[_EventHandler] = None
        self._callback: Optional[FileSystemEventCallback] = None

    # English comment:
    # Starts the file system monitoring in a separate thread.
    # Takes an optional callback function to be executed when a relevant event occurs.
    # 日本語コメント:
    # 別のスレッドでファイルシステムの監視を開始します。
    # 関連イベントが発生したときに実行されるオプションのコールバック関数を受け取ります。
    def start(self, callback: Optional[FileSystemEventCallback] = None):
        if self._observer and self._observer.is_alive():
            logger.warning("Observer is already running.")
            return

        self._callback = callback if callback else self._default_callback
        self._event_handler = _EventHandler(self._callback, self.ignore_processor, self.project_root)
        self._observer = Observer()
        self._observer.schedule(self._event_handler, str(self.project_root), recursive=True)

        try:
            self._observer.start()
            logger.info(f"Started watching directory: {self.project_root}")
        except Exception as e:
            logger.error(f"Failed to start observer: {e}")
            self._observer = None # Reset observer if start failed

    # English comment:
    # Stops the file system monitoring thread.
    # 日本語コメント:
    # ファイルシステムの監視スレッドを停止します。
    def stop(self):
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            logger.info("Stopped watching directory.")
        else:
            logger.warning("Observer is not running or already stopped.")
        self._observer = None
        self._event_handler = None
        self._callback = None

    # English comment:
    # Default callback function used if no specific callback is provided.
    # 日本語コメント:
    # 特定のコールバックが提供されない場合に使用されるデフォルトのコールバック関数。
    def _default_callback(self, event: FileSystemEvent):
        # This default callback does nothing but log. Users will typically provide
        # their own callback (e.g., CacheUpdater.invalidate_cache_on_event).
        # このデフォルトコールバックはログ記録以外何もしません。通常、ユーザーは
        # 独自のコールバック（例：CacheUpdater.invalidate_cache_on_event）を提供します。
        logger.debug(f"Default callback received event: {event}")

    def is_alive(self) -> bool:
        """Check if the observer thread is currently running."""
        # """オブザーバースレッドが現在実行中かどうかを確認します。"""
        return self._observer is not None and self._observer.is_alive() 