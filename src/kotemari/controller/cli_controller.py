from pathlib import Path
from typing import List, Optional, Dict, Any
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

    def _get_kotemari_instance(self, ctx: typer.Context) -> Kotemari:
        """Gets or initializes the Kotemari instance."""
        project_path_str = ctx.params.get('project_root', '.')
        config_path_str = ctx.params.get('config_path')
        log_level_str = ctx.params.get('log_level', 'INFO')

        # Convert project_root to Path object
        # project_root を Path オブジェクトに変換
        project_path = Path(project_path_str).resolve()
        config_path = Path(config_path_str).resolve() if config_path_str else None

        # Configure logging based on the log_level parameter
        # log_level パラメータに基づいてロギングを設定
        numeric_level = getattr(logging, log_level_str.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {log_level_str}')
        logging.basicConfig(level=numeric_level, format='[%(levelname)s] %(message)s')

        # Initialize Kotemari instance if not already done
        # まだ初期化されていない場合は Kotemari インスタンスを初期化
        if not self._kotemari_instance:
            try:
                self._kotemari_instance = Kotemari(
                    project_root=project_path,
                    config_path=config_path,
                    log_level=numeric_level
                )
            except Exception as e:
                logger.error(f"Failed to initialize Kotemari: {e}", exc_info=True)
                raise typer.Exit(code=1)
        return self._kotemari_instance

    def analyze(self, ctx: typer.Context):
        """
        Analyzes the project and displays a summary.
        プロジェクトを分析し、要約を表示します。
        """
        instance = self._get_kotemari_instance(ctx)
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

    def show_dependencies(self, ctx: typer.Context, target_file_path: str):
        """
        Shows dependencies for a specific file.
        特定のファイルの依存関係を表示します。
        Args:
            target_file_path: Path to the target file.
                             ターゲットファイルへのパス。
        """
        instance = self._get_kotemari_instance(ctx)
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

    def generate_context(self, ctx: typer.Context, target_file_paths: List[str]):
        """
        Generates and prints the context string for the given files.
        指定されたファイルのコンテキスト文字列を生成して表示します。
        Args:
            target_file_paths: List of paths to the target files.
                               ターゲットファイルへのパスのリスト。
        """
        instance = self._get_kotemari_instance(ctx)
        try:
            # Ensure analysis is done
            instance.analyze_project()
            context_data = instance.get_context(target_file_paths)

            # Use rich.Syntax for potential highlighting (detect language if possible)
            # 潜在的なハイライトのために rich.Syntax を使用します（可能であれば言語を検出）
            # Simple print for now
            # 今はシンプルな print
            # self.console.print(Panel(context_string, title="Generated Context", border_style="blue"))
            # self.console.print(context_string) # Old: Direct print
            self.console.print(context_data.context_string) # Corrected: print the string attribute

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

    def display_list(self, ctx: typer.Context):
        """Analyzes the project and displays the list of files (respecting ignores).
        プロジェクトを解析し、ファイルリスト（無視ルール適用後）を表示します。
        """
        try:
            logger.debug("display_list: Getting analysis results...")
            analyzed_files: list[FileInfo] = self._get_kotemari_instance(ctx).analyze_project()
            logger.debug(f"display_list: Got {len(analyzed_files)} files.")
            if not analyzed_files:
                self.console.print("No files found in the project (after applying ignore rules).")
                return

            self.console.print("Files (respecting ignore rules):")
            for file_info in sorted(analyzed_files, key=lambda f: f.path):
                relative_path = file_info.path.relative_to(self._get_kotemari_instance(ctx).project_root)
                self.console.print(f"  {relative_path}")
            logger.debug("display_list: Finished printing files.")
        except Exception as e:
            logger.error(f"Error during file listing: {e}", exc_info=True)
            console.print(f"[bold red]An unexpected error occurred while listing files:[/bold red] {e}")
            console.print_exception(show_locals=True)
            raise typer.Exit(code=1)

    def display_tree(self, ctx: typer.Context):
        """Analyzes the project and displays the file tree (respecting ignores).
        プロジェクトを解析し、ファイルツリー（無視ルール適用後）を表示します。
        """
        try:
            logger.debug("display_tree: Getting analysis results...")
            analyzed_files: list[FileInfo] = self._get_kotemari_instance(ctx).analyze_project()
            logger.debug(f"display_tree: Got {len(analyzed_files)} files.")
            if not analyzed_files:
                self.console.print("No files found to build tree (after applying ignore rules).")
                return

            # Build and display tree using rich
            # rich を使用してツリーを構築および表示
            project_root_instance = self._get_kotemari_instance(ctx).project_root # Get root path once
            tree = Tree(f":open_file_folder: [bold blue]{project_root_instance.name}")
            nodes: Dict[Path, Tree] = {project_root_instance: tree} # Map paths to Tree nodes

            logger.debug("display_tree: Starting tree construction.")
            # Sort files to ensure consistent tree structure
            # 一貫したツリー構造を確保するためにファイルをソート
            sorted_files = sorted(analyzed_files, key=lambda f: f.path)

            for file_info in sorted_files:
                path = file_info.path
                current_parent_path = project_root_instance
                current_parent_node = tree

                # Iterate through parent directories relative to project root
                # プロジェクトルートからの相対的な親ディレクトリを反復処理
                relative_path = path.relative_to(project_root_instance)
                for part in relative_path.parts[:-1]: # Iterate over directory parts
                    current_child_path = current_parent_path / part
                    # Find or create the node for this directory part
                    # このディレクトリ部分のノードを見つけるか作成する
                    child_node = nodes.get(current_child_path)
                    if child_node is None:
                        # logger.debug(f"Adding node for dir: {current_child_path}")
                        child_node = current_parent_node.add(f":folder: {part}")
                        nodes[current_child_path] = child_node
                    current_parent_path = current_child_path
                    current_parent_node = child_node

                # Add the file node to the correct parent directory node
                # 正しい親ディレクトリノードにファイルノードを追加
                # logger.debug(f"Adding node for file: {path.name} under {current_parent_path}")
                current_parent_node.add(f":page_facing_up: {path.name}")

            logger.debug("display_tree: Finished tree construction.")
            self.console.print(tree)
            logger.debug("display_tree: Finished printing tree.")

        except Exception as e:
            logger.error(f"Error during tree display: {e}", exc_info=True)
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