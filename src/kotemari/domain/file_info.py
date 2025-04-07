from dataclasses import dataclass, field
from pathlib import Path
import datetime
from typing import Optional, List

from .dependency_info import DependencyInfo


@dataclass
class FileInfo:
    """
    Represents information about a single file in the project.
    プロジェクト内の単一ファイルに関する情報を表します。

    Attributes:
        path (Path): The absolute path to the file.
                     ファイルへの絶対パス。
        mtime (datetime.datetime): The last modification time of the file.
                                ファイルの最終更新日時。
        size (int): The size of the file in bytes.
                    ファイルサイズ（バイト単位）。
        hash (Optional[str]): The hash (e.g., SHA256) of the file content.
                              ファイル内容のハッシュ（例: SHA256）。
        language (Optional[str]): The detected programming language of the file.
                                  検出されたファイルのプログラミング言語。
        dependencies (List[DependencyInfo]): List of dependencies found in the file.
                                             ファイル内で見つかった依存関係のリスト。
    """
    path: Path
    mtime: datetime.datetime
    size: int
    hash: Optional[str] = None
    language: Optional[str] = None
    dependencies: List[DependencyInfo] = field(default_factory=list)