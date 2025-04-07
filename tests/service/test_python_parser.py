import pytest
from pathlib import Path
import textwrap

from kotemari.service.python_parser import PythonParser
from kotemari.domain.parsed_python_info import ParsedPythonInfo

@pytest.fixture
def parser() -> PythonParser:
    return PythonParser()

def test_parse_simple_file(parser: PythonParser):
    """
    Tests parsing a simple Python file with basic elements.
    基本的な要素を持つ単純な Python ファイルの解析をテストします。
    """
    content = textwrap.dedent("""
    import os
    from pathlib import Path
    import sys as system

    # This is a comment

    class MyClass:
        def __init__(self, value):
            self.value = value

        def method_a(self):
            print("Method A")

    def my_function(x, y):
        '''A simple function.'''
        return x + y

    CONSTANT = 10
    result = my_function(5, 3)
    instance = MyClass(result)
    print("Hello")
    """)
    file_path = Path("/fake/simple_module.py")

    parsed_info = parser.parse(content, file_path)

    assert isinstance(parsed_info, ParsedPythonInfo)
    assert parsed_info.file_path == file_path
    assert parsed_info.imports == sorted(['os', 'pathlib.Path', 'sys'])
    assert parsed_info.defined_classes == ['MyClass']
    # Note: Inner methods/functions are not extracted by _extract_definitions
    # 注意: 内側のメソッド/関数は _extract_definitions では抽出されません
    assert parsed_info.defined_functions == ['my_function']
    # Extracts top-level calls
    # トップレベルの呼び出しを抽出します
    assert parsed_info.top_level_calls == sorted(['print'])
    assert parsed_info.docstring is None # No module docstring

def test_parse_with_docstring(parser: PythonParser):
    """
    Tests parsing a file with a module docstring.
    モジュールのドキュメント文字列を持つファイルの解析をテストします。
    """
    content = textwrap.dedent("""
    \"\"\"This is the module docstring.\"\"\"
    import logging

    def func():
        pass
    """)
    file_path = Path("/fake/docstring_module.py")

    parsed_info = parser.parse(content, file_path)

    assert parsed_info.docstring == "This is the module docstring."
    assert parsed_info.imports == ['logging']
    assert parsed_info.defined_functions == ['func']

def test_parse_relative_imports(parser: PythonParser):
    """
    Tests parsing different types of relative imports.
    さまざまな種類の相対インポートの解析をテストします。
    """
    content = textwrap.dedent("""
    from . import helper
    from .models import User
    from .. import utils
    from ..services import auth_service
    from ...common import constants
    """)
    file_path = Path("/app/core/logic.py")

    parsed_info = parser.parse(content, file_path)

    # Note: Representation of relative imports might need adjustment based on desired use case.
    # 注意: 相対インポートの表現は、望ましいユースケースに基づいて調整が必要になる場合があります。
    expected_imports = sorted([
        'helper',         # from . import helper
        'models.User',    # from .models import User
        'utils',          # from .. import utils
        'services.auth_service', # from ..services import auth_service
        'common.constants' # from ...common import constants
    ])
    assert parsed_info.imports == expected_imports

def test_parse_empty_file(parser: PythonParser):
    """
    Tests parsing an empty file.
    空のファイルの解析をテストします。
    """
    content = ""
    file_path = Path("/fake/empty.py")
    parsed_info = parser.parse(content, file_path)

    assert parsed_info.file_path == file_path
    assert parsed_info.imports == []
    assert parsed_info.defined_classes == []
    assert parsed_info.defined_functions == []
    assert parsed_info.top_level_calls == []
    assert parsed_info.docstring is None

def test_parse_syntax_error(parser: PythonParser):
    """
    Tests that parsing a file with syntax errors raises SyntaxError.
    構文エラーのあるファイルの解析が SyntaxError を発生させることをテストします。
    """
    content = "def func("
    file_path = Path("/fake/syntax_error.py")

    with pytest.raises(SyntaxError):
        parser.parse(content, file_path)

def test_parse_async_def(parser: PythonParser):
    """
    Tests parsing async function definitions.
    非同期関数定義の解析をテストします。
    """
    content = textwrap.dedent("""
    async def my_async_func():
        pass

    class AsyncClass:
        async def async_method(self):
            pass
    """)
    file_path = Path("/fake/async_module.py")
    parsed_info = parser.parse(content, file_path)

    assert parsed_info.defined_functions == ['my_async_func']
    assert parsed_info.defined_classes == ['AsyncClass']

def test_parse_complex_calls(parser: PythonParser):
    """ Tests parsing of more complex top-level calls. """
    content = textwrap.dedent("""
    import os
    from my_module import MyClass

    result = os.path.join('a', 'b')
    instance = MyClass().do_something(value=1)
    print(f"Result: {result}")
    """)
    file_path = Path("/fake/complex_calls.py")
    parsed_info = parser.parse(content, file_path)

    # Expecting only direct calls in Expr context at top level
    # トップレベルの Expr コンテキストでの直接呼び出しのみを期待します
    assert parsed_info.top_level_calls == sorted(['print'])
    assert parsed_info.imports == sorted(['os', 'my_module.MyClass']) 