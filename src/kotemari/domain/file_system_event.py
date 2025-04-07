from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

# English comment:
# Define the types of file system events detected by watchdog.
# 日本語コメント:
# watchdog によって検出されるファイルシステムイベントの種類を定義します。
FileSystemEventType = Literal["created", "deleted", "modified", "moved"]

# English comment:
# Represents a file system event detected by the FileSystemEventMonitor.
# This class holds information about the type of event, the affected path(s),
# and whether the path refers to a directory.
# 日本語コメント:
# FileSystemEventMonitor によって検出されたファイルシステムイベントを表します。
# このクラスは、イベントの種類、影響を受けるパス、およびパスがディレクトリを参照するかどうかに関する情報を保持します。
@dataclass(frozen=True)
class FileSystemEvent:
    # English comment:
    # The type of the event (e.g., 'created', 'modified').
    # 日本語コメント:
    # イベントの種類（例: 'created', 'modified'）。
    event_type: FileSystemEventType

    # English comment:
    # The source path of the file system object that triggered the event.
    # For 'moved' events, this is the original path.
    # 日本語コメント:
    # イベントをトリガーしたファイルシステムオブジェクトのソースパス。
    # 'moved' イベントの場合、これは元のパスです。
    src_path: Path

    # English comment:
    # Indicates whether the event pertains to a directory.
    # 日本語コメント:
    # イベントがディレクトリに関するものかどうかを示します。
    is_directory: bool

    # English comment:
    # The destination path for 'moved' events. None for other event types.
    # 日本語コメント:
    # 'moved' イベントの移動先パス。他のイベントタイプの場合は None。
    dest_path: Optional[Path] = None 