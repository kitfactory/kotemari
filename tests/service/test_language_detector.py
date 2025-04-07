import pytest
from pathlib import Path

from kotemari.service.language_detector import LanguageDetector, DEFAULT_EXTENSION_TO_LANGUAGE_MAP

# Fixture for the default detector
@pytest.fixture
def detector() -> LanguageDetector:
    return LanguageDetector()

# --- Test detect_language --- #

@pytest.mark.parametrize(
    "filename, expected_language",
    [
        ("main.py", "Python"),
        ("script.js", "JavaScript"),
        ("Component.ts", "TypeScript"),
        ("style.css", "CSS"),
        ("README.md", "Markdown"),
        ("config.yaml", "YAML"),
        ("settings.yml", "YAML"),
        ("document.txt", "Text"),
        ("archive.tar.gz", None), # Unknown extension
        ("no_extension", None),    # No extension
        (".bashrc", None),         # Hidden file with known extension, but map uses suffix
                                  # 既知の拡張子を持つ隠しファイルですが、マップはサフィックスを使用します
                                  # Let's test explicit filename matching
                                  # 明示的なファイル名マッチングをテストしましょう
        ("Dockerfile", "Dockerfile"),
        ("MyDockerfile", None), # Case sensitive filename match test (depends on map keys)
                                # 大文字小文字を区別するファイル名マッチングテスト（マップキーに依存）
        ("image.JPG", None),     # Default map has lowercase keys, input is lowercased
                                # デフォルトマップは小文字のキーを持ち、入力は小文字化されます
                                # Re-check: detector lowercases input suffix.
                                # 再確認：検出器は入力サフィックスを小文字化します。
        ("image.JPG", None),     # Map has no ".jpg"
        ("script.pyw", None),    # Map has no ".pyw"
    ]
)
def test_detect_language_default_map(detector: LanguageDetector, filename: str, expected_language: str | None):
    """
    Tests language detection with the default extension map.
    デフォルトの拡張子マップで言語検出をテストします。
    """
    # Create a dummy Path object
    # ダミーの Path オブジェクトを作成します
    dummy_path = Path(f"/fake/dir/{filename}")
    language = detector.detect_language(dummy_path)
    assert language == expected_language

# --- Test with custom map --- #

def test_detect_language_custom_map():
    """
    Tests language detection with a custom extension map.
    カスタム拡張子マップで言語検出をテストします。
    """
    custom_map = {
        ".script": "CustomScript",
        ".config": "Configuration",
        "Makefile": "Makefile", # Filename match
        ".JPG": "JPEG Image" # Uppercase key test
    }
    custom_detector = LanguageDetector(extension_map=custom_map)

    assert custom_detector.detect_language(Path("run.script")) == "CustomScript"
    assert custom_detector.detect_language(Path("settings.config")) == "Configuration"
    assert custom_detector.detect_language(Path("Makefile")) == "Makefile"
    assert custom_detector.detect_language(Path("Image.JPG")) == "JPEG Image" # Input lowercased, map keys lowercased on init
                                                                              # 入力は小文字化、マップキーは初期化時に小文字化
    assert custom_detector.detect_language(Path("main.py")) is None # Default map not used
                                                                 # デフォルトマップは使用されない 