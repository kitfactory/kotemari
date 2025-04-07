import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import datetime
import logging

# Import Kotemari from the package root
# パッケージルートから Kotemari をインポートします
from kotemari import Kotemari
from kotemari.domain.file_info import FileInfo
from kotemari.domain.dependency_info import DependencyInfo
from kotemari.usecase.cache_updater import CacheUpdater
from kotemari.gateway.cache_storage import CacheStorage
from kotemari.domain.cache_metadata import CacheMetadata
from kotemari.domain.file_system_event import FileSystemEvent, FileSystemEventType

# Create a logger instance for this test module
logger = logging.getLogger(__name__)

# Configure logging for tests (optional) - Can be configured globally or via pytest options
# logging.basicConfig(level=logging.DEBUG)

# Re-use or adapt the project structure fixture from analyzer tests
# アナライザーテストからプロジェクト構造フィクスチャを再利用または適合させます
@pytest.fixture
def setup_facade_test_project(tmp_path: Path):
    proj_root = tmp_path / "facade_test_proj"
    proj_root.mkdir()

    (proj_root / ".gitignore").write_text("*.log\nvenv/\n__pycache__/\nignored.py", encoding='utf-8')
    (proj_root / ".kotemari.yml").touch() # Empty config

    (proj_root / "app.py").write_text("import os\nprint('app')", encoding='utf-8')
    (proj_root / "lib").mkdir()
    (proj_root / "lib" / "helpers.py").write_text("from . import models", encoding='utf-8')
    (proj_root / "lib" / "models.py").write_text("class Model: pass", encoding='utf-8')
    (proj_root / "data.csv").write_text("col1,col2\n1,2", encoding='utf-8')
    (proj_root / "docs").mkdir()
    (proj_root / "docs" / "index.md").write_text("# Docs", encoding='utf-8')
    (proj_root / "ignored.py").write_text("print('ignored')", encoding='utf-8')

    (proj_root / "temp.log").touch()
    (proj_root / "venv").mkdir()
    (proj_root / "venv" / "activate").touch()

    # Create files needed for specific tests (e.g., test_get_context_success)
    # 特定のテスト（例：test_get_context_success）に必要なファイルを作成します
    (proj_root / "main.py").write_text("print('hello from main')")
    (proj_root / "my_module").mkdir()
    (proj_root / "my_module" / "utils.py").write_text("def helper(): return 1")
    (proj_root / "ignored.log").write_text("log data") # Example ignored file

    logger.debug(f"Created test project structure at: {proj_root}")
    return proj_root

# Fixtures for Kotemari instances
@pytest.fixture
def kotemari_instance_empty(setup_facade_test_project):
    """
    Provides a Kotemari instance without analysis performed.
    分析が実行されていない Kotemari インスタンスを提供します。
    """
    return Kotemari(setup_facade_test_project)

@pytest.fixture
@patch('kotemari.usecase.project_analyzer.ProjectAnalyzer.analyze')
def kotemari_instance_analyzed(mock_analyze, setup_facade_test_project):
    """
    Provides a Kotemari instance that is considered analyzed (mocks analysis).
    Includes files created by setup_facade_test_project in the mock results.
    分析済みとみなされる Kotemari インスタンスを提供します（分析をモックします）。
    setup_facade_test_project で作成されたファイルをモック結果に含めます。
    """
    project_root = setup_facade_test_project
    # Mock results needed for tests using this fixture
    # Include files that are actually created by the setup fixture
    # このフィクスチャを使用するテストに必要なモック結果
    # セットアップフィクスチャによって実際に作成されるファイルを含めます
    mock_results = [
        # Files typically included in analysis mock
        # 通常分析モックに含まれるファイル
        FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=10, language="Python", hash="h1", dependencies=[]), # Added dependencies=[]
        FileInfo(path=project_root / "lib" / "helpers.py", mtime=datetime.datetime.now(), size=20, language="Python", hash="h2", dependencies=[]), # Added dependencies=[]
        FileInfo(path=project_root / "data.csv", mtime=datetime.datetime.now(), size=30, language=None, hash="h3", dependencies=[]), # Added dependencies=[]
        # Files created by setup_facade_test_project specifically for context tests
        # コンテキストテスト用に setup_facade_test_project によって特別に作成されたファイル
        FileInfo(path=project_root / "main.py", mtime=datetime.datetime.now(), size=25, language="Python", hash="h4", dependencies=[]),
        FileInfo(path=project_root / "my_module" / "utils.py", mtime=datetime.datetime.now(), size=21, language="Python", hash="h5", dependencies=[]),
    ]
    mock_analyze.return_value = mock_results

    kotemari = Kotemari(project_root)
    try:
        kotemari.analyze_project() # Perform the mocked analysis
    except Exception as e:
        pytest.fail(f"analyze_project failed during fixture setup: {e}")

    # Add a check to ensure the analysis results are set
    # 分析結果が設定されていることを確認するためのチェックを追加します
    assert kotemari._analysis_results is not None, "Analysis results were not set in fixture"
    assert kotemari.project_analyzed, "Project analyzed flag not set in fixture"

    # Debugging: Check if cache storage has paths after analysis (if cache enabled)
    # デバッグ: 分析後にキャッシュストレージにパスがあるか確認します（キャッシュが有効な場合）
    if kotemari._use_cache and kotemari._cache_storage:
        stored_paths = kotemari._cache_storage.get_all_file_paths()
        logger.debug(f"[Fixture] Paths in CacheStorage after analyze: {stored_paths}")
        expected_paths = {str(fi.path) for fi in mock_results}
        assert set(stored_paths) == expected_paths, "CacheStorage paths do not match mock results"

    return kotemari

# --- Test Kotemari Initialization --- #

def test_kotemari_init(setup_facade_test_project):
    """
    Tests basic initialization of the Kotemari facade.
    Kotemari ファサードの基本的な初期化をテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root)

    assert kotemari.project_root.is_absolute()
    assert kotemari.project_root.name == "facade_test_proj"
    # Check if internal analyzer seems initialized (basic check)
    # 内部アナライザーが初期化されているように見えるか確認します（基本チェック）
    assert hasattr(kotemari, 'analyzer') # Changed from _project_analyzer
    assert kotemari._config_manager is not None
    assert kotemari._ignore_processor is not None
    assert kotemari._analysis_results is None # Results not loaded initially
    assert kotemari.project_analyzed is False # Ensure analysis flag is initially False

# --- Test analyze_project Method --- #

@patch('kotemari.usecase.project_analyzer.ProjectAnalyzer.analyze')
def test_kotemari_analyze_project_calls_analyzer(mock_analyze, setup_facade_test_project):
    """
    Tests that Kotemari.analyze_project() calls the underlying ProjectAnalyzer.analyze().
    Kotemari.analyze_project() が基盤となる ProjectAnalyzer.analyze() を呼び出すことをテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root)

    # Setup mock return value
    # モックの戻り値を設定します
    mock_file_info = FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=100)
    mock_analyze.return_value = [mock_file_info]

    results = kotemari.analyze_project()

    mock_analyze.assert_called_once()
    assert results == [mock_file_info]
    assert kotemari._analysis_results == [mock_file_info] # Check caching

    # Call again, should use cache
    # 再度呼び出し、キャッシュを使用するはず
    results_cached = kotemari.analyze_project()
    mock_analyze.assert_called_once() # Should not be called again
    assert results_cached is results # Should be the same cached object

    # Force reload -> Force reanalyze
    # 強制リロード -> 強制再分析
    mock_analyze.reset_mock() # Reset mock before re-analysis call
    mock_analyze.return_value = [] # Change return value for reload
    results_reloaded = kotemari.analyze_project(force_reanalyze=True) # Updated from force_reload
    mock_analyze.assert_called_once()
    assert results_reloaded == []
    assert kotemari._analysis_results == []

# --- Test list_files Method --- #

def test_list_files_before_analysis(setup_facade_test_project):
    """
    Tests that list_files() raises RuntimeError if called before analysis.
    分析前に呼び出された場合に list_files() が RuntimeError を発生させることをテストします。
    """
    kotemari = Kotemari(setup_facade_test_project)
    with pytest.raises(RuntimeError, match="Project must be analyzed"):
        kotemari.list_files()

@patch('kotemari.usecase.project_analyzer.ProjectAnalyzer.analyze')
def test_list_files_success(mock_analyze, setup_facade_test_project):
    """
    Tests list_files() after analysis, checking relative and absolute paths.
    分析後の list_files() をテストし、相対パスと絶対パスを確認します。
    """
    project_root = setup_facade_test_project
    # Define mock FileInfo objects with paths relative to the mocked project root
    # モックされたプロジェクトルートからの相対パスを持つモック FileInfo オブジェクトを定義します
    mock_results = [
        FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=10, language="Python", hash="h1"),
        FileInfo(path=project_root / "lib" / "helpers.py", mtime=datetime.datetime.now(), size=20, language="Python", hash="h2"),
        FileInfo(path=project_root / "data.csv", mtime=datetime.datetime.now(), size=30, language=None, hash="h3"),
    ]
    mock_analyze.return_value = mock_results

    kotemari = Kotemari(project_root)
    kotemari.analyze_project()

    # Test relative paths (default)
    # 相対パスをテストします（デフォルト）
    relative_files = kotemari.list_files()
    expected_relative = sorted(["app.py", "lib/helpers.py", "data.csv"])
    assert sorted(relative_files) == expected_relative

    # Test absolute paths
    # 絶対パスをテストします
    absolute_files = kotemari.list_files(relative=False)
    expected_absolute = sorted([str(project_root / p) for p in expected_relative])
    assert sorted(absolute_files) == expected_absolute

def test_list_files_empty_results(setup_facade_test_project):
    """
    Tests list_files() when analysis returns an empty list.
    分析が空のリストを返す場合の list_files() をテストします。
    """
    kotemari = Kotemari(setup_facade_test_project)
    kotemari._analysis_results = [] # Manually set empty results
    assert kotemari.list_files() == []
    assert kotemari.list_files(relative=False) == []

# --- Test get_tree Method --- #

def test_get_tree_before_analysis(setup_facade_test_project):
    """
    Tests that get_tree() raises RuntimeError if called before analysis.
    分析前に呼び出された場合に get_tree() が RuntimeError を発生させることをテストします。
    """
    kotemari = Kotemari(setup_facade_test_project)
    with pytest.raises(RuntimeError, match="Project must be analyzed"):
        kotemari.get_tree()

@patch('kotemari.usecase.project_analyzer.ProjectAnalyzer.analyze')
def test_get_tree_success(mock_analyze, setup_facade_test_project):
    """
    Tests get_tree() generates a correct tree string representation.
    get_tree() が正しいツリー文字列表現を生成するかをテストします。
    """
    project_root = setup_facade_test_project
    mock_results = [
        FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=10),
        FileInfo(path=project_root / "lib" / "helpers.py", mtime=datetime.datetime.now(), size=20),
        FileInfo(path=project_root / "docs" / "index.md", mtime=datetime.datetime.now(), size=30),
        FileInfo(path=project_root / ".gitignore", mtime=datetime.datetime.now(), size=40),
    ]
    mock_analyze.return_value = mock_results

    kotemari = Kotemari(project_root)
    kotemari.analyze_project()

    tree = kotemari.get_tree()
    print(f"\nGenerated Tree:\n{tree}") # Print for visual inspection during test run

    # Expected tree structure (adjust based on implementation details)
    # 期待されるツリー構造（実装の詳細に基づいて調整）
    # Note: Order matters, and connector characters need to be exact.
    # 注意: 順序が重要であり、コネクタ文字は正確である必要があります。
    expected_tree = (
        f"{project_root.name}/\n"
        "├── .gitignore\n"
        "├── app.py\n"
        "├── docs\n"
        "│   └── index.md\n"
        "└── lib\n"
        "    └── helpers.py"
    )
    assert tree.strip() == expected_tree.strip()

def test_get_tree_empty_results(setup_facade_test_project):
    """
    Tests get_tree() when analysis returns an empty list.
    分析が空のリストを返す場合の get_tree() をテストします。
    """
    kotemari = Kotemari(setup_facade_test_project)
    kotemari._analysis_results = [] # Manually set empty results
    tree = kotemari.get_tree()
    assert "(Project is empty or all files were ignored)" in tree

def test_get_tree_with_max_depth(setup_facade_test_project):
    """
    Tests get_tree() with the max_depth parameter.
    max_depth パラメータを指定して get_tree() をテストします。
    """
    project_root = setup_facade_test_project
    # Use the same mock results as test_get_tree_success
    # test_get_tree_success と同じモック結果を使用します
    kotemari = Kotemari(project_root)
    kotemari._analysis_results = [
        FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=10),
        FileInfo(path=project_root / "lib" / "helpers.py", mtime=datetime.datetime.now(), size=20),
        FileInfo(path=project_root / "docs" / "subdocs" / "detail.md", mtime=datetime.datetime.now(), size=30),
        FileInfo(path=project_root / ".gitignore", mtime=datetime.datetime.now(), size=40),
    ]

    # Depth 1: Only show top-level files/dirs
    # 深度 1: トップレベルのファイル/ディレクトリのみを表示します
    tree_depth1 = kotemari.get_tree(max_depth=1)
    print(f"\nGenerated Tree (Depth 1):\n{tree_depth1}")
    expected_tree_d1 = (
        f"{project_root.name}/\n"
        "├── .gitignore\n"
        "├── app.py\n"
        "├── docs\n"
        "│   └── ...\n" # Ellipsis indicates truncated depth
        "└── lib\n"
        "    └── ..."
    ).strip()
    # Strip trailing spaces/newlines for comparison
    # 比較のために末尾のスペース/改行を削除します
    assert '\n'.join(line.rstrip() for line in tree_depth1.strip().split('\n')) == \
           '\n'.join(line.rstrip() for line in expected_tree_d1.split('\n'))

    # Depth 2: Show one level deeper
    # 深度 2: 1 レベル深く表示します
    tree_depth2 = kotemari.get_tree(max_depth=2)
    print(f"\nGenerated Tree (Depth 2):\n{tree_depth2}")
    expected_tree_d2 = (
        f"{project_root.name}/\n"
        "├── .gitignore\n"
        "├── app.py\n"
        "├── docs\n"
        "│   └── subdocs\n"
        "│       └── ...\n" # Ellipsis here
        "└── lib\n"
        "    └── helpers.py"
    ).strip()
    assert '\n'.join(line.rstrip() for line in tree_depth2.strip().split('\n')) == \
           '\n'.join(line.rstrip() for line in expected_tree_d2.split('\n')) 

# --- Test Kotemari Cache Functionality --- #

# Use patch to control CacheUpdater behavior within Kotemari
# Kotemari 内の CacheUpdater の動作を制御するために patch を使用します
@patch('kotemari.core.CacheStorage')
@patch('kotemari.core.CacheUpdater')
@patch('kotemari.usecase.project_analyzer.ProjectAnalyzer.analyze')
def test_kotemari_analyze_uses_cache(
    mock_analyze,
    mock_cache_updater_cls,
    mock_cache_storage_cls,
    setup_facade_test_project
):
    """
    Tests that analyze_project uses CacheStorage for loading and CacheUpdater for saving.
    analyze_project が読み込みに CacheStorage を、保存に CacheUpdater を使用することをテストします。
    """
    project_root = setup_facade_test_project
    # Need separate mocks for storage and updater instances if Kotemari creates them internally
    # Kotemari が内部でインスタンスを作成する場合、ストレージとアップデーター用に別々のモックが必要です
    mock_cache_storage_instance = mock_cache_storage_cls.return_value
    mock_cache_updater_instance = mock_cache_updater_cls.return_value # Keep for update assertion

    # Note: Kotemari.__init__ creates CacheStorage and potentially CacheUpdater.
    # The patch needs to intercept *these* creations.
    kotemari = Kotemari(project_root, use_cache=True)

    # Fresh analysis result if cache misses
    # キャッシュミスの場合の新しい分析結果
    fresh_result = [FileInfo(path=project_root / "a.py", mtime=datetime.datetime.now(), size=1)]
    mock_analyze.return_value = fresh_result

    # Cached analysis result and metadata
    # キャッシュされた分析結果とメタデータ
    cached_files = [FileInfo(path=project_root / "cached.py", mtime=datetime.datetime.now(), size=2)]
    cached_metadata = CacheMetadata(cache_time=datetime.datetime.now(), source_hash="dummy_hash")
    cached_data = (cached_files, cached_metadata)

    # --- Scenario 1: Valid cache found ---
    logger.info("Testing cache hit scenario...")
    mock_cache_storage_instance.load_cache.return_value = cached_data # Mock load_cache
    mock_analyze.reset_mock() # Reset analyze mock before call
    mock_cache_updater_instance.update_cache.reset_mock() # Reset update mock

    results1 = kotemari.analyze_project()

    mock_cache_storage_instance.load_cache.assert_called_once() # Verify load was attempted
    mock_analyze.assert_not_called() # Analyzer should NOT be called if cache hits
    mock_cache_updater_instance.update_cache.assert_not_called() # Updater should NOT be called if cache hits
    assert results1 == cached_files # Result should be the cached data
    logger.info("Cache hit scenario passed.")

    # --- Scenario 2: No valid cache found ---
    logger.info("Testing cache miss scenario...")
    kotemari.project_analyzed = False # Reset analysis state for re-analysis
    kotemari._analysis_results = None # Clear in-memory cache
    mock_cache_storage_instance.load_cache.return_value = None # Simulate no cache found
    mock_cache_storage_instance.reset_mock() # Reset mocks for second run
    mock_analyze.reset_mock()
    mock_cache_updater_instance.reset_mock()

    results2 = kotemari.analyze_project()

    mock_cache_storage_instance.load_cache.assert_called_once() # Verify load was attempted again
    mock_analyze.assert_called_once() # Analyzer *should* be called now
    mock_cache_updater_instance.update_cache.assert_called_once_with(fresh_result) # Verify updater is called with fresh results
    assert results2 == fresh_result # Result should be the fresh analysis data
    logger.info("Cache miss scenario passed.")

    # --- Scenario 3: Cache disabled ---
    # (Optional: Add a test case where use_cache=False and assert mocks are not called)

@patch('kotemari.core.CacheUpdater')
@patch('kotemari.usecase.project_analyzer.ProjectAnalyzer.analyze')
def test_kotemari_analyze_cache_disabled(mock_analyze, mock_cache_updater_cls, setup_facade_test_project):
    """
    Tests that analyze_project does not use CacheUpdater when cache is disabled.
    キャッシュが無効な場合に analyze_project が CacheUpdater を使用しないことをテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root, use_cache=False)

    mock_cache_updater_instance = mock_cache_updater_cls.return_value
    mock_analyze.return_value = [FileInfo(path=project_root / "a.py", mtime=datetime.datetime.now(), size=1)]

    results = kotemari.analyze_project()

    mock_analyze.assert_called_once()
    mock_cache_updater_cls.assert_not_called() # CacheUpdater should not be instantiated
    mock_cache_updater_instance.get_valid_cache.assert_not_called()
    mock_cache_updater_instance.update_cache.assert_not_called()
    assert results == mock_analyze.return_value
    assert kotemari._analysis_results == mock_analyze.return_value

@patch('kotemari.core.CacheUpdater')
def test_kotemari_clear_cache(mock_cache_updater_cls, setup_facade_test_project):
    """
    Tests the clear_cache method.
    clear_cache メソッドをテストします。
    """
    project_root = setup_facade_test_project

    # Scenario 1: Cache enabled
    # シナリオ 1: キャッシュ有効
    kotemari_enabled = Kotemari(project_root, use_cache=True)
    mock_cache_updater_instance = mock_cache_updater_cls.return_value
    # Simulate cached results
    # キャッシュされた結果をシミュレートします
    kotemari_enabled._analysis_results = [MagicMock()]

    kotemari_enabled.clear_cache()
    mock_cache_updater_instance.clear_cache_state.assert_called_once()

    # Verify cache storage clear was called

    # Reset mock for next scenario
    # 次のシナリオのためにモックをリセットします
    mock_cache_updater_instance.reset_mock()

    # Scenario 2: Cache disabled
    # シナリオ 2: キャッシュ無効
    kotemari_disabled = Kotemari(project_root, use_cache=False)
    kotemari_disabled._analysis_results = [MagicMock()]

    kotemari_disabled.clear_cache()
    mock_cache_updater_instance.clear_cache.assert_not_called()
    assert kotemari_disabled._analysis_results is None # In-memory cache still cleared 

# --- Test get_dependencies Method ---

def test_get_dependencies_before_analysis(setup_facade_test_project):
    """
    Tests that get_dependencies() raises RuntimeError if called before analysis.
    分析前に呼び出された場合に get_dependencies() が RuntimeError を発生させることをテストします。
    """
    kotemari = Kotemari(setup_facade_test_project)
    with pytest.raises(RuntimeError, match="Project must be analyzed"):
        kotemari.get_dependencies("app.py")

def test_get_dependencies_success(setup_facade_test_project):
    """
    Tests get_dependencies() returns correct list for an analyzed Python file.
    分析済みの Python ファイルに対して get_dependencies() が正しいリストを返すことをテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root, use_cache=False) # Disable cache for simpler mocking

    # Prepare mock analysis results
    app_py_path = project_root / "app.py"
    helpers_py_path = project_root / "lib" / "helpers.py"
    csv_path = project_root / "data.csv"

    app_deps = [DependencyInfo("os")]
    helpers_deps = [DependencyInfo(".")] # Example dependency from "from . import models"

    mock_results = [
        FileInfo(path=app_py_path, mtime=datetime.datetime.now(), size=20, language="Python", hash="h_app", dependencies=app_deps),
        FileInfo(path=helpers_py_path, mtime=datetime.datetime.now(), size=30, language="Python", hash="h_help", dependencies=helpers_deps),
        FileInfo(path=csv_path, mtime=datetime.datetime.now(), size=15, language=None, hash="h_csv", dependencies=[]), # No deps for non-python
    ]
    kotemari._analysis_results = mock_results # Manually set analysis results

    # Get dependencies for app.py (using relative path)
    deps_app = kotemari.get_dependencies("app.py")
    assert deps_app == app_deps

    # Get dependencies for helpers.py (using absolute path)
    deps_helpers = kotemari.get_dependencies(helpers_py_path)
    assert deps_helpers == helpers_deps

def test_get_dependencies_non_python_file(setup_facade_test_project):
    """
    Tests get_dependencies() returns empty list for non-Python files.
    Python 以外のファイルに対して get_dependencies() が空のリストを返すことをテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root, use_cache=False)

    csv_path = project_root / "data.csv"
    mock_results = [
        FileInfo(path=csv_path, mtime=datetime.datetime.now(), size=15, language=None, hash="h_csv", dependencies=[]),
    ]
    kotemari._analysis_results = mock_results

    deps_csv = kotemari.get_dependencies("data.csv")
    assert deps_csv == []

def test_get_dependencies_file_not_in_analysis(setup_facade_test_project, caplog):
    """
    Tests get_dependencies() for a file path not found in analysis results (e.g., ignored).
    分析結果に見つからない（例: 無視された）ファイルパスに対する get_dependencies() をテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root, use_cache=False)

    # Simulate analysis results without 'ignored.py'
    mock_results = [
        FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=20, language="Python", hash="h_app", dependencies=[DependencyInfo("os")]),
    ]
    kotemari._analysis_results = mock_results

    ignored_py_path = project_root / "ignored.py" # This file exists but wasn't in results

    with caplog.at_level(logging.WARNING):
        deps_ignored = kotemari.get_dependencies(ignored_py_path)

    assert deps_ignored == []
    assert f"File '{ignored_py_path}' not found in analysis results" in caplog.text

def test_get_dependencies_non_existent_file(setup_facade_test_project, caplog):
    """
    Tests get_dependencies() for a file path that does not exist.
    存在しないファイルパスに対する get_dependencies() をテストします。
    """
    project_root = setup_facade_test_project
    kotemari = Kotemari(project_root, use_cache=False)

    # Simulate analysis results
    mock_results = [
        FileInfo(path=project_root / "app.py", mtime=datetime.datetime.now(), size=20, language="Python", hash="h_app", dependencies=[DependencyInfo("os")]),
    ]
    kotemari._analysis_results = mock_results

    non_existent_path_str = "non_existent_file.py"
    non_existent_path_abs = project_root / non_existent_path_str

    with caplog.at_level(logging.WARNING):
        deps_non_existent = kotemari.get_dependencies(non_existent_path_str)

    assert deps_non_existent == []
    # PathResolver might log or the get_dependencies logic logs
    # Check for the warning from get_dependencies
    assert f"Cannot resolve path for dependency lookup: {non_existent_path_str}" in caplog.text or \
           f"File '{non_existent_path_abs}' not found in analysis results" in caplog.text 

# --- get_context tests ---

def test_get_context_not_analyzed(kotemari_instance_empty):
    """Tests that get_context raises RuntimeError if analyze hasn't run."""
    instance: Kotemari = kotemari_instance_empty
    target_file = instance.project_root / "dummy_file.py"
    target_file.touch() # Create the file

    with pytest.raises(RuntimeError, match="Project must be analyzed first"):
        instance.get_context([str(target_file)])

def test_get_context_success(kotemari_instance_analyzed):
    """Tests get_context successfully retrieves formatted content."""
    instance: Kotemari = kotemari_instance_analyzed
    main_py_path = instance.project_root / "main.py"
    util_py_path = instance.project_root / "my_module" / "utils.py"

    # Ensure files exist (they should from the fixture)
    assert main_py_path.exists()
    assert util_py_path.exists()

    context_str = instance.get_context([str(main_py_path), str(util_py_path)])

    # Check if content from both files and headers are present
    # Check for file names in the header, ignoring path separator differences
    # ヘッダー内のファイル名をチェックし、パス区切り文字の違いを無視します
    assert f"# --- File: {main_py_path.name} ---" in context_str
    assert f"# --- File: {util_py_path.name} ---" in context_str
    # Also check for the actual content written by the fixture
    # フィクスチャによって書き込まれた実際のコンテンツもチェックします
    assert "print('hello from main')" in context_str # Content from setup_facade_test_project
    assert "def helper(): return 1" in context_str # Content from setup_facade_test_project

def test_get_context_target_file_not_in_analysis(kotemari_instance_analyzed):
    """Tests get_context when a target file exists but wasn't part of analysis (e.g., ignored)."""
    instance: Kotemari = kotemari_instance_analyzed
    ignored_file_path = instance.project_root / "ignored_by_gitignore.txt"
    ignored_file_path.write_text("This file is ignored.")

    # Should raise FileNotFoundError because it's not in the cache/analysis result
    with pytest.raises(FileNotFoundError, match="not found in analyzed project data"):
         instance.get_context([str(ignored_file_path)])

def test_get_context_target_file_does_not_exist(kotemari_instance_analyzed):
    """Tests get_context when a target file physically doesn't exist."""
    instance: Kotemari = kotemari_instance_analyzed
    non_existent_file = instance.project_root / "non_existent.py"
    assert not non_existent_file.exists()

    # Should raise FileNotFoundError because it's not in the cache and likely fails existence check
    with pytest.raises(FileNotFoundError, match="not found in analyzed project data"):
        instance.get_context([str(non_existent_file)]) 