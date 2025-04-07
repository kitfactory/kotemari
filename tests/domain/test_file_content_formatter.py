import pytest
from pathlib import Path
from kotemari.domain.file_content_formatter import BasicFileContentFormatter

@pytest.fixture
def formatter():
    """
    Provides an instance of BasicFileContentFormatter.
    BasicFileContentFormatterのインスタンスを提供します。
    """
    return BasicFileContentFormatter()

def test_format_single_file(formatter: BasicFileContentFormatter):
    """
    Tests formatting content from a single file.
    単一ファイルのコンテンツのフォーマットをテストします。
    """
    file_path = Path("/path/to/file1.py")
    content = "print('Hello')"
    file_contents = {file_path: content}
    expected_header = f"# --- File: {file_path.name} ---"
    expected_output = f"{expected_header}\n{content}"
    assert formatter.format_content(file_contents) == expected_output

def test_format_multiple_files(formatter: BasicFileContentFormatter):
    """
    Tests formatting content from multiple files, ensuring correct order and separation.
    複数ファイルのコンテンツのフォーマットをテストし、正しい順序と区切りを確認します。
    """
    file1_path = Path("/path/to/z_file.py") # Test sorting
    file2_path = Path("/path/to/a_file.py")
    content1 = "import os"
    content2 = "def func():\n    pass"
    file_contents = {file1_path: content1, file2_path: content2}

    header1 = f"# --- File: {file1_path.name} ---"
    header2 = f"# --- File: {file2_path.name} ---"

    block1 = f"{header1}\n{content1}"
    block2 = f"{header2}\n{content2}"
    expected_output = f"{block2}\n\n{block1}"
    assert formatter.format_content(file_contents) == expected_output

def test_format_empty_content(formatter: BasicFileContentFormatter):
    """
    Tests formatting when one of the files has empty content.
    ファイルの一つが空のコンテンツを持つ場合のフォーマットをテストします。
    """
    file1_path = Path("/path/file1.py")
    file2_path = Path("/path/empty.py")
    content1 = "Data"
    content2 = "" # Empty content
    file_contents = {file1_path: content1, file2_path: content2}

    header1 = f"# --- File: {file1_path.name} ---"
    header2 = f"# --- File: {file2_path.name} ---"

    block1 = f"{header1}\n{content1}"
    block2 = f"{header2}\n{content2}"
    expected_output = f"{block2}\n\n{block1}"
    assert formatter.format_content(file_contents) == expected_output

def test_format_no_files(formatter: BasicFileContentFormatter):
    """
    Tests formatting with an empty input dictionary.
    空の入力辞書でのフォーマットをテストします。
    """
    file_contents = {}
    expected_output = ""
    assert formatter.format_content(file_contents) == expected_output

def test_format_content_with_trailing_newline(formatter: BasicFileContentFormatter):
    """
    Tests formatting behavior regardless of trailing newlines in content.
    コンテンツの末尾の改行に関係なく、フォーマットの動作をテストします。
    """
    file1_path = Path("/a.py")
    file2_path = Path("/b.py")
    content1 = "line1\nline2\n" # Ends with newline
    content2 = "line3"
    file_contents = {file1_path: content1, file2_path: content2}

    header1 = f"# --- File: {file1_path.name} ---"
    header2 = f"# --- File: {file2_path.name} ---"

    block1 = f"{header1}\n{content1}"
    block2 = f"{header2}\n{content2}"
    expected_output = f"{block1}\n\n{block2}"
    assert formatter.format_content(file_contents) == expected_output 