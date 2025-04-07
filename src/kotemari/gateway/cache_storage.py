import pickle
from pathlib import Path
import logging
import os
from typing import Any, Tuple, Optional, List

from ..domain.file_info import FileInfo # Assuming cache stores List[FileInfo]
from ..domain.cache_metadata import CacheMetadata

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR_NAME = ".kotemari_cache"
DEFAULT_CACHE_FILE_NAME = "analysis_cache.pkl"

class CacheStorage:
    """
    Handles reading and writing cache data (analysis results and metadata) to disk.
    Uses pickle for serialization.
    キャッシュデータ（分析結果とメタデータ）のディスクへの読み書きを処理します。
    シリアライズには pickle を使用します。
    """

    def __init__(self, project_root: Path):
        """
        Initializes the CacheStorage.
        CacheStorage を初期化します。

        Args:
            project_root (Path): The root directory of the project.
                                 The cache directory will be created inside this root.
                                 プロジェクトのルートディレクトリ。
                                 キャッシュディレクトリはこのルート内に作成されます。
        """
        self.cache_dir = project_root.resolve() / DEFAULT_CACHE_DIR_NAME
        self.cache_file = self.cache_dir / DEFAULT_CACHE_FILE_NAME
        logger.debug(f"Cache directory set to: {self.cache_dir}")

    def _ensure_cache_dir_exists(self):
        """Ensures the cache directory exists."""
        if not self.cache_dir.exists():
            try:
                self.cache_dir.mkdir(parents=False, exist_ok=True)
                logger.info(f"Created cache directory: {self.cache_dir}")
            except OSError as e:
                logger.error(f"Failed to create cache directory {self.cache_dir}: {e}")
                # Re-raise or handle as appropriate? For now, log and continue.
                # 適切に再発生または処理しますか？今のところ、ログに記録して続行します。
                pass # Subsequent read/write attempts will likely fail

    def load_cache(self) -> Optional[Tuple[List[FileInfo], CacheMetadata]]:
        """
        Loads the cached analysis results and metadata from the cache file.
        キャッシュファイルからキャッシュされた分析結果とメタデータを読み込みます。

        Returns:
            Optional[Tuple[List[FileInfo], CacheMetadata]]:
                A tuple containing the list of FileInfo objects and CacheMetadata,
                or None if the cache file doesn't exist or fails to load.
                FileInfo オブジェクトのリストと CacheMetadata を含むタプル。
                キャッシュファイルが存在しないか、読み込みに失敗した場合は None。
        """
        if not self.cache_file.is_file():
            logger.info("Cache file not found.")
            return None

        try:
            with self.cache_file.open('rb') as f:
                cached_data = pickle.load(f)
            # Basic validation: Check if it's a tuple of expected types (list, CacheMetadata)
            # 基本的な検証: 期待される型（list、CacheMetadata）のタプルであるかを確認します
            if (
                isinstance(cached_data, tuple) and
                len(cached_data) == 2 and
                isinstance(cached_data[0], list) and
                all(isinstance(item, FileInfo) for item in cached_data[0]) and
                isinstance(cached_data[1], CacheMetadata)
            ):
                logger.info(f"Successfully loaded cache from {self.cache_file}")
                # Type hint helps static analysis
                result: Tuple[List[FileInfo], CacheMetadata] = cached_data
                return result
            else:
                logger.warning(f"Cache file {self.cache_file} has unexpected format. Ignoring cache.")
                self.clear_cache() # Clear invalid cache
                return None
        except (pickle.UnpicklingError, EOFError, TypeError, AttributeError, ValueError, ImportError) as e:
            logger.warning(f"Failed to load or unpickle cache file {self.cache_file}: {e}. Ignoring cache.")
            self.clear_cache() # Clear corrupted cache
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred loading cache from {self.cache_file}: {e}", exc_info=True)
            return None

    def save_cache(self, analysis_results: List[FileInfo], metadata: CacheMetadata):
        """
        Saves the analysis results and metadata to the cache file.
        分析結果とメタデータをキャッシュファイルに保存します。

        Args:
            analysis_results (List[FileInfo]): The list of FileInfo objects to cache.
                                               キャッシュする FileInfo オブジェクトのリスト。
            metadata (CacheMetadata): The metadata associated with the cache.
                                      キャッシュに関連付けられたメタデータ。
        """
        self._ensure_cache_dir_exists()
        data_to_save = (analysis_results, metadata)
        try:
            # Write to a temporary file first, then rename to make the save atomic
            # 最初に一時ファイルに書き込み、次に名前を変更して保存をアトミックにします
            temp_file_path = self.cache_file.with_suffix(f".{os.getpid()}.tmp")
            with temp_file_path.open('wb') as f:
                pickle.dump(data_to_save, f, protocol=pickle.HIGHEST_PROTOCOL)
            # Atomically replace the old cache file with the new one
            # 古いキャッシュファイルを新しいファイルでアトミックに置き換えます
            os.replace(temp_file_path, self.cache_file)
            logger.info(f"Successfully saved cache to {self.cache_file}")
        except (pickle.PicklingError, OSError, Exception) as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}", exc_info=True)
            # Attempt to clean up temporary file if it exists
            # 存在する場合、一時ファイルのクリーンアップを試みます
            if temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except OSError:
                    pass

    def clear_cache(self) -> bool:
        """
        Deletes the cache file if it exists.
        キャッシュファイルが存在する場合は削除します。

        Returns:
            bool: True if the cache file was deleted or didn't exist, False otherwise.
                  キャッシュファイルが削除されたか存在しなかった場合は True、それ以外の場合は False。
        """
        if self.cache_file.is_file():
            try:
                self.cache_file.unlink()
                logger.info(f"Cache file {self.cache_file} deleted.")
                return True
            except OSError as e:
                logger.error(f"Failed to delete cache file {self.cache_file}: {e}")
                return False
        else:
            logger.info("Cache file does not exist, nothing to clear.")
            return True # Considered success if already clear
                       # すでにクリアされている場合は成功とみなされます 

    def get_all_file_paths(self) -> List[str]:
        """
        Returns all file paths from the cached analysis results as strings.
        キャッシュされた分析結果からすべてのファイルパスを文字列として返します。

        Returns:
            List[str]: A list of file paths as strings.
                       文字列としてのファイルパスのリスト。
        """
        if self.cache_file.is_file():
            try:
                with self.cache_file.open('rb') as f:
                    cached_data = pickle.load(f)
                if (isinstance(cached_data, tuple) and len(cached_data) == 2 and
                    isinstance(cached_data[0], list)):
                    file_infos = cached_data[0]
                    # Assuming each FileInfo object has an attribute 'path' of type Path or str.
                    # 各 FileInfo オブジェクトが Path または str 型の 'path' 属性を持つと仮定します。
                    return [str(fi.path) for fi in file_infos if hasattr(fi, 'path')]
                else:
                    logger.warning(f"Cache file {self.cache_file} has unexpected format.")
                    return []
            except Exception as e:
                logger.error(f"Error loading cache in get_all_file_paths: {e}")
                return []
        else:
            return [] 