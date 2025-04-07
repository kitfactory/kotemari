# tests/service/test_ast_parser.py
import pytest
from pathlib import Path
import textwrap

from kotemari.service.ast_parser import AstParser
from kotemari.domain.dependency_info import DependencyInfo

@pytest.fixture
def parser() -> AstParser:
    """Provides an AstParser instance for tests."""
    return AstParser()

# --- Test Cases ---

def test_parse_simple_imports(parser: AstParser):
    """Tests parsing basic 'import module' statements."""
    content = textwrap.dedent("""
    import os
    import sys
    import logging as log
    """)
    file_path = Path("/fake/simple.py")
    expected = sorted([
        DependencyInfo("os"),
        DependencyInfo("sys"),
        DependencyInfo("logging"),
    ])
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_from_imports(parser: AstParser):
    """Tests parsing 'from module import name' statements."""
    content = textwrap.dedent("""
    from pathlib import Path
    from collections import defaultdict, OrderedDict
    from math import sqrt as square_root
    """)
    file_path = Path("/fake/from_import.py")
    expected = sorted([
        DependencyInfo("pathlib"),
        DependencyInfo("collections"),
        DependencyInfo("math"),
    ])
    # Note: The current parser extracts the module 'math', not 'sqrt' or 'square_root'
    # 注意: 現在のパーサーはモジュール 'math' を抽出し、'sqrt' や 'square_root' は抽出しません
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_relative_imports(parser: AstParser):
    """Tests parsing various relative imports."""
    content = textwrap.dedent("""
    from . import helper
    from .models import User
    from .. import utils
    from ..services import auth_service
    from ...common import constants
    """)
    file_path = Path("/app/core/logic.py")
    expected = [
        DependencyInfo("."),
        DependencyInfo(".."),
        DependencyInfo("...common"),
        DependencyInfo(".models"),
        DependencyInfo("..services"),
    ]
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_mixed_imports(parser: AstParser):
    """Tests parsing a mix of import types."""
    content = textwrap.dedent("""
    import json
    from os import path
    from . import config
    import requests as req
    from ..utils import logger
    """)
    file_path = Path("/app/main.py")
    expected = [
        DependencyInfo("."),
        DependencyInfo("..utils"),
        DependencyInfo("json"),
        DependencyInfo("os"),
        DependencyInfo("requests"),
    ]
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_imports_inside_code(parser: AstParser):
    """Tests that imports inside functions/classes are ignored (module-level only)."""
    content = textwrap.dedent("""
    import os # Top-level

    def my_func():
        import sys # Inside function
        from pathlib import Path # Inside function
        print("Hello")

    class MyClass:
        import datetime # Inside class (unusual but valid syntax)

        def method(self):
            from collections import deque # Inside method
            pass
    """)
    file_path = Path("/fake/inner_imports.py")
    expected = [
        DependencyInfo("datetime"), # Class-level import
        DependencyInfo("os"),      # Top-level import
    ]
    # Note: The current implementation focuses on top-level and class-level imports found by ast.NodeVisitor
    # 注意: 現在の実装は ast.NodeVisitor によって見つけられるトップレベルおよびクラスレベルのインポートに焦点を当てています
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_no_imports(parser: AstParser):
    """Tests parsing a file with no import statements."""
    content = textwrap.dedent("""
    print("Hello, world!")
    def greet():
        return "Hi"
    """)
    file_path = Path("/fake/no_imports.py")
    expected = []
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_empty_file(parser: AstParser):
    """Tests parsing an empty file."""
    content = ""
    file_path = Path("/fake/empty.py")
    expected = []
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_syntax_error(parser: AstParser):
    """Tests that parsing a file with syntax errors raises SyntaxError."""
    content = "import os\ndef func(" # Incomplete function definition
    file_path = Path("/fake/syntax_error.py")
    with pytest.raises(SyntaxError):
        parser.parse_dependencies(content, file_path)

def test_import_star(parser: AstParser):
    """Tests 'from module import *'."""
    content = textwrap.dedent("""
    from os import *
    """)
    file_path = Path("/fake/import_star.py")
    # The current visitor implementation extracts the module name 'os'
    # 現在のビジター実装はモジュール名 'os' を抽出します
    expected = [DependencyInfo("os")]
    assert parser.parse_dependencies(content, file_path) == expected

def test_parse_complex_from_import(parser: AstParser):
    """Tests complex 'from' imports like 'from a.b.c import d'."""
    content = textwrap.dedent("""
    from concurrent.futures import ThreadPoolExecutor
    import my_package.sub_module
    """)
    file_path = Path("/fake/complex_from.py")
    expected = sorted([
        DependencyInfo("concurrent.futures"),
        DependencyInfo("my_package.sub_module"),
    ])
    assert parser.parse_dependencies(content, file_path) == expected 