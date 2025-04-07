import pytest
from pathlib import Path
from kotemari.domain.parsed_python_info import ParsedPythonInfo

def test_parsed_python_info_initialization():
    """
    Tests the basic initialization and default values of ParsedPythonInfo.
    ParsedPythonInfo の基本的な初期化とデフォルト値をテストします。
    """
    file_path = Path("/path/to/some/file.py")
    info = ParsedPythonInfo(file_path=file_path)

    assert info.file_path == file_path
    assert info.imports == []
    assert info.defined_classes == []
    assert info.defined_functions == []
    assert info.top_level_calls == []
    assert info.docstring is None

def test_parsed_python_info_with_values():
    """
    Tests initializing ParsedPythonInfo with specific values.
    特定の値で ParsedPythonInfo を初期化するテストをします。
    """
    file_path = Path("/another/module.py")
    imports = ["os", "sys"]
    classes = ["MyClass"]
    functions = ["my_function", "_helper"]
    calls = ["print", "setup"]
    docstring = "This is a module docstring."

    info = ParsedPythonInfo(
        file_path=file_path,
        imports=imports,
        defined_classes=classes,
        defined_functions=functions,
        top_level_calls=calls,
        docstring=docstring
    )

    assert info.file_path == file_path
    assert info.imports == imports
    assert info.defined_classes == classes
    assert info.defined_functions == functions
    assert info.top_level_calls == calls
    assert info.docstring == docstring 