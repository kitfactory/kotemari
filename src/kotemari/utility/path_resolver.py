from pathlib import Path
import os


class PathResolver:
    """
    Provides utility functions for resolving and normalizing file paths.
    ファイルパスの解決と正規化のためのユーティリティ機能を提供します。
    """

    @staticmethod
    def normalize(path: Path | str) -> Path:
        """
        Normalizes a given path string or Path object.
        Resolves '..' and '.' components and ensures consistent representation.
        与えられたパス文字列またはPathオブジェクトを正規化します。
        '..' や '.' のコンポーネントを解決し、一貫した表現を保証します。

        Args:
            path (Path | str): The path to normalize.
                               正規化するパス。

        Returns:
            Path: The normalized Path object.
                  正規化されたPathオブジェクト。
        """
        return Path(os.path.normpath(str(path)))

    @staticmethod
    def resolve_absolute(path: Path | str, base_dir: Path | str | None = None) -> Path:
        """
        Resolves a given path to an absolute path.
        If the path is relative, it's resolved relative to the base_dir (or current working directory if base_dir is None).
        与えられたパスを絶対パスに解決します。
        パスが相対パスの場合、base_dir を基準に解決します (base_dirがNoneの場合は現在の作業ディレクトリを基準にします)。

        Args:
            path (Path | str): The path to resolve.
                               解決するパス。
            base_dir (Path | str | None, optional): The base directory for resolving relative paths.
                                                    Defaults to None (use current working directory).
                                                    相対パスを解決するための基準ディレクトリ。
                                                    デフォルトは None (現在の作業ディレクトリを使用)。

        Returns:
            Path: The absolute, normalized Path object.
                  絶対パスで正規化されたPathオブジェクト。
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return PathResolver.normalize(path_obj)
        else:
            base = Path(base_dir) if base_dir else Path.cwd()
            absolute_path = base.resolve() / path_obj
            return PathResolver.normalize(absolute_path) 