from pathlib import Path
from typing import Dict, Optional

# Simple mapping from file extensions to language names
# ファイル拡張子から言語名への簡単なマッピング
# This can be expanded significantly.
# これは大幅に拡張できます。
DEFAULT_EXTENSION_TO_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".rs": "Rust",
    ".scala": "Scala",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "LESS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".md": "Markdown",
    ".txt": "Text",
    ".sh": "Shell Script",
    ".bash": "Bash Script",
    ".zsh": "Zsh Script",
    ".sql": "SQL",
    ".r": "R",
    ".pl": "Perl",
    ".lua": "Lua",
    ".dockerfile": "Dockerfile",
    "Dockerfile": "Dockerfile", # Also match filename
}

class LanguageDetector:
    """
    Detects the programming language of a file based on its extension.
    ファイルの拡張子に基づいてプログラミング言語を検出します。
    """

    def __init__(self, extension_map: Dict[str, str] = DEFAULT_EXTENSION_TO_LANGUAGE_MAP):
        """
        Initializes the LanguageDetector.
        LanguageDetector を初期化します。

        Args:
            extension_map (Dict[str, str], optional):
                A dictionary mapping file extensions (including dot) to language names.
                Defaults to DEFAULT_EXTENSION_TO_LANGUAGE_MAP.
                ファイル拡張子（ドットを含む）を言語名にマッピングする辞書。
                デフォルトは DEFAULT_EXTENSION_TO_LANGUAGE_MAP。
        """
        # Convert keys to lowercase for case-insensitive matching
        # 大文字小文字を区別しないマッチングのためにキーを小文字に変換します
        self.extension_map = {k.lower(): v for k, v in extension_map.items()}

    def detect_language(self, file_path: Path) -> Optional[str]:
        """
        Detects the language of the file based on its extension or name.
        ファイルの拡張子または名前に基づいて言語を検出します。

        Args:
            file_path (Path): The path to the file.
                              ファイルへのパス。

        Returns:
            Optional[str]: The detected language name, or None if not recognized.
                           検出された言語名。認識されない場合は None。
        """
        file_name_lower = file_path.name.lower()
        file_suffix_lower = file_path.suffix.lower()

        # Check full filename first (e.g., Dockerfile)
        # 最初に完全なファイル名を確認します（例: Dockerfile）
        if file_name_lower in self.extension_map:
            return self.extension_map[file_name_lower]

        # Then check extension
        # 次に拡張子を確認します
        if file_suffix_lower in self.extension_map:
            return self.extension_map[file_suffix_lower]

        return None # Language not recognized based on extension/name
                    # 拡張子/名前に基づいて言語が認識されません 