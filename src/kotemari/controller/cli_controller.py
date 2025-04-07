from pathlib import Path
from typing import List, Optional
import logging
import sys
import traceback

from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.tree import Tree

from ..core import Kotemari
from ..domain.dependency_info import DependencyType
from ..domain.file_info import FileInfo
import typer # Typer needed for exit

from ..domain.exceptions import KotemariError, FileNotFoundErrorInAnalysis # Import custom exceptions

# English: Use rich for better console output formatting.
# 日本語: より良いコンソール出力フォーマットのために rich を使用します。

# Basic logger setup (adjust level and format as needed)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

console = Console()

class CliController:
    """
    Handles the logic for CLI commands, interfacing with the Kotemari core library.
    CLIコマンドのロジックを処理し、Kotemariコアライブラリとのインターフェースを提供します。
    """
    def __init__(self, project_root: str, config_path: Optional[str] = None, use_cache: bool = True):
        """
        Initializes the controller with project context.
        プロジェクトコンテキストでコントローラーを初期化します。

        Args:
            project_root: The absolute path to the project root directory.
                          プロジェクトルートディレクトリへの絶対パス。
            config_path: Optional path to the configuration file.
                         設定ファイルへのオプションのパス。
            use_cache: Whether the Kotemari instance should use caching.
                       Kotemari インスタンスがキャッシュを使用するかどうか。
        """
        self.project_root = project_root
        self.config_path = config_path
        self.use_cache = use_cache # Store cache preference
        # Lazy initialization of Kotemari instance
        # Kotemari インスタンスの遅延初期化
        self._kotemari_instance: Optional[Kotemari] = None
        self.console = Console()

    def _get_kotemari_instance(self) -> Kotemari:
        """Gets or initializes the Kotemari instance."""
        if self._kotemari_instance is None:
            try:
                logger.debug(f"Initializing Kotemari for project: {self.project_root}, config: {self.config_path}, use_cache: {self.use_cache}")
                # Pass the stored use_cache preference to Kotemari constructor
                # 保存された use_cache 設定を Kotemari コンストラクタに渡します
                self._kotemari_instance = Kotemari(
                    project_root=self.project_root, 
                    config_path=self.config_path,
                    use_cache=self.use_cache # Pass the flag here
                )
                logger.debug("Kotemari instance initialized successfully.")
            except Exception as e:
                logger.exception(f"Failed to initialize Kotemari: {e}")
                self.console.print(f"[bold red]Error:[/bold red] Failed to initialize project analysis: {e}")
                raise typer.Exit(code=1)
        return self._kotemari_instance

    def analyze_and_display(self):
        """
        Analyzes the project and displays a summary.
        プロジェクトを分析し、要約を表示します。
        """
        instance = self._get_kotemari_instance()
        try:
            analyzed_files = instance.analyze_project(force_reanalyze=False)
            self._display_analysis_summary(analyzed_files)
        except KotemariError as e:
            console.print(f"[bold red]Analysis Error:[/bold red] {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred during analysis:[/bold red] {e}")
            console.print_exception(show_locals=True)
            raise typer.Exit(code=1)

    def _display_analysis_summary(self, analyzed_files: list):
        """Displays the analysis summary in a table format.
        解析結果の要約をテーブル形式で表示します。
        """
        table = Table(title="Analysis Summary", show_header=False, box=box.ROUNDED)
        table.add_row("Total Files Analyzed", str(len(analyzed_files)))
        self.console.print(table)

    def show_dependencies(self, target_file_path: str):
        """
        Shows dependencies for a specific file.
        特定のファイルの依存関係を表示します。
        Args:
            target_file_path: Path to the target file.
                             ターゲットファイルへのパス。
        """
        instance = self._get_kotemari_instance()
        try:
            # Ensure analysis is done first, preferably using cache
            # まず分析が完了していることを確認します（できればキャッシュを使用）
            instance.analyze_project()
            
            dependencies = instance.get_dependencies(target_file_path)
            
            if not dependencies:
                self.console.print(f"No dependencies found for: [cyan]{target_file_path}[/cyan]")
                return

            # Prepare data for the table
            # テーブル用のデータを準備します
            dependency_data = []
            for dep in dependencies:
                # Check the DependencyType enum to determine if internal or external
                # DependencyType enum をチェックして内部か外部かを判断します
                if dep.dependency_type in (DependencyType.INTERNAL_RELATIVE, DependencyType.INTERNAL_ABSOLUTE):
                    dep_type = "Internal"
                else:
                    dep_type = "External"
                # dep_type = "Internal" if dep.is_internal else "External" # OLD WAY
                dependency_data.append((dep.module_name, dep_type))

            if not dependency_data:
                self.console.print("  No dependencies found.")

            table = Table(title=f"Dependencies for: {Path(target_file_path).name}")
            table.add_column("Imported Module", style="cyan")
            table.add_column("Type", style="magenta")
            # table.add_column("Source File (if internal)", style="green") # Comment out for now

            # Sort the prepared data by module name
            # 準備したデータをモジュール名でソートします
            for module_name, dep_type in sorted(dependency_data, key=lambda d: d[0]):
                table.add_row(module_name, dep_type) # Removed source_file display
                # source_file = str(dep[0]) if dep_type == "Internal" else "N/A"
                # table.add_row(dep[0], dep_type, source_file)

            self.console.print(table)

        except FileNotFoundErrorInAnalysis as e:
            console.print(f"[bold red]Dependency Error:[/bold red] {e}")
            console.print(f"Hint: Have you run 'kotemari analyze' for this project yet?")
            raise typer.Exit(code=1)
        except KotemariError as e:
            console.print(f"[bold red]Dependency Error:[/bold red] {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred while getting dependencies:[/bold red] {e}")
            console.print_exception(show_locals=True)
            raise typer.Exit(code=1)

    def generate_context(self, target_file_paths: List[str]):
        """
        Generates and prints the context string for the given files.
        指定されたファイルのコンテキスト文字列を生成して表示します。
        Args:
            target_file_paths: List of paths to the target files.
                               ターゲットファイルへのパスのリスト。
        """
        instance = self._get_kotemari_instance()
        try:
            # Ensure analysis is done
            instance.analyze_project()
            context_string = instance.get_context(target_file_paths)
            
            # Use rich.Syntax for potential highlighting (detect language if possible)
            # 潜在的なハイライトのために rich.Syntax を使用します（可能であれば言語を検出）
            # Simple print for now
            # 今はシンプルな print
            # self.console.print(Panel(context_string, title="Generated Context", border_style="blue"))
            self.console.print(context_string) # Direct print as per current formatter output

        except FileNotFoundErrorInAnalysis as e:
            console.print(f"[bold red]Error generating context:[/bold red] {e}")
            console.print(f"Hint: Make sure the file exists and was included in the analysis.")
            raise typer.Exit(code=1)
        except KotemariError as e:
            console.print(f"[bold red]Context Generation Error:[/bold red] {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred during context generation:[/bold red] {e}")
            console.print_exception(show_locals=True)
            raise typer.Exit(code=1)

    def display_list(self):
        """Analyzes the project and displays the list of files (respecting ignores).
        プロジェクトを解析し、ファイルリスト（無視ルール適用後）を表示します。
        """
        try:
            analyzed_files: list[FileInfo] = self._get_kotemari_instance().analyze_project() # Ensure analysis is done
            if not analyzed_files:
                self.console.print("No files found in the project (after applying ignore rules).")
                return

            self.console.print("Files (respecting ignore rules):")
            # Extract relative paths and sort them
            # 相対パスを抽出し、ソートします
            relative_paths = sorted([str(file_info.path.relative_to(self.project_root).as_posix()) for file_info in analyzed_files])
            for path_str in relative_paths:
                self.console.print(path_str)

        except KotemariError as e:
            self.console.print(f"[bold red]Error listing files:[/bold red] {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            self.console.print(f"[bold red]An unexpected error occurred while listing files:[/bold red] {e}")
            self.console.print_exception(show_locals=True)
            raise typer.Exit(code=1)

    def display_tree(self):
        """Analyzes the project and displays the file tree (respecting ignores).
        プロジェクトを解析し、ファイルツリー（無視ルール適用後）を表示します。
        """
        try:
            analyzed_files: list[FileInfo] = self._get_kotemari_instance().analyze_project() # Ensure analysis is done
            if not analyzed_files:
                self.console.print("No files found to build tree (after applying ignore rules).")
                return

            tree = Tree(f":open_file_folder: [link file://{self.project_root}]{self.project_root.name}")

            # Build a directory structure from the file paths
            # ファイルパスからディレクトリ構造を構築します
            structure: dict = {}
            relative_paths = sorted([file_info.path.relative_to(self.project_root) for file_info in analyzed_files])

            for path in relative_paths:
                current_level = structure
                parts = path.parts
                for i, part in enumerate(parts):
                    if i == len(parts) - 1: # It's a file
                        current_level[part] = None # Mark as file
                    else: # It's a directory
                        if part not in current_level:
                            current_level[part] = {}
                        current_level = current_level[part]

            # Recursively build the rich Tree
            # rich Tree を再帰的に構築します
            def add_nodes(branch: Tree, structure_level: dict):
                items = sorted(structure_level.items())
                for i, (name, content) in enumerate(items):
                    is_last = i == len(items) - 1
                    style = "" if is_last else "dim"
                    if content is None: # File
                        branch.add(f":page_facing_up: {name}", style=style)
                    else: # Directory
                        new_branch = branch.add(f":folder: {name}", style=style)
                        add_nodes(new_branch, content)

            add_nodes(tree, structure)
            self.console.print(tree)

        except KotemariError as e:
            # Use standard traceback printing to stderr for better capture by subprocess
            # subprocess によるキャプチャ向上のため、標準の traceback を stderr に出力します
            print(f"[bold red]Error displaying tree:[/bold red]", file=sys.stderr)
            print(f"Exception Type: {type(e).__name__}", file=sys.stderr)
            print(f"Exception Details: {e}", file=sys.stderr)
            print("Traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            raise typer.Exit(code=1)
        except Exception as e:
            console = Console()
            console.print(f"[bold red]An unexpected error occurred while displaying tree:[/bold red] {e}")
            console.print_exception(show_locals=True)
            raise typer.Exit(code=1)

    def start_watching(self, targets: list[str] | None = None):
        """Starts watching the project directory for changes.
        プロジェクトディレクトリの変更監視を開始します。
        """
        # Implementation of start_watching method
        pass

# --- Integration with Typer App --- 
# English: Remove the outdated controller instantiation.
# 日本語: 古いコントローラーのインスタンス化を削除します。
# The controller is now instantiated within each command function in cli_parser.py
# コントローラーは cli_parser.py の各コマンド関数内でインスタンス化されるようになりました
# controller = CliController() # REMOVE THIS LINE

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
    controller.show_dependencies(str(file_path))

@app.command()
def context(target_files: List[Path] = ..., project_path: Path = ...):
    controller.generate_context([str(f) for f in target_files])

@app.command()
def watch(project_path: Path = ...):
    controller.start_watching(project_path)
    # Remove the while True loop and KeyboardInterrupt handling from here
    # ここから while True ループと KeyboardInterrupt 処理を削除します

''' 