from pathlib import Path
import logging
import datetime
import hashlib
from typing import List, Optional, Tuple

from ..domain.file_info import FileInfo
from ..domain.cache_metadata import CacheMetadata
from ..gateway.cache_storage import CacheStorage
from ..utility.path_resolver import PathResolver # May be needed if resolving paths here
from ..domain.file_system_event import FileSystemEvent # Add this import

logger = logging.getLogger(__name__)

class CacheUpdater:
    """
    Manages the lifecycle of the analysis cache.
    Checks cache validity based on metadata (e.g., source hash).
    Loads cache if valid, triggers analysis and saves cache if invalid or missing.
    分析キャッシュのライフサイクルを管理します。
    メタデータ（例: ソースハッシュ）に基づいてキャッシュの有効性をチェックします。
    有効な場合はキャッシュを読み込み、無効または欠落している場合は分析をトリガーしてキャッシュを保存します。
    """

    def __init__(self, project_root: Path, cache_storage: Optional[CacheStorage] = None):
        """
        Initializes the CacheUpdater.
        CacheUpdater を初期化します。

        Args:
            project_root (Path): The root directory of the project.
                                 プロジェクトのルートディレクトリ。
            cache_storage (Optional[CacheStorage]): CacheStorage instance.
                                                    If None, a default one is created.
                                                    CacheStorage インスタンス。
                                                    None の場合、デフォルトのものが作成されます。
        """
        self.project_root = project_root.resolve()
        self.cache_storage = cache_storage or CacheStorage(self.project_root)

    def _calculate_project_state_hash(self, analyzed_files: List[FileInfo]) -> str:
        """
        Calculates a hash representing the current state of the analyzed files.
        This simple version hashes the sorted list of (relative_path, mtime, size, hash).
        分析されたファイルの現在の状態を表すハッシュを計算します。
        この簡単なバージョンは、（relative_path、mtime、size、hash）のソートされたリストをハッシュ化します。

        Args:
            analyzed_files (List[FileInfo]): The list of analyzed files.
                                             分析されたファイルのリスト。

        Returns:
            str: A SHA256 hash representing the project state.
                 プロジェクトの状態を表す SHA256 ハッシュ。
        """
        if not analyzed_files:
            return hashlib.sha256(b"empty_project").hexdigest()

        hasher = hashlib.sha256()
        # Sort files by path to ensure consistent hashing order
        # 一貫したハッシュ順序を確保するために、パスでファイルをソートします
        sorted_files = sorted(analyzed_files, key=lambda fi: fi.path)

        for fi in sorted_files:
            try:
                relative_path = fi.path.relative_to(self.project_root).as_posix()
                # Include path, mtime (timestamp), size, and the file's own hash
                # パス、mtime（タイムスタンプ）、サイズ、およびファイル自体のハッシュを含めます
                state_str = f"{relative_path}|{fi.mtime.timestamp()}|{fi.size}|{fi.hash or 'NOHASH'}"
                hasher.update(state_str.encode('utf-8'))
            except ValueError:
                # Should not happen if analyzer provides correct paths
                # アナライザーが正しいパスを提供していれば発生しないはずです
                logger.warning(f"Could not get relative path for {fi.path} relative to {self.project_root}. Skipping file for state hash.")
                continue
            except Exception as e:
                logger.error(f"Error processing file {fi.path} for state hash: {e}", exc_info=True)
                # Handle error: maybe return a special hash or raise?
                # エラー処理: 特別なハッシュを返すか、発生させますか？
                # For now, continue, potentially leading to an inaccurate state hash
                # 今のところ、続行します。これにより、不正確な状態ハッシュになる可能性があります
                continue

        return hasher.hexdigest()

    def get_valid_cache(self, current_files: List[FileInfo]) -> Optional[List[FileInfo]]:
        """
        Attempts to load the cache and validates it against the current project state.
        キャッシュの読み込みを試み、現在のプロジェクトの状態に対して検証します。

        Args:
            current_files (List[FileInfo]): The list of files as currently analyzed (used for state hashing).
                                            現在分析されているファイルのリスト（状態ハッシュに使用）。

        Returns:
            Optional[List[FileInfo]]: The cached list of FileInfo if the cache is valid, otherwise None.
                                     キャッシュが有効な場合はキャッシュされた FileInfo のリスト、それ以外の場合は None。
        """
        cached_data = self.cache_storage.load_cache()
        if cached_data is None:
            logger.info("No valid cache found (or cache file missing/corrupt).")
            return None

        _cached_files, metadata = cached_data
        current_state_hash = self._calculate_project_state_hash(current_files)

        if metadata.source_hash == current_state_hash:
            logger.info(f"Cache is valid (Source hash match: {current_state_hash[:8]}...).")
            # Note: We return the _cached_files list, not current_files, as the cache is valid.
            # 注意: キャッシュが有効であるため、current_files ではなく _cached_files リストを返します。
            return _cached_files
        else:
            logger.info("Cache is invalid (source hash mismatch). Expected: {metadata.source_hash[:8]}..., Got: {current_state_hash[:8]}...")
            return None

    def update_cache(self, analysis_results: List[FileInfo]):
        """
        Calculates the new state hash and saves the analysis results to the cache.
        新しい状態ハッシュを計算し、分析結果をキャッシュに保存します。

        Args:
            analysis_results (List[FileInfo]): The fresh analysis results to be cached.
                                               キャッシュされる新しい分析結果。
        """
        if not analysis_results:
             logger.info("Skipping cache update for empty analysis results.")
             # Optionally clear existing cache if results are now empty?
             # 結果が空になった場合、オプションで既存のキャッシュをクリアしますか？
             # self.cache_storage.clear_cache()
             return

        current_state_hash = self._calculate_project_state_hash(analysis_results)
        metadata = CacheMetadata(
            cache_time=datetime.datetime.now(datetime.timezone.utc),
            source_hash=current_state_hash
        )
        self.cache_storage.save_cache(analysis_results, metadata)
        logger.info(f"Cache updated with new state hash: {current_state_hash[:8]}...")

    def invalidate_cache_on_event(self, event: FileSystemEvent):
        """
        Invalidates relevant caches based on a file system event.
        Currently, any file/dir event invalidates the main analysis cache.
        For simplicity, it also clears all context caches (if they existed).
        ファイルシステムイベントに基づいて関連するキャッシュを無効化します。
        現在、どのファイル/ディレクトリイベントでもメイン分析キャッシュが無効になります。
        簡単にするために、すべてのコンテキストキャッシュもクリアします（存在する場合）。

        Args:
            event (FileSystemEvent): The detected file system event.
                                     検出されたファイルシステムイベント。
        """
        logger.info(f"Invalidating cache due to event: {event}")

        # Always invalidate the main analysis cache regardless of the specific file
        # 特定のファイルに関係なく、常にメイン分析キャッシュを無効化します
        try:
            self.cache_storage.clear_cache(target="analysis")
            logger.debug("Invalidated analysis cache.")
        except Exception as e:
            logger.error(f"Error invalidating analysis cache: {e}", exc_info=True)

        # Invalidate context caches (simplistic approach: clear all)
        # コンテキストキャッシュを無効化します (単純なアプローチ: すべてクリア)
        # TODO: Implement more granular context cache invalidation based on dependencies
        # TODO: 依存関係に基づいて、より詳細なコンテキストキャッシュの無効化を実装します
        try:
            self.cache_storage.clear_cache(target="context") # Assuming target="context" handles context caches
            logger.debug("Invalidated context cache (all).")
        except FileNotFoundError:
             logger.debug("No context cache found to invalidate.") # It's ok if context cache doesn't exist
        except Exception as e:
            logger.error(f"Error invalidating context cache: {e}", exc_info=True)

    def clear_cache(self):
        """Clears the cache using the CacheStorage."""
        self.cache_storage.clear_cache()