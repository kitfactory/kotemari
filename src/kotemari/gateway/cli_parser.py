import typer
from typing import List, Optional
from pathlib import Path
# English: Import the controller instance to link commands to logic.
# 日本語: コマンドをロジックにリンクするためにコントローラーインスタンスをインポートします。
from kotemari.controller.cli_controller import controller

app = typer.Typer(
    help="Kotemari: A tool for analyzing Python project dependencies and generating context.",
    # English: Rich markup is enabled for better help text rendering.
    # 日本語: ヘルプテキストのレンダリングを改善するためにリッチマークアップが有効になっています。
    rich_markup_mode="rich"
)

# English: Define a common callback to handle global options or initialization if needed in the future.
# 日本語: 将来的にグローバルオプションや初期化を処理する必要がある場合に備えて、共通のコールバックを定義します。
@app.callback()
def main_callback(ctx: typer.Context):
    pass

@app.command()
def analyze(
    project_path: Path = typer.Option(
        ".",
        "--project-path", "-p",
        help="The root path of the project to analyze.",
        # English: Resolve the path to ensure it's absolute and exists.
        # 日本語: パスを解決して、絶対パスであり存在することを確認します。
        resolve_path=True,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    )
):
    """
    Analyze the specified Python project and cache its structure and dependencies.
    指定されたPythonプロジェクトを分析し、その構造と依存関係をキャッシュします。
    """
    # English: Call the corresponding controller method.
    # 日本語: 対応するコントローラーメソッドを呼び出します。
    controller.analyze_project(project_path)

@app.command()
def dependencies(
    file_path: Path = typer.Argument(
        ...,
        help="The path to the Python file to show dependencies for.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    project_path: Path = typer.Option(
        ".",
        "--project-path", "-p",
        help="The root path of the project the file belongs to.",
        resolve_path=True,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    )
):
    """
    Show the dependencies of a specific Python file within the project.
    プロジェクト内の特定のPythonファイルの依存関係を表示します。
    """
    # English: Call the corresponding controller method.
    # 日本語: 対応するコントローラーメソッドを呼び出します。
    controller.show_dependencies(file_path, project_path)

@app.command()
def context(
    target_files: List[Path] = typer.Argument(
        ...,
        help="The paths to the Python files to generate context from.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    project_path: Path = typer.Option(
        ".",
        "--project-path", "-p",
        help="The root path of the project these files belong to.",
        resolve_path=True,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    )
):
    """
    Generate and display context from the specified Python files.
    指定されたPythonファイルからコンテキストを生成して表示します。
    """
    # English: Call the corresponding controller method.
    # 日本語: 対応するコントローラーメソッドを呼び出します。
    controller.generate_context(target_files, project_path)

@app.command()
def watch(
    project_path: Path = typer.Option(
        ".",
        "--project-path", "-p",
        help="The root path of the project to watch for changes.",
        resolve_path=True,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    )
):
    """
    Watch the project directory for file changes and update the cache automatically.
    プロジェクトディレクトリのファイル変更を監視し、キャッシュを自動的に更新します。
    """
    # English: Call the corresponding controller method. Blocking/waiting is handled within the controller/core.
    # 日本語: 対応するコントローラーメソッドを呼び出します。ブロッキング/待機はコントローラー/コア内で処理されます。
    controller.start_watching(project_path)

# English: Entry point for the CLI application.
# 日本語: CLIアプリケーションのエントリポイント。
if __name__ == "__main__":
    app() 