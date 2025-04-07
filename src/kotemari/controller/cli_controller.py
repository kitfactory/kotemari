from pathlib import Path
from typing import List
from kotemari.core import Kotemari
import typer # Typer needed for exit

# English: Use rich for better console output formatting.
# 日本語: より良いコンソール出力フォーマットのために rich を使用します。
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

console = Console()

class CliController:
    """
    Controller class to handle CLI commands and interact with the Kotemari core.
    CLIコマンドを処理し、Kotemariコアと対話するためのコントローラークラス。

    Attributes:
        kotemari: An instance of the Kotemari core class.
                  Kotemariコアクラスのインスタンス。
    """
    def analyze_project(self, project_path: Path):
        """
        Handles the 'analyze' command.
        'analyze' コマンドを処理します。

        Args:
            project_path: The root path of the project to analyze.
                          分析するプロジェクトのルートパス。
        """
        # English: Create Kotemari instance specific to this command's project path.
        # 日本語: このコマンドのプロジェクトパスに固有のKotemariインスタンスを作成します。
        kotemari = Kotemari(str(project_path))
        console.print(f"[bold cyan]Analyzing project:[/bold cyan] {project_path}")
        try:
            kotemari.analyze_project() # analyze_project now takes no args
            console.print("[bold green]Analysis complete and cache updated.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error during analysis:[/bold red] {e}")
            raise typer.Exit(code=1)

    def show_dependencies(self, file_path: Path, project_path: Path):
        """
        Handles the 'dependencies' command.
        'dependencies' コマンドを処理します。

        Args:
            file_path: The path to the file to show dependencies for.
                       依存関係を表示するファイルのパス。
            project_path: The root path of the project.
                          プロジェクトのルートパス。
        """
        # English: Create Kotemari instance specific to this command's project path.
        # 日本語: このコマンドのプロジェクトパスに固有のKotemariインスタンスを作成します。
        kotemari = Kotemari(str(project_path))
        console.print(f"[bold cyan]Showing dependencies for:[/bold cyan] {file_path}")
        try:
            # English: Ensure analysis has run at least once, maybe implicitly via Kotemari?
            # 日本語: 分析が少なくとも一度実行されたことを確認します（Kotemari経由で暗黙的に？）。
            # self.kotemari.ensure_analysis(str(project_path))
            dependencies = kotemari.get_dependencies(str(file_path))

            if not dependencies:
                console.print("No dependencies found or file not part of the analysis.")
                return

            table = Table(title=f"Dependencies for {file_path.name}", show_header=True, header_style="bold magenta")
            table.add_column("Module Name", style="dim", width=40)
            table.add_column("Type", width=20)
            table.add_column("Resolved Name", width=40)
            table.add_column("Level", width=10)

            for dep in sorted(dependencies):
                table.add_row(
                    dep.module_name,
                    dep.dependency_type.name,
                    dep.resolved_name,
                    str(dep.level) if dep.level is not None else "N/A"
                )
            console.print(table)

        except RuntimeError as e:
             console.print(f"[bold red]Error:[/bold red] {e} Please run 'analyze' first.")
             raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]Error getting dependencies:[/bold red] {e}")
            raise typer.Exit(code=1)

    def generate_context(self, target_files: List[Path], project_path: Path):
        """
        Handles the 'context' command.
        'context' コマンドを処理します。

        Args:
            target_files: List of file paths to generate context from.
                          コンテキストを生成するファイルパスのリスト。
            project_path: The root path of the project.
                          プロジェクトのルートパス。
        """
        # English: Create Kotemari instance specific to this command's project path.
        # 日本語: このコマンドのプロジェクトパスに固有のKotemariインスタンスを作成します。
        kotemari = Kotemari(str(project_path))
        console.print(f"[bold cyan]Generating context for:[/bold cyan] {', '.join(map(str, target_files))}")
        try:
            # English: Ensure analysis has run at least once.
            # 日本語: 分析が少なくとも一度実行されたことを確認します。
            # self.kotemari.ensure_analysis(str(project_path))
            context_str = kotemari.get_context([str(f) for f in target_files])

            if not context_str:
                console.print("Could not generate context. Files might not be part of the analysis or have no content.")
                return

            # English: Use rich.syntax for highlighting the generated context.
            # 日本語: 生成されたコンテキストをハイライト表示するために rich.syntax を使用します。
            syntax = Syntax(context_str, "python", theme="default", line_numbers=True)
            console.print(syntax)

        except RuntimeError as e:
             console.print(f"[bold red]Error:[/bold red] {e} Please run 'analyze' first.")
             raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]Error generating context:[/bold red] {e}")
            raise typer.Exit(code=1)

    def start_watching(self, project_path: Path):
        """
        Handles the 'watch' command.
        'watch' コマンドを処理します。

        Args:
            project_path: The root path of the project to watch.
                          監視するプロジェクトのルートパス。
        """
        # English: Create Kotemari instance specific to this command's project path.
        # 日本語: このコマンドのプロジェクトパスに固有のKotemariインスタンスを作成します。
        kotemari = Kotemari(str(project_path))
        console.print(f"[bold cyan]Starting file watcher for:[/bold cyan] {project_path}")
        console.print("Press Ctrl+C to stop.")
        try:
            # English: The start_watching method in Kotemari should handle the background thread and blocking.
            # 日本語: Kotemariのstart_watchingメソッドがバックグラウンドスレッドとブロッキングを処理する必要があります。
            kotemari.start_watching()
            # Note: The loop in cli_parser is now redundant if Kotemari handles blocking.
            # 注意: Kotemariがブロッキングを処理する場合、cli_parser内のループは冗長になります。
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Watcher stopped by user.[/bold yellow]")
            kotemari.stop_watching() # Ensure stop is called
        except Exception as e:
            console.print(f"[bold red]Error during watching:[/bold red] {e}")
            kotemari.stop_watching() # Attempt to stop watcher on error
            raise typer.Exit(code=1)

# --- Integration with Typer App --- 
# English: Create an instance of the controller.
# 日本語: コントローラーのインスタンスを作成します。
controller = CliController()

# English: Modify the Typer command functions in cli_parser to call the controller methods.
# 日本語: cli_parser の Typer コマンド関数を修正して、コントローラーメソッドを呼び出します。
# This requires modifying the cli_parser.py file or structuring the project differently (e.g., passing controller).
# これには、cli_parser.pyファイルを変更するか、プロジェクトの構造を異なる方法で構成する必要があります（例：コントローラーを渡す）。

# For demonstration, let's assume cli_parser.py is modified like this:
# (This code won't run directly here, it shows the intended link)
'''
# In src/kotemari/gateway/cli_parser.py

from kotemari.controller.cli_controller import controller

@app.command()
def analyze(project_path: Path = ...):
    controller.analyze_project(project_path)

@app.command()
def dependencies(file_path: Path = ..., project_path: Path = ...):
    controller.show_dependencies(file_path, project_path)

@app.command()
def context(target_files: List[Path] = ..., project_path: Path = ...):
    controller.generate_context(target_files, project_path)

@app.command()
def watch(project_path: Path = ...):
    controller.start_watching(project_path)
    # Remove the while True loop and KeyboardInterrupt handling from here
    # ここから while True ループと KeyboardInterrupt 処理を削除します

''' 