from dataclasses import dataclass


@dataclass
class ContextData:
    """
    Represents the generated context data for LLM input.
    LLM入力用に生成されたコンテキストデータを表します。

    Attributes:
        content (str): The combined content of the relevant files.
                      関連ファイルの結合された内容。
        # TODO: Add metadata later, like included files, tokens count, etc.
        # TODO: 後でメタデータを追加します（例: 含まれるファイル、トークン数など）
    """
    content: str 