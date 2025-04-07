# This file makes src/kotemari a Python package 

"""
Kotemari: Project analysis and context generation library.
Kotemari: プロジェクト分析およびコンテキスト生成ライブラリ。
"""

__version__ = "0.0.1" # TODO: Keep this in sync with pyproject.toml

from .core import Kotemari

# Optionally expose other core components if needed
# 必要に応じて他のコアコンポーネントを公開します
# from .domain import FileInfo, ProjectConfig

__all__ = ["Kotemari", "__version__"] 