# src/kotemari/service/ast_parser.py
import ast
import logging
from pathlib import Path
from typing import List, Set

from ..domain.dependency_info import DependencyInfo

logger = logging.getLogger(__name__)

class _ImportVisitor(ast.NodeVisitor):
    """
    An AST NodeVisitor that collects imported module names.
    インポートされたモジュール名を収集する AST NodeVisitor。
    """
    def __init__(self, file_path: Path):
        self.imports: Set[str] = set()
        self.file_path = file_path # Needed for potential relative import resolution later

    def visit_Import(self, node: ast.Import):
        """
        Visits ast.Import nodes (e.g., import os, sys).
        ast.Import ノード（例: import os, sys）を訪問します。
        """
        for alias in node.names:
            self.imports.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """
        Visits ast.ImportFrom nodes (e.g., from os import path).
        ast.ImportFrom ノード（例: from os import path）を訪問します。

        Handles both absolute and relative imports. Level indicates relative level:
        0 for absolute, 1 for '.', 2 for '..', etc.
        絶対インポートと相対インポートの両方を処理します。level は相対レベルを示します:
        0 は絶対、1 は '.'、2 は '..' など。
        """
        module_name = ""
        if node.module:
            if node.level == 0:
                module_name = node.module
            else:
                relative_prefix = "." * node.level
                module_name = relative_prefix + (node.module if node.module else "")
        else:
            # When no module is specified, use plain relative import (e.g. "from . import helper")
            module_name = "." * node.level
        if module_name:
            logger.debug(f"Adding import: {module_name}")  # Debug: log the dependency being added
            self.imports.add(module_name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Do not call self.generic_visit(node) to prevent visiting inside functions
        # 関数内部への訪問を防ぐために self.generic_visit(node) を呼び出さない
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # Do not call self.generic_visit(node) to prevent visiting inside async functions
        # 非同期関数内部への訪問を防ぐために self.generic_visit(node) を呼び出さない
        pass

class AstParser:
    """
    Parses Python source code using the 'ast' module to extract information
    like dependencies (imports).
    'ast' モジュールを使用して Python ソースコードを解析し、依存関係（インポート）などの情報を抽出します。
    """

    def parse_dependencies(self, content: str, file_path: Path) -> List[DependencyInfo]:
        """
        Parses the given Python code content to extract module dependencies.
        指定された Python コードの内容を解析し、モジュールの依存関係を抽出します。

        Args:
            content: The Python source code as a string.
                     文字列としての Python ソースコード。
            file_path: The path to the file being parsed (used for context, e.g., error messages).
                       解析対象ファイルのパス（コンテキスト、例: エラーメッセージに使用）。

        Returns:
            A list of DependencyInfo objects representing the imported modules.
            インポートされたモジュールを表す DependencyInfo オブジェクトのリスト。
            Returns an empty list if parsing fails or no imports are found.
            解析に失敗した場合やインポートが見つからない場合は空のリストを返します。

        Raises:
            SyntaxError: If the content has syntax errors that prevent parsing.
                         内容に解析を妨げる構文エラーがある場合。
        """
        try:
            tree = ast.parse(content, filename=str(file_path))
            visitor = _ImportVisitor(file_path)
            visitor.visit(tree)
            
            # Updated sorting logic considering internal vs external dependencies
            def sort_key(module_name: str):
                PROJECT_NAME = "kotemari"
                if module_name.startswith('.'):
                    num_dots = 0
                    for c in module_name:
                        if c == '.':
                            num_dots += 1
                        else:
                            break
                    suffix = module_name[num_dots:]
                    if not suffix:
                        # Plain relative import: key = (0, 0, num_dots, "")
                        return (0, 0, num_dots, "")
                    else:
                        # Relative import with module name: key = (0, 1, suffix, 0)
                        return (0, 1, suffix, 0)
                else:
                    if module_name.startswith(PROJECT_NAME):
                        # Internal absolute import: key = (0, 2, module_name, "")
                        return (0, 2, module_name, "")
                    else:
                        # External absolute import: key = (1, 0, module_name, "")
                        return (1, 0, module_name, "")
            
            sorted_imports = sorted(list(visitor.imports), key=sort_key)
            dependencies = [DependencyInfo(module_name=name) for name in sorted_imports]
            return dependencies
        except SyntaxError as e:
            logger.error(f"Syntax error parsing {file_path}: {e}")
            # Re-raise the original SyntaxError to indicate parsing failure
            # 元の SyntaxError を再発生させて解析の失敗を示します
            raise e
        except Exception as e:
            # Catch other potential errors during parsing/visiting
            # 解析/訪問中の他の潜在的なエラーをキャッチします
            logger.error(f"Error parsing dependencies in {file_path}: {e}", exc_info=True)
            return [] # Return empty list on unexpected errors 