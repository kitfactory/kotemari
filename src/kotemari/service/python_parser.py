"""
Service for parsing Python source code using the AST module.
AST モジュールを使用して Python ソースコードを解析するサービス。
"""
import ast
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from ..domain.parsed_python_info import ParsedPythonInfo

logger = logging.getLogger(__name__)

class PythonParser:
    """
    Parses a Python file content using the `ast` module to extract structural information.
    `ast` モジュールを使用して Python ファイルの内容を解析し、構造情報を抽出します。
    """

    def parse(self, file_content: str, file_path: Path) -> ParsedPythonInfo:
        """
        Parses the given Python file content.
        指定された Python ファイルの内容を解析します。

        Args:
            file_content (str): The content of the Python file.
                                Python ファイルの内容。
            file_path (Path): The path to the Python file (used for context and reporting).
                              Python ファイルへのパス (コンテキストとレポート用)。

        Returns:
            ParsedPythonInfo: An object containing the parsed information.
                              解析された情報を含むオブジェクト。

        Raises:
            SyntaxError: If the file content has syntax errors that prevent AST parsing.
                         AST 解析を妨げる構文エラーがファイルコンテンツにある場合。
        """
        logger.debug(f"Parsing Python file: {file_path}")
        try:
            tree = ast.parse(file_content, filename=str(file_path))
        except SyntaxError as e:
            logger.error(f"Syntax error parsing {file_path}: {e}")
            raise # Re-raise the syntax error
        except Exception as e:
            # Catch other potential errors during parsing
            # 解析中の他の潜在的なエラーをキャッチします
            logger.error(f"Unexpected error parsing AST for {file_path}: {e}", exc_info=True)
            # Return an empty structure or raise a custom error?
            # 空の構造を返すか、カスタムエラーを発生させますか？
            # For now, let's return a minimal info object to avoid crashing consumers.
            # 今のところ、コンシューマのクラッシュを避けるために最小限の情報オブジェクトを返しましょう。
            return ParsedPythonInfo(file_path=file_path)

        imports = self._extract_imports(tree)
        classes, functions = self._extract_definitions(tree)
        calls = self._extract_calls(tree)
        docstring = self._extract_docstring(tree)

        parsed_info = ParsedPythonInfo(
            file_path=file_path,
            imports=imports,
            defined_classes=classes,
            defined_functions=functions,
            top_level_calls=calls,
            docstring=docstring
        )
        logger.debug(f"Finished parsing {file_path}. Imports: {len(imports)}, Classes: {len(classes)}, Functions: {len(functions)}, Calls: {len(calls)}")
        return parsed_info

    def _extract_imports(self, node: ast.AST) -> List[str]:
        """Extracts import statements from the AST."""
        imports = []
        for item in ast.walk(node):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    imports.append(alias.name)
            elif isinstance(item, ast.ImportFrom):
                module = item.module if item.module else ''
                for alias in item.names:
                    # Handle relative imports (level > 0)
                    # 相対インポートを処理します (level > 0)
                    prefix = '.' * item.level if item.level > 0 else ''
                    imported_name = f"{prefix}{module}.{alias.name}" if module else f"{prefix}{alias.name}"
                    # Simplify common case like 'from . import foo'
                    # '.foo' のような一般的なケースを単純化します
                    if imported_name.startswith('.') and '.' not in imported_name[1:] and module is None:
                         imported_name = f".{alias.name}"
                    elif module:
                         imported_name = f"{prefix}{module}.{alias.name}"
                    else: # from . import name
                         imported_name = f"{prefix}{alias.name}"

                    # Clean up leading dots if module is present in relative import
                    # Note: This might need refinement based on how relative imports should be represented.
                    # 注意: これは相対インポートをどのように表現すべきかに基づいて改良が必要になる場合があります。
                    # Example: from ..utils import helper -> ..utils.helper
                    if module and item.level > 0:
                        imported_name = f"{'.' * item.level}{module}.{alias.name}"
                    elif item.level > 0: # from . import name
                        imported_name = f"{'.' * item.level}{alias.name}"
                    # else: absolute import like 'import os' or 'from os import path'

                    imports.append(imported_name.strip('.'))
        # Return unique imports, sorted
        # 一意のインポートをソートして返します
        return sorted(list(set(imports)))

    def _extract_definitions(self, node: ast.AST) -> Tuple[List[str], List[str]]:
        """Extracts class and function definitions from the top level of the AST."""
        classes = []
        functions = []
        # We only look at the direct children of the Module node (top level)
        # Module ノードの直接の子のみを見ます（トップレベル）
        if isinstance(node, ast.Module):
            for item in node.body:
                if isinstance(item, ast.ClassDef):
                    classes.append(item.name)
                elif isinstance(item, ast.FunctionDef):
                    functions.append(item.name)
                elif isinstance(item, ast.AsyncFunctionDef):
                    functions.append(item.name)
        return sorted(classes), sorted(functions)

    def _extract_calls(self, node: ast.AST) -> List[str]:
        """Extracts function calls made at the top level of the AST."""
        calls = []
        # We only look at the direct children of the Module node (top level)
        # Module ノードの直接の子のみを見ます（トップレベル）
        if isinstance(node, ast.Module):
            for item in node.body:
                # Look for top-level expressions that are function calls
                # 関数呼び出しであるトップレベルの式を探します
                if isinstance(item, ast.Expr) and isinstance(item.value, ast.Call):
                    func = item.value.func
                    call_name = self._get_call_name(func)
                    if call_name:
                        calls.append(call_name)
        return sorted(list(set(calls)))

    def _get_call_name(self, func_node: ast.expr) -> Optional[str]:
        """Helper to get the name of the function being called."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            # Recursively build the full attribute chain (e.g., os.path.join)
            # 完全な属性チェーンを再帰的に構築します (例: os.path.join)
            obj_name = self._get_call_name(func_node.value)
            if obj_name:
                return f"{obj_name}.{func_node.attr}"
        # Add other cases if needed (e.g., calls on subscripted objects)
        # 必要に応じて他のケースを追加します (例: 添え字付きオブジェクトでの呼び出し)
        return None # Cannot determine name

    def _extract_docstring(self, node: ast.AST) -> Optional[str]:
        """Extracts the module-level docstring."""
        if isinstance(node, ast.Module) and node.body:
            first_node = node.body[0]
            if isinstance(first_node, ast.Expr) and isinstance(first_node.value, ast.Constant):
                 if isinstance(first_node.value.value, str):
                      return ast.get_docstring(node, clean=False) # Keep indentation etc.
        return None 