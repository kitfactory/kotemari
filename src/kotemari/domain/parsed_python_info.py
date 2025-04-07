"""
Domain object representing the parsed information from a Python file.
Python ファイルから解析された情報を表すドメインオブジェクト。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class ParsedPythonInfo:
    """
    Holds structured information extracted from parsing a Python source file.
    Python ソースファイルの解析から抽出された構造化情報を保持します。

    Attributes:
        file_path (Path): The absolute path to the parsed Python file.
                          解析された Python ファイルへの絶対パス。
        imports (List[str]): A list of imported modules or objects (e.g., 'os', 'pathlib.Path', 'collections.defaultdict').
                             インポートされたモジュールまたはオブジェクトのリスト (例: 'os', 'pathlib.Path', 'collections.defaultdict')。
        defined_classes (List[str]): A list of class names defined within the file.
                                     ファイル内で定義されたクラス名のリスト。
        defined_functions (List[str]): A list of function/method names defined within the file.
                                       ファイル内で定義された関数/メソッド名のリスト。
        top_level_calls (List[str]): A list of function/method calls made at the top level of the module.
                                    モジュールのトップレベルで行われた関数/メソッド呼び出しのリスト。
        docstring (Optional[str]): The module-level docstring, if present.
                                   モジュールレベルのドキュメント文字列 (存在する場合)。
    """
    file_path: Path
    imports: List[str] = field(default_factory=list)
    defined_classes: List[str] = field(default_factory=list)
    defined_functions: List[str] = field(default_factory=list)
    top_level_calls: List[str] = field(default_factory=list)
    docstring: Optional[str] = None 