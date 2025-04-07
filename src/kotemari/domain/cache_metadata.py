from dataclasses import dataclass
import datetime
from typing import List, Any # List と Any をインポート


@dataclass
class CacheMetadata:
    """
    Represents metadata about cached data.
    キャッシュされたデータに関するメタ情報を表します。

    Attributes:
        cache_time (datetime.datetime): The timestamp when the data was cached.
                                        データがキャッシュされた日時。
        source_hash (str): A hash representing the state of the source data when cached.
                           キャッシュ時のソースデータの状態を表すハッシュ。
        # TODO: Add more attributes like cache version, config hash, etc.
        # TODO: 後で属性を追加します（例: キャッシュバージョン、設定ハッシュなど）
    """
    cache_time: datetime.datetime
    source_hash: str # 例: プロジェクトファイル全体のハッシュなど
    # cached_data: Any # キャッシュされたデータ本体 (例: List[FileInfo]) は別途管理するか、ここに含めるか検討 