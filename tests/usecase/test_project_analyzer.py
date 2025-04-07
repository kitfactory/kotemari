import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import datetime
import logging

from kotemari.usecase.project_analyzer import ProjectAnalyzer
from kotemari.domain.file_info import FileInfo
from kotemari.domain.project_config import ProjectConfig
from kotemari.domain.dependency_info import DependencyInfo
from kotemari.utility.path_resolver import PathResolver
# Import other necessary classes if needed for setup or mocking
# 設定やモックに必要な場合は、他の必要なクラスをインポートします
from kotemari.gateway.file_system_accessor import FileSystemAccessor
from kotemari.service.ignore_rule_processor import IgnoreRuleProcessor
from kotemari.service.hash_calculator import HashCalculator
from kotemari.service.language_detector import LanguageDetector
from kotemari.service.ast_parser import AstParser
from kotemari.usecase.config_manager import ConfigManager

# Fixture for a basic PathResolver
@pytest.fixture
def path_resolver() -> PathResolver:
    return PathResolver()

# Fixture to create a test project structure
@pytest.fixture
def setup_analyzer_test_project(tmp_path: Path):
    # Structure:
    # tmp_path/test_proj/
    #   .gitignore (ignore *.log, venv/)
    #   .kotemari.yml (empty for now)
    #   main.py (Python)
    #   utils.py (Python)
    #   data.txt (Text)
    #   README.md (Markdown)
    #   venv/
    #     script.py
    #   output.log
    #   src/
    #     module.js (JavaScript)

    proj_root = tmp_path / "test_proj"
    proj_root.mkdir()

    (proj_root / ".gitignore").write_text("*.log\nvenv/\n__pycache__/\nsyntax_error.py", encoding='utf-8')
    (proj_root / ".kotemari.yml").touch() # Empty config file

    (proj_root / "main.py").write_text("import os\nprint('main')", encoding='utf-8')
    (proj_root / "utils.py").write_text("from pathlib import Path\ndef helper(): pass", encoding='utf-8')
    (proj_root / "data.txt").write_text("some data", encoding='utf-8')
    (proj_root / "README.md").write_text("# Test Project", encoding='utf-8')
    (proj_root / "syntax_error.py").write_text("def func(", encoding='utf-8')

    venv_dir = proj_root / "venv"
    venv_dir.mkdir()
    (venv_dir / "script.py").touch()

    (proj_root / "output.log").touch()

    src_dir = proj_root / "src"
    src_dir.mkdir()
    (src_dir / "module.js").write_text("console.log('hello');", encoding='utf-8')

    return proj_root

# --- Test ProjectAnalyzer Initialization --- #

def test_project_analyzer_init_creates_dependencies(setup_analyzer_test_project, path_resolver):
    """
    Tests if ProjectAnalyzer correctly initializes its dependencies if they are not provided.
    依存関係が提供されない場合に、ProjectAnalyzer がそれらを正しく初期化するかをテストします。
    """
    analyzer = ProjectAnalyzer(setup_analyzer_test_project, path_resolver=path_resolver)

    assert analyzer.project_root == path_resolver.resolve_absolute(setup_analyzer_test_project)
    assert isinstance(analyzer.path_resolver, PathResolver)
    assert isinstance(analyzer.config_manager, ConfigManager)
    assert isinstance(analyzer.config, ProjectConfig)
    assert isinstance(analyzer.fs_accessor, FileSystemAccessor)
    assert isinstance(analyzer.ignore_processor, IgnoreRuleProcessor)
    assert isinstance(analyzer.hash_calculator, HashCalculator)
    assert isinstance(analyzer.language_detector, LanguageDetector)
    assert isinstance(analyzer.ast_parser, AstParser)

def test_project_analyzer_init_uses_injected_dependencies(setup_analyzer_test_project):
    """
    Tests if ProjectAnalyzer uses dependencies injected during initialization.
    初期化中に注入された依存関係を ProjectAnalyzer が使用するかをテストします。
    """
    # Create mock objects for dependencies
    # 依存関係のモックオブジェクトを作成します
    mock_pr = MagicMock(spec=PathResolver)
    mock_cm = MagicMock(spec=ConfigManager)
    mock_cfg = MagicMock(spec=ProjectConfig)
    mock_fs = MagicMock(spec=FileSystemAccessor)
    mock_ip = MagicMock(spec=IgnoreRuleProcessor)
    mock_hc = MagicMock(spec=HashCalculator)
    mock_ld = MagicMock(spec=LanguageDetector)
    mock_ap = MagicMock(spec=AstParser)

    # Configure mocks to return expected values if needed
    # 必要に応じて、期待される値を返すようにモックを設定します
    mock_pr.resolve_absolute.return_value = setup_analyzer_test_project # Simplified mock
    mock_cm.get_config.return_value = mock_cfg

    analyzer = ProjectAnalyzer(
        setup_analyzer_test_project,
        path_resolver=mock_pr,
        config_manager=mock_cm,
        fs_accessor=mock_fs,
        ignore_processor=mock_ip,
        hash_calculator=mock_hc,
        language_detector=mock_ld,
        ast_parser=mock_ap
    )

    # Assert that the injected mocks are used
    # 注入されたモックが使用されていることを表明します
    assert analyzer.path_resolver is mock_pr
    assert analyzer.config_manager is mock_cm
    assert analyzer.config is mock_cfg
    assert analyzer.fs_accessor is mock_fs
    assert analyzer.ignore_processor is mock_ip
    assert analyzer.hash_calculator is mock_hc
    assert analyzer.language_detector is mock_ld
    assert analyzer.ast_parser is mock_ap
    mock_pr.resolve_absolute.assert_called_once_with(setup_analyzer_test_project)
    mock_cm.get_config.assert_called_once()

# --- Test ProjectAnalyzer analyze Method --- #

@patch('kotemari.service.hash_calculator.HashCalculator.calculate_file_hash')
def test_analyze_integration(mock_calc_hash, setup_analyzer_test_project, path_resolver):
    """
    Tests the overall analyze process, integrating scanning, ignoring, hashing, and language detection.
    スキャン、無視、ハッシュ化、言語検出を統合して、全体的な分析プロセスをテストします。
    """
    # Let hash calculator return predictable values
    # ハッシュ計算機に予測可能な値を返させます
    mock_calc_hash.side_effect = lambda path, **kwargs: f"hash_for_{path.name}"

    analyzer = ProjectAnalyzer(setup_analyzer_test_project, path_resolver=path_resolver)
    results = analyzer.analyze()

    # Expected files (relative paths for easier assertion)
    # 期待されるファイル（アサーションを容易にするための相対パス）
    # venv/ and *.log should be ignored by .gitignore
    # venv/ と *.log は .gitignore によって無視されるはずです
    expected_relative_paths = {
        ".gitignore",
        ".kotemari.yml",
        "main.py",
        "utils.py",
        "data.txt",
        "README.md",
        "src/module.js",
    }

    found_relative_paths = {fi.path.relative_to(setup_analyzer_test_project).as_posix() for fi in results}

    assert found_relative_paths == expected_relative_paths
    assert len(results) == len(expected_relative_paths)

    # Check details for a few files
    # いくつかのファイルの詳細を確認します
    file_info_map = {fi.path.name: fi for fi in results}

    # main.py
    assert "main.py" in file_info_map
    main_fi = file_info_map["main.py"]
    assert isinstance(main_fi, FileInfo)
    assert main_fi.path.is_absolute()
    assert main_fi.language == "Python"
    assert main_fi.hash == "hash_for_main.py"
    assert isinstance(main_fi.mtime, datetime.datetime)
    assert main_fi.size > 0

    # module.js
    assert "module.js" in file_info_map
    js_fi = file_info_map["module.js"]
    assert js_fi.language == "JavaScript"
    assert js_fi.hash == "hash_for_module.js"

    # data.txt
    assert "data.txt" in file_info_map
    txt_fi = file_info_map["data.txt"]
    assert txt_fi.language == "Text"
    assert txt_fi.hash == "hash_for_data.txt"

    # .gitignore
    assert ".gitignore" in file_info_map
    git_fi = file_info_map[".gitignore"]
    assert git_fi.language is None # No specific language for .gitignore by default
                                 # デフォルトでは .gitignore に特定の言語はありません
    assert git_fi.hash == "hash_for_.gitignore"

    # Check that hash calculator was called for each non-ignored file
    # 無視されなかった各ファイルに対してハッシュ計算機が呼び出されたことを確認します
    assert mock_calc_hash.call_count == len(expected_relative_paths)

def test_analyze_project_not_found(tmp_path, path_resolver):
    """
    Tests analyzing a non-existent project directory.
    存在しないプロジェクトディレクトリを分析するテスト。
    """
    non_existent_root = tmp_path / "non_existent_project"
    analyzer = ProjectAnalyzer(non_existent_root, path_resolver=path_resolver)
    results = analyzer.analyze()
    assert results == [] # Should return empty list

def test_analyze_integration_with_dependency_parsing(setup_analyzer_test_project, path_resolver):
    """
    Tests the overall analyze process, including Python dependency extraction.
    Python 依存関係抽出を含む、全体的な分析プロセスをテストします。
    """
    proj_root = setup_analyzer_test_project
    main_py_path = proj_root / "main.py"
    utils_py_path = proj_root / "utils.py"
    js_path = proj_root / "src" / "module.js"

    # --- Mocks Setup ---
    mock_fs_accessor = MagicMock(spec=FileSystemAccessor)
    mock_hash_calculator = MagicMock(spec=HashCalculator)
    mock_language_detector = MagicMock(spec=LanguageDetector)
    mock_ast_parser = MagicMock(spec=AstParser)
    mock_ignore_processor = MagicMock(spec=IgnoreRuleProcessor)
    mock_config_manager = MagicMock(spec=ConfigManager)
    mock_config = MagicMock(spec=ProjectConfig)

    # Mock ConfigManager behavior
    mock_config_manager.get_config.return_value = mock_config

    # Mock IgnoreProcessor behavior (simplified: returns a function that ignores nothing for this test)
    mock_ignore_processor.get_ignore_function.return_value = lambda path: False

    # Mock FileSystemAccessor scan_directory to yield FileInfo objects
    # scan_directory は基本的な FileInfo (path, mtime, size) を返す想定
    # hash, language, dependencies は analyze メソッド内で設定される
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_fs_accessor.scan_directory.return_value = iter([
        FileInfo(path=proj_root / ".gitignore", mtime=now, size=10),
        FileInfo(path=proj_root / ".kotemari.yml", mtime=now, size=0),
        FileInfo(path=main_py_path, mtime=now, size=20),
        FileInfo(path=utils_py_path, mtime=now, size=30),
        FileInfo(path=proj_root / "data.txt", mtime=now, size=9),
        FileInfo(path=proj_root / "README.md", mtime=now, size=15),
        FileInfo(path=js_path, mtime=now, size=25),
        # Ignored files (syntax_error.py, output.log, venv/*) are NOT yielded by scan_directory
        # if the ignore_func works correctly (or if mocked scan doesn't yield them).
        # For this test, assume scan_directory respects ignore rules or we manually yield non-ignored.
    ])

    # Mock FileSystemAccessor read_file for Python files
    main_py_content = "import os\nprint('main')"
    utils_py_content = "from pathlib import Path\ndef helper(): pass"
    def mock_read_file(path):
        if path == main_py_path: return main_py_content
        if path == utils_py_path: return utils_py_content
        return None # Or raise error, depending on expected behavior
    mock_fs_accessor.read_file.side_effect = mock_read_file

    # Mock HashCalculator
    mock_hash_calculator.calculate_file_hash.side_effect = lambda p, **kw: f"hash_{p.name}"

    # Mock LanguageDetector
    def mock_detect_lang(path):
        if path.suffix == '.py': return 'Python'
        if path.suffix == '.js': return 'JavaScript'
        if path.suffix == '.md': return 'Markdown'
        if path.suffix == '.txt': return 'Text'
        return None
    mock_language_detector.detect_language.side_effect = mock_detect_lang

    # Mock AstParser
    main_deps = [DependencyInfo("os")]
    utils_deps = [DependencyInfo("pathlib")]
    def mock_parse_deps(content, path):
        if path == main_py_path: return main_deps
        if path == utils_py_path: return utils_deps
        return []
    mock_ast_parser.parse_dependencies.side_effect = mock_parse_deps

    # --- Analyzer Initialization with Mocks ---
    analyzer = ProjectAnalyzer(
        project_root=proj_root,
        path_resolver=path_resolver,
        config_manager=mock_config_manager,
        fs_accessor=mock_fs_accessor,
        ignore_processor=mock_ignore_processor,
        hash_calculator=mock_hash_calculator,
        language_detector=mock_language_detector,
        ast_parser=mock_ast_parser
    )

    # --- Execute ---
    results = analyzer.analyze()

    # --- Assertions ---
    assert len(results) == 7 # Number of non-ignored files yielded by mock scan

    file_info_map = {fi.path: fi for fi in results}

    # Check main.py details (including dependencies)
    assert main_py_path in file_info_map
    main_fi = file_info_map[main_py_path]
    assert main_fi.language == "Python"
    assert main_fi.hash == "hash_main.py"
    assert main_fi.dependencies == main_deps # Check dependencies

    # Check utils.py details (including dependencies)
    assert utils_py_path in file_info_map
    utils_fi = file_info_map[utils_py_path]
    assert utils_fi.language == "Python"
    assert utils_fi.hash == "hash_utils.py"
    assert utils_fi.dependencies == utils_deps # Check dependencies

    # Check js file (no dependencies expected to be parsed)
    assert js_path in file_info_map
    js_fi = file_info_map[js_path]
    assert js_fi.language == "JavaScript"
    assert js_fi.hash == "hash_module.js"
    assert js_fi.dependencies == [] # Should be default empty list

    # Check mock calls
    mock_fs_accessor.scan_directory.assert_called_once_with(proj_root, ignore_func=mock_ignore_processor.get_ignore_function())
    assert mock_hash_calculator.calculate_file_hash.call_count == 7
    assert mock_language_detector.detect_language.call_count == 7

    # Assert read_file and parse_dependencies were called only for Python files
    expected_read_calls = [call(main_py_path), call(utils_py_path)]
    mock_fs_accessor.read_file.assert_has_calls(expected_read_calls, any_order=True)
    assert mock_fs_accessor.read_file.call_count == 2

    expected_parse_calls = [
        call(main_py_content, main_py_path),
        call(utils_py_content, utils_py_path),
    ]
    mock_ast_parser.parse_dependencies.assert_has_calls(expected_parse_calls, any_order=True)
    assert mock_ast_parser.parse_dependencies.call_count == 2

def test_analyze_with_python_syntax_error(setup_analyzer_test_project, path_resolver, caplog):
    """
    Tests that analysis continues and logs a warning when a Python file has syntax errors.
    Python ファイルに構文エラーがある場合でも分析が続行され、警告がログに記録されることをテストします。
    """
    proj_root = setup_analyzer_test_project
    # syntax_error.py is created by the fixture but should be ignored by .gitignore
    # If it weren't ignored, this test would check handling during analysis.
    # Let's modify the setup to NOT ignore syntax_error.py for this specific test,
    # OR create a non-ignored file with syntax error.
    # Option 2: Create a non-ignored file.
    error_py_path = proj_root / "error_module.py"
    error_py_content = "import sys\ndef broken("
    error_py_path.write_text(error_py_content, encoding='utf-8')

    # --- Mocks Setup ---
    mock_fs_accessor = MagicMock(spec=FileSystemAccessor)
    mock_hash_calculator = MagicMock(spec=HashCalculator)
    mock_language_detector = MagicMock(spec=LanguageDetector)
    mock_ast_parser = MagicMock(spec=AstParser)
    mock_ignore_processor = MagicMock(spec=IgnoreRuleProcessor)
    mock_config_manager = MagicMock(spec=ConfigManager)
    mock_config = MagicMock(spec=ProjectConfig)

    mock_config_manager.get_config.return_value = mock_config
    mock_ignore_processor.get_ignore_function.return_value = lambda path: False # Ignore nothing

    # Yield the error file along with another valid file
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_fs_accessor.scan_directory.return_value = iter([
        FileInfo(path=proj_root / "main.py", mtime=now, size=20),
        FileInfo(path=error_py_path, mtime=now, size=20), # Include the error file
    ])

    # Mock read_file
    def mock_read_file_for_error(path):
        if path == error_py_path: return error_py_content
        if path == proj_root / "main.py": return "import os"
        return None
    mock_fs_accessor.read_file.side_effect = mock_read_file_for_error

    # Mock LanguageDetector
    mock_language_detector.detect_language.return_value = "Python" # Assume both are Python

    # Mock HashCalculator
    mock_hash_calculator.calculate_file_hash.return_value = "some_hash"

    # Mock AstParser to raise SyntaxError for the specific file
    def mock_parse_deps_with_error(content, path):
        if path == error_py_path:
            raise SyntaxError("Test Syntax Error")
        elif path == proj_root / "main.py":
            return [DependencyInfo("os")] # Valid dependency for the other file
        return []
    mock_ast_parser.parse_dependencies.side_effect = mock_parse_deps_with_error

    # --- Analyzer Initialization ---
    analyzer = ProjectAnalyzer(
        project_root=proj_root, path_resolver=path_resolver,
        config_manager=mock_config_manager, fs_accessor=mock_fs_accessor,
        ignore_processor=mock_ignore_processor, hash_calculator=mock_hash_calculator,
        language_detector=mock_language_detector, ast_parser=mock_ast_parser
    )

    # --- Execute ---
    with caplog.at_level(logging.WARNING):
        results = analyzer.analyze()

    # --- Assertions ---
    assert len(results) == 2 # Analysis should complete for both files yielded

    file_info_map = {fi.path: fi for fi in results}

    # Check the file with syntax error
    assert error_py_path in file_info_map
    error_fi = file_info_map[error_py_path]
    assert error_fi.language == "Python"
    assert error_fi.dependencies == [] # Dependencies should be empty

    # Check the valid file
    assert (proj_root / "main.py") in file_info_map
    main_fi = file_info_map[proj_root / "main.py"]
    assert main_fi.language == "Python"
    assert main_fi.dependencies == [DependencyInfo("os")] # Dependencies should be parsed

    # Check logs
    assert any("Skipping dependency parsing" in record.message and "error_module.py" in record.message for record in caplog.records)
    # Check AstParser was called for both
    assert mock_ast_parser.parse_dependencies.call_count == 2 