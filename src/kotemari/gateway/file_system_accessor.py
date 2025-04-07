from pathlib import Path
import os
import datetime
from typing import Iterator, List, Callable # Iterator, List, Callable をインポート
import sys
import logging

from ..domain.file_info import FileInfo
from ..utility.path_resolver import PathResolver
from ..domain.exceptions import FileSystemError # カスタム例外をインポート

logger = logging.getLogger(__name__)

class FileSystemAccessor:
    """
    Provides access to the file system for reading files and listing directories.
    ファイル読み込みとディレクトリ一覧表示のためにファイルシステムへのアクセスを提供します。
    """

    def __init__(self, path_resolver: PathResolver):
        """
        Initializes the FileSystemAccessor.
        FileSystemAccessorを初期化します。

        Args:
            path_resolver (PathResolver): An instance of PathResolver for path operations.
                                          パス操作のためのPathResolverのインスタンス。
        """
        self.path_resolver = path_resolver

    def read_file(self, file_path: Path | str) -> str:
        """
        Reads the content of a file.
        ファイルの内容を読み込みます。

        Args:
            file_path (Path | str): The path to the file to read.
                                    読み込むファイルのパス。

        Returns:
            str: The content of the file.
                 ファイルの内容。

        Raises:
            FileNotFoundError: If the file does not exist.
                               ファイルが存在しない場合。
            IOError: If there is an error reading the file.
                     ファイルの読み込み中にエラーが発生した場合。
        """
        abs_path = self.path_resolver.resolve_absolute(file_path)
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError as e:
            # Wrap FileNotFoundError in our custom FileSystemError
            # FileNotFoundError をカスタム FileSystemError でラップします
            logger.warning(f"File not found during read: {abs_path}")
            raise FileSystemError(f"File not found: {abs_path}") from e
        except IOError as e: # Catch potential encoding errors or other read issues
            logger.error(f"IOError reading file {abs_path}: {e}")
            raise FileSystemError(f"Error reading file {abs_path}: {e}") from e
        except Exception as e: # Catch other unexpected errors
            # Catch potential encoding errors or other read issues
            # エンコーディングエラーやその他の読み取り問題をキャッチする
            logger.exception(f"Unexpected error reading file {abs_path}: {e}")
            raise FileSystemError(f"Unexpected error reading file {abs_path}: {e}") from e

    def scan_directory(self, dir_path: Path | str, ignore_func: Callable[[Path], bool] | None = None) -> Iterator[FileInfo]:
        """
        Recursively scans a directory and yields FileInfo objects for each file found.
        Optionally applies an ignore function to skip certain files or directories.
        ディレクトリを再帰的にスキャンし、見つかった各ファイルのFileInfoオブジェクトをyieldします。
        オプションで無視関数を適用して、特定のファイルやディレクトリをスキップします。

        Args:
            dir_path (Path | str): The path to the directory to scan.
                                   スキャンするディレクトリのパス。
            ignore_func (Callable[[Path], bool] | None, optional):
                A function that takes a Path object and returns True if it should be ignored.
                Defaults to None (no ignoring).
                Pathオブジェクトを受け取り、無視すべき場合にTrueを返す関数。
                デフォルトは None (無視しない)。

        Yields:
            Iterator[FileInfo]: An iterator yielding FileInfo objects for non-ignored files.
                                無視されなかったファイルのFileInfoオブジェクトをyieldするイテレータ。

        Raises:
            FileNotFoundError: If the directory does not exist.
                               ディレクトリが存在しない場合。
        """
        abs_dir_path = self.path_resolver.resolve_absolute(dir_path)
        if not abs_dir_path.is_dir():
            # Raise custom FileSystemError if directory not found
            # ディレクトリが見つからない場合にカスタム FileSystemError を発生させます
            raise FileSystemError(f"Directory not found: {abs_dir_path}")

        for root, dirs, files in os.walk(abs_dir_path, topdown=True):
            root_path = Path(root)

            # Apply ignore function to directories
            # ディレクトリに無視関数を適用する
            if ignore_func:
                # Filter dirs in-place to prevent descending into ignored directories
                # 無視されたディレクトリへの降下を防ぐために、dirsをインプレースでフィルタリングする
                dirs[:] = [d for d in dirs if not ignore_func(root_path / d)]

            for file_name in files:
                file_path = root_path / file_name

                # Apply ignore function to files
                # ファイルに無視関数を適用する
                if ignore_func and ignore_func(file_path):
                    continue

                try:
                    stat_result = file_path.stat()
                    mtime = datetime.datetime.fromtimestamp(stat_result.st_mtime, tz=datetime.timezone.utc)
                    size = stat_result.st_size
                    yield FileInfo(path=file_path, mtime=mtime, size=size)
                except OSError as e:
                    # Handle potential errors like permission denied during stat
                    # stat中の権限拒否などの潜在的なエラーを処理する
                    # Log this error? For now, skip the file.
                    # このエラーをログに記録しますか？今のところ、ファイルをスキップします。
                    logger.warning(f"Could not access file info for {file_path}: {e}")
                    # Optionally raise FileSystemError here? Decide based on desired strictness.
                    # オプションでここで FileSystemError を発生させますか？望ましい厳格さに基づいて決定します。
                    pass 

    def exists(self, file_path: Path | str) -> bool:
        """
        Checks if a file or directory exists at the given path.
        指定されたパスにファイルまたはディレクトリが存在するかどうかを確認します。

        Args:
            file_path (Path | str): The path to check.
                                    確認するパス。

        Returns:
            bool: True if the path exists, False otherwise.
                  パスが存在する場合は True、それ以外の場合は False。
        """
        abs_path = self.path_resolver.resolve_absolute(file_path)
        return abs_path.exists() 