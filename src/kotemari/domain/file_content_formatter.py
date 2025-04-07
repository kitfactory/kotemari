from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict

class FileContentFormatter(ABC):
    """
    Abstract base class for formatting content from multiple files into a single string.
    複数のファイルの内容を単一の文字列にフォーマットするための抽象基底クラス。
    """

    @abstractmethod
    def format_content(self, file_contents: Dict[Path, str]) -> str:
        """
        Formats the content of given files into a single string.
        指定されたファイルの内容を単一の文字列にフォーマットします。

        Args:
            file_contents: A dictionary mapping absolute file paths to their content.
                           絶対ファイルパスとその内容をマッピングする辞書。

        Returns:
            A single string containing the formatted content of all files.
            すべてのファイルのフォーマットされた内容を含む単一の文字列。
        """
        pass

class BasicFileContentFormatter(FileContentFormatter):
    """
    A basic implementation that concatenates file contents with a simple header indicating the file path.
    ファイルパスを示す単純なヘッダーを付けてファイル内容を連結する基本的な実装。
    """

    def format_content(self, file_contents: Dict[Path, str]) -> str:
        """
        Concatenates file contents, adding a header line for each file and separating entries with a blank line.
        各ファイルにヘッダー行を追加し、エントリを空行で区切ってファイル内容を連結します。

        Example:
        # --- File: path/to/file1.py ---
        content of file1

        # --- File: path/to/file2.py ---
        content of file2

        Args:
            file_contents: A dictionary mapping absolute file paths to their content.
                           絶対ファイルパスとその内容をマッピングする辞書。

        Returns:
            A single string with all file contents concatenated, headers added, and separated by blank lines.
            すべてのファイル内容が連結され、ヘッダーが追加され、空行で区切られた単一の文字列。
        """
        if not file_contents:
            return ""

        formatted_blocks: List[str] = []
        # English: Sort by path for consistent output order.
        # 日本語: 一貫した出力順序のためにパスでソートします。
        sorted_paths = sorted(file_contents.keys())

        for file_path in sorted_paths:
            content = file_contents[file_path]
            # Use Path.name for a cleaner header, showing only the filename
            # よりクリーンなヘッダーのために Path.name を使用し、ファイル名のみを表示します
            header = f"# --- File: {file_path.name} ---"
            # Create a single block for header and content
            # ヘッダーと内容の単一ブロックを作成します
            block = header + "\n" + content
            formatted_blocks.append(block)

        # English: Join all blocks with double newline characters for separation.
        # 日本語: 区切りのためにすべてのブロックを二重改行文字で結合します。
        return "\n\n".join(formatted_blocks) 