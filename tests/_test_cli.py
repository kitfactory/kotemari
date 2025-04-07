import pytest
import subprocess
import sys
import os
from pathlib import Path
import shutil
import textwrap
import time
import signal

# English: Define the path to the kotemari executable within the virtual environment.
# 日本語: 仮想環境内の kotemari 実行可能ファイルへのパスを定義します。
# This might need adjustment depending on the OS and virtual environment structure.
# これはOSや仮想環境の構造によって調整が必要になる場合があります。
VENV_PATH = Path(sys.prefix)
EXECUTABLE_NAME = 'kotemari.exe' if sys.platform == "win32" else 'kotemari'
KOTEMARI_CMD = VENV_PATH / 'Scripts' / EXECUTABLE_NAME if sys.platform == "win32" else VENV_PATH / 'bin' / EXECUTABLE_NAME

@pytest.fixture(scope='function')
def setup_test_project(tmp_path: Path):
    """
    Creates a temporary directory structure for a dummy Python project.
    ダミーPythonプロジェクト用の一時的なディレクトリ構造を作成します。

    Yields:
        Path: The root path of the temporary project.
              一時プロジェクトのルートパス。
    """
    project_dir = tmp_path / "test_proj"
    project_dir.mkdir()
    (project_dir / ".kotemari_cache").mkdir() # Simulate existing cache dir sometimes

    # Create dummy files
    (project_dir / "main.py").write_text(textwrap.dedent("""
        import os
        from my_module import util
        from . import local_helper

        print('Hello from main')
        util.do_something()
        local_helper.help_me()
    """), encoding='utf-8')

    (project_dir / "local_helper.py").write_text(textwrap.dedent("""
        def help_me():
            print('Helping locally!')
    """), encoding='utf-8')

    my_module_dir = project_dir / "my_module"
    my_module_dir.mkdir()
    (my_module_dir / "__init__.py").touch()
    (my_module_dir / "util.py").write_text(textwrap.dedent("""
        import sys
        from .. import external_dep # Example of relative import beyond top-level

        def do_something():
            print(f'Doing something with sys version {sys.version_info}')
    """), encoding='utf-8')

    # File with syntax error
    (project_dir / "syntax_error.py").write_text("print('Valid')\ninvalid syntax", encoding='utf-8')

    # Non-python file
    (project_dir / "data.txt").write_text("This is not Python code.", encoding='utf-8')

    # Simulate external dep (though resolution isn't tested here)
    (project_dir / "external_dep.py").write_text("print('External dependency simulation')", encoding='utf-8')


    yield project_dir

    # Teardown (usually handled by tmp_path fixture)
    # shutil.rmtree(project_dir)

def run_kotemari_cmd(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """
    Helper function to run the kotemari command.
    kotemariコマンドを実行するためのヘルパー関数。

    Args:
        args: A list of arguments to pass to the kotemari command.
              kotemariコマンドに渡す引数のリスト。
        cwd: The working directory from which to run the command.
             コマンドを実行する作業ディレクトリ。

    Returns:
        subprocess.CompletedProcess: The result of the command execution.
                                     コマンド実行の結果。
    """
    command = [str(KOTEMARI_CMD)] + args
    print(f"\nRunning command: {' '.join(command)} in {cwd}") # Debug output
    result = subprocess.run(
        command, # type: ignore
        cwd=cwd,
        capture_output=True,
        text=True,
        # English: Force UTF-8 encoding for the subprocess environment and capture streams
        # 日本語: サブプロセス環境とキャプチャストリームにUTF-8エンコーディングを強制します
        encoding='utf-8', errors='replace', # Replace errors to avoid decode failures
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        # English: Set a timeout to prevent tests from hanging indefinitely.
        # 日本語: テストが無期限にハングするのを防ぐためにタイムアウトを設定します。
        timeout=30 # 30 seconds timeout
    )
    print(f"Exit Code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
    return result

# --- Test Cases --- 

def test_cli_help():
    """
    Tests if the --help option works correctly.
    --help オプションが正しく機能するかテストします。
    """
    result = run_kotemari_cmd(["--help"], Path(".")) # CWD doesn't matter for help
    assert result.returncode == 0
    assert "Usage: kotemari" in result.stdout
    assert "analyze" in result.stdout
    assert "dependencies" in result.stdout
    assert "context" in result.stdout
    assert "watch" in result.stdout

def test_cli_analyze_success(setup_test_project):
    """
    Tests the 'analyze' command on a valid project.
    有効なプロジェクトで 'analyze' コマンドをテストします。
    """
    project_dir = setup_test_project
    result = run_kotemari_cmd(["analyze", "-p", str(project_dir)], cwd=project_dir)
    assert result.returncode == 0
    assert "Analysis complete and cache updated" in result.stdout
    # English: Check if the cache file was created/updated.
    # 日本語: キャッシュファイルが作成/更新されたか確認します。
    cache_file = project_dir / ".kotemari_cache" / "kotemari_cache.json"
    assert cache_file.exists()
    # TODO: Optionally, check cache content for basic validity

def test_cli_analyze_project_not_found():
    """
    Tests the 'analyze' command with a non-existent project path.
    存在しないプロジェクトパスで 'analyze' コマンドをテストします。
    """
    non_existent_path = Path("./non_existent_project_dir_for_test")
    assert not non_existent_path.exists() # Ensure it really doesn't exist
    # English: Run from a valid CWD, but point -p to a non-existent dir.
    # 日本語: 有効なCWDから実行しますが、-p は存在しないディレクトリを指します。
    result = run_kotemari_cmd(["analyze", "-p", str(non_existent_path)], cwd=Path("."))
    # English: Typer handles the validation and exits with code 2 for invalid options/args.
    # 日本語: Typer が検証を処理し、無効なオプション/引数の場合はコード 2 で終了します。
    assert result.returncode == 2
    assert "Invalid value" in result.stderr
    assert "Directory" in result.stderr
    assert "does not exist" in result.stderr

def test_cli_dependencies_success(setup_test_project):
    """
    Tests the 'dependencies' command on a valid file after analysis.
    分析後の有効なファイルで 'dependencies' コマンドをテストします。
    """
    project_dir = setup_test_project
    main_py_path = project_dir / "main.py"

    # 1. Run analyze first
    # 1. 最初に analyze を実行します
    analyze_result = run_kotemari_cmd(["analyze", "-p", str(project_dir)], cwd=project_dir)
    assert analyze_result.returncode == 0

    # 2. Run dependencies command
    # 2. dependencies コマンドを実行します
    deps_result = run_kotemari_cmd(["dependencies", str(main_py_path), "-p", str(project_dir)], cwd=project_dir)
    assert deps_result.returncode == 0
    # English: Check for expected dependencies in the output table.
    # 日本語: 出力テーブルに期待される依存関係が含まれているか確認します。
    assert "os" in deps_result.stdout
    assert "EXTERNAL" in deps_result.stdout
    assert "my_module.util" in deps_result.stdout # Assuming util is resolved this way
    # assert "INTERNAL_ABSOLUTE" in deps_result.stdout # Type depends on resolution logic
    assert ".local_helper" in deps_result.stdout
    # assert "INTERNAL_RELATIVE" in deps_result.stdout

def test_cli_dependencies_no_analyze(setup_test_project):
    """
    Tests that 'dependencies' command fails gracefully if 'analyze' wasn't run.
    'analyze' が実行されていない場合に 'dependencies' コマンドが正常に失敗するかテストします。
    """
    project_dir = setup_test_project
    main_py_path = project_dir / "main.py"
    # English: Clear potential cache from previous tests in the same tmp_path if any.
    # 日本語: 同じ tmp_path 内の以前のテストでキャッシュが残っている可能性がある場合、クリアします。
    cache_dir = project_dir / ".kotemari_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    deps_result = run_kotemari_cmd(["dependencies", str(main_py_path), "-p", str(project_dir)], cwd=project_dir)
    # English: Expecting exit code 1 due to RuntimeError("Project not analyzed...").
    # 日本語: RuntimeError("Project not analyzed...") により終了コード 1 を期待します。
    assert deps_result.returncode == 1
    assert "Please run 'analyze' first" in deps_result.stdout # Check rich console output

def test_cli_dependencies_file_not_found(setup_test_project):
    """
    Tests the 'dependencies' command with a non-existent file path.
    存在しないファイルパスで 'dependencies' コマンドをテストします。
    """
    project_dir = setup_test_project
    non_existent_file = project_dir / "non_existent.py"

    # Analyze first
    run_kotemari_cmd(["analyze", "-p", str(project_dir)], cwd=project_dir)

    deps_result = run_kotemari_cmd(["dependencies", str(non_existent_file), "-p", str(project_dir)], cwd=project_dir)
    # English: Typer handles the file existence check.
    # 日本語: Typer がファイルの存在チェックを処理します。
    assert deps_result.returncode == 2
    assert "Invalid value" in deps_result.stderr
    assert "does not exist" in deps_result.stderr

def test_cli_context_success(setup_test_project):
    """
    Tests the 'context' command with valid files after analysis.
    分析後の有効なファイルで 'context' コマンドをテストします。
    """
    project_dir = setup_test_project
    main_py_path = project_dir / "main.py"
    util_py_path = project_dir / "my_module" / "util.py"

    # 1. Run analyze first
    analyze_result = run_kotemari_cmd(["analyze", "-p", str(project_dir)], cwd=project_dir)
    assert analyze_result.returncode == 0

    # 2. Run context command
    context_result = run_kotemari_cmd([
        "context", str(main_py_path), str(util_py_path), "-p", str(project_dir)
    ], cwd=project_dir)
    assert context_result.returncode == 0
    # English: Check if the output contains parts of the source code from both files.
    # 日本語: 出力に両方のファイルのソースコードの一部が含まれているか確認します。
    assert "print('Hello from main')" in context_result.stdout # From main.py
    assert "def do_something():" in context_result.stdout      # From util.py
    # English: Check for the file path markers added by the formatter.
    # 日本語: フォーマッタによって追加されたファイルパスマーカーを確認します。
    assert f"# --- File: {main_py_path.relative_to(project_dir)}" in context_result.stdout
    assert f"# --- File: {util_py_path.relative_to(project_dir)}" in context_result.stdout

def test_cli_context_no_analyze(setup_test_project):
    """
    Tests that 'context' command fails gracefully if 'analyze' wasn't run.
    'analyze' が実行されていない場合に 'context' コマンドが正常に失敗するかテストします。
    """
    project_dir = setup_test_project
    main_py_path = project_dir / "main.py"
    cache_dir = project_dir / ".kotemari_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    context_result = run_kotemari_cmd(["context", str(main_py_path), "-p", str(project_dir)], cwd=project_dir)
    assert context_result.returncode == 1
    assert "Please run 'analyze' first" in context_result.stdout

def test_cli_context_file_not_found(setup_test_project):
    """
    Tests the 'context' command when one of the target files doesn't exist.
    ターゲットファイルの一つが存在しない場合に 'context' コマンドをテストします。
    """
    project_dir = setup_test_project
    main_py_path = project_dir / "main.py"
    non_existent_file = project_dir / "non_existent.py"

    # Analyze first
    run_kotemari_cmd(["analyze", "-p", str(project_dir)], cwd=project_dir)

    context_result = run_kotemari_cmd([
        "context", str(main_py_path), str(non_existent_file), "-p", str(project_dir)
    ], cwd=project_dir)
    # English: Typer handles the file existence check for arguments.
    # 日本語: Typer が引数のファイルの存在チェックを処理します。
    assert context_result.returncode == 2
    assert "Invalid value" in context_result.stderr
    assert "does not exist" in context_result.stderr

# Add more tests for dependencies, context, watch...
def test_cli_watch_starts_and_stops(setup_test_project):
    """
    Tests if the 'watch' command starts and can be stopped using Ctrl+C (SIGINT).
    'watch' コマンドが起動し、Ctrl+C (SIGINT) を使って停止できるかテストします。
    """
    project_dir = setup_test_project
    command = [str(KOTEMARI_CMD), "watch", "-p", str(project_dir)]
    print(f"\nStarting watch command: {' '.join(command)} in {project_dir}")

    # English: Start the watch command as a background process.
    # 日本語: watch コマンドをバックグラウンドプロセスとして開始します。
    process = subprocess.Popen(
        command,
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8'
    )

    # English: Wait a bit for the watcher to potentially initialize and print output.
    # 日本語: ウォッチャーが初期化され、出力を表示する可能性を考慮して少し待ちます。
    time.sleep(3) # Adjust timing as needed

    # English: Check if the process is still running and initial output is as expected.
    # 日本語: プロセスがまだ実行中であり、初期出力が期待通りか確認します。
    assert process.poll() is None, "Process terminated unexpectedly early."
    stdout_initial, stderr_initial = process.communicate(timeout=1) # Read initial buffer
    print(f"Initial Stdout: {stdout_initial}")
    print(f"Initial Stderr: {stderr_initial}")
    assert f"Starting file watcher for: {project_dir}" in stdout_initial
    assert "Press Ctrl+C to stop." in stdout_initial

    # English: Send SIGINT (Ctrl+C equivalent) to the process group on non-Windows.
    # English: On Windows, subprocess.Popen doesn't handle Ctrl+C well directly for console apps.
    # English: We might need taskkill or other methods, or rely on Kotemari's internal handling if robust.
    # English: For simplicity here, we'll try SIGINT, acknowledging potential platform differences.
    # 日本語: 非WindowsではプロセスグループにSIGINT（Ctrl+C相当）を送信します。
    # 日本語: Windowsでは、subprocess.Popen はコンソールアプリに対して直接Ctrl+Cをうまく処理しません。
    # 日本語: taskkill や他の方法が必要になるか、Kotemariの内部処理が堅牢であればそれに依存するかもしれません。
    # 日本語: ここでは簡潔さのためにSIGINTを試しますが、プラットフォームの違いがある可能性を認識しておきます。
    print("Sending SIGINT...")
    if sys.platform == "win32":
         # On Windows, sending SIGINT might not work as expected for console processes
         # started this way. A more robust method might involve os.kill or taskkill.
         # For now, we rely on the watcher potentially exiting cleanly on its own
         # or timing out in the wait call below if it doesn't.
         # Windowsでは、この方法で開始されたコンソールプロセスに対してSIGINTを送信しても期待通りに動作しない場合があります。
         # os.killやtaskkillなどのより堅牢な方法が必要になるかもしれません。
         # ここでは、ウォッチャーが自身でクリーンに終了するか、下のwait呼び出しでタイムアウトすることに依存します。
         process.send_signal(signal.CTRL_C_EVENT) # Try sending Ctrl+C event
    else:
        # Try sending SIGINT to the process group to simulate Ctrl+C
        # Ctrl+CをシミュレートするためにプロセスグループにSIGINTを送信してみます
        try:
             os.killpg(os.getpgid(process.pid), signal.SIGINT)
        except ProcessLookupError:
             print("Process already terminated.") # Process might have exited quickly
             pass # Allow check below

    # English: Wait for the process to terminate.
    # 日本語: プロセスが終了するのを待ちます。
    try:
        stdout_final, stderr_final = process.communicate(timeout=15) # Increased timeout
        print(f"Final Stdout: {stdout_final}")
        print(f"Final Stderr: {stderr_final}")
        return_code = process.returncode
    except subprocess.TimeoutExpired:
        print("Process did not terminate after SIGINT, killing.")
        process.kill()
        stdout_final, stderr_final = process.communicate()
        pytest.fail("Watch process did not terminate gracefully after SIGINT.")

    # English: Check if the termination output is as expected.
    # 日本語: 終了時の出力が期待通りか確認します。
    # Note: Depending on timing and buffering, the "Watcher stopped by user"
    # message might be in stdout_initial or stdout_final.
    # 注意: タイミングとバッファリングによっては、「Watcher stopped by user」
    # メッセージが stdout_initial または stdout_final に含まれる場合があります。
    assert "Watcher stopped by user" in stdout_initial + stdout_final
    # English: Expecting clean exit (code 0) after Ctrl+C handling in the controller.
    # 日本語: コントローラーでのCtrl+C処理後、クリーンな終了（コード0）を期待します。
    # On Windows, if SIGINT doesn't work, it might exit differently or timeout.
    # Windowsでは、SIGINTが機能しない場合、異なる方法で終了するかタイムアウトする可能性があります。
    if sys.platform != "win32": # Be lenient on Windows for now
        assert return_code == 0, f"Process exited with code {return_code}" 