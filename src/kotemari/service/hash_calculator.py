import hashlib
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HashCalculator:
    """
    Calculates hash values for files.
    ファイルのハッシュ値を計算します。
    """

    @staticmethod
    def calculate_file_hash(file_path: Path, algorithm: str = 'sha256', chunk_size: int = 8192) -> str | None:
        """
        Calculates the hash of a file's content.
        ファイル内容のハッシュを計算します。

        Args:
            file_path (Path): The path to the file.
                              ファイルへのパス。
            algorithm (str, optional): The hash algorithm to use (e.g., 'sha256', 'md5').
                                       Defaults to 'sha256'.
                                       使用するハッシュアルゴリズム（例: 'sha256', 'md5'）。
                                       デフォルトは 'sha256'。
            chunk_size (int, optional): The chunk size for reading the file.
                                        Defaults to 8192.
                                        ファイルを読み込む際のチャンクサイズ。
                                        デフォルトは 8192。

        Returns:
            str | None: The hexadecimal hash digest of the file, or None if the file cannot be read.
                       ファイルの16進数ハッシュダイジェスト。ファイルが読み取れない場合は None。
        """
        try:
            hasher = hashlib.new(algorithm)
            with file_path.open('rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            logger.warning(f"File not found, cannot calculate hash: {file_path}")
            return None
        except OSError as e:
            logger.warning(f"Error reading file {file_path} for hashing: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid hash algorithm specified: {algorithm}. {e}")
            # Or re-raise, depending on desired behavior
            # または、望ましい動作に応じて再発生させる
            return None
        except Exception as e:
            logger.error(f"Unexpected error calculating hash for {file_path}: {e}", exc_info=True)
            return None 