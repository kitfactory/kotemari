from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
from pathlib import Path

class DependencyType(Enum):
    """
    Enumeration for the type of dependency.
    依存関係の種類を示す列挙型。

    Attributes:
        INTERNAL_RELATIVE: Dependency is an internal relative import (e.g., from . import foo).
                           内部の相対インポート依存 (例: from . import foo)。
        INTERNAL_ABSOLUTE: Dependency is an internal absolute import (e.g., from kotemari.service import bar).
                           内部の絶対インポート依存 (例: from kotemari.service import bar)。
        EXTERNAL: Dependency is an external library import (e.g., import os).
                    外部ライブラリのインポート依存 (例: import os)。
    """
    INTERNAL_RELATIVE = auto()
    INTERNAL_ABSOLUTE = auto()
    EXTERNAL = auto()

@dataclass(init=False)
class DependencyInfo:
    """
    Represents a dependency relationship extracted from source code.
    ソースコードから抽出された依存関係を表します。

    Attributes:
        module_name: The name of the imported module (original string).
                     インポートされたモジュールの名前（元の文字列）。
        dependency_type: The type of the dependency (internal relative, internal absolute, external).
                         依存関係の種類（内部相対、内部絶対、外部）。
        level: The relative import level (for INTERNAL_RELATIVE only, e.g., 1 for '.', 2 for '..'). None otherwise.
               相対インポートのレベル（INTERNAL_RELATIVE のみ、例: '.' は 1, '..' は 2）。それ以外は None。
        resolved_name: The potentially resolved name or suffix for sorting/grouping.
                       ソート/グルーピング用の解決された可能性のある名前または接尾辞。
        resolved_path: The absolute path to the resolved dependency file (for internal dependencies).
                       解決された依存関係ファイルの絶対パス（内部依存関係の場合）。
    """
    dependency_type: DependencyType = field()  # Required dependency type
    resolved_name: str = field()         # The resolved dependency name
    module_name: str = field()           # The original module name
    level: int | None = field(default=None)  # Optional level, default is None
    resolved_path: Optional[Path] = field(default=None)

    def __init__(self, name: Optional[str] = None, *, dependency_type: DependencyType = DependencyType.EXTERNAL, resolved_name: Optional[str] = None, module_name: Optional[str] = None, level: Optional[int] = None, resolved_path: Optional[Path] = None):
        # Custom initializer supporting shorthand creation.
        # English: If 'name' is not provided, use the value of the 'module_name' keyword argument.
        # 日本語: 'name' が提供されない場合、module_name キーワード引数の値を使用します。
        if name is None:
            if module_name is not None:
                name = module_name
            else:
                raise TypeError("Missing required argument 'name'")

        if resolved_name is None:
            resolved_name = name
        if module_name is None:
            module_name = name

        self.dependency_type = dependency_type
        self.resolved_name = resolved_name
        self.module_name = module_name
        self.level = level
        self.resolved_path = resolved_path

    def __lt__(self, other):
        # English: Define less-than for sorting based on module_name
        # 日本語: module_name に基づくソートのための less-than を定義
        return self.module_name < other.module_name