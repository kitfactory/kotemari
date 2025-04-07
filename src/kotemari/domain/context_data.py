from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

@dataclass(frozen=True)
class ContextData:
    """
    Represents the generated context for a set of target files.
    ターゲットファイルのセットに対して生成されたコンテキストを表します。

    Attributes:
        target_files: The list of absolute file paths the context was generated for.
                      コンテキストが生成された対象の絶対ファイルパスのリスト。
        context_string: The generated context as a single string.
                        単一の文字列として生成されたコンテキスト。
        related_files: Optional list of additional related file paths discovered during context generation.
                       コンテキスト生成中に発見された追加の関連ファイルパスのオプションリスト。
        context_type: Optional identifier for the type or strategy of context generation used.
                      使用されたコンテキスト生成のタイプまたは戦略のオプション識別子。
    """
    target_files: List[Path]
    context_string: str
    related_files: Optional[List[Path]] = field(default=None)
    context_type: Optional[str] = field(default=None)

    # TODO: Add metadata later, like included files, tokens count, etc.
    # TODO: 後でメタデータを追加します（例: 含まれるファイル、トークン数など） 