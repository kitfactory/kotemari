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

# Use the specific logger name defined in cli_parser
# cli_parser で定義された特定のロガー名を使用
logger = logging.getLogger("kotemari_cli")

console = Console()

class CliController:
    """
    Handles the logic for CLI commands, interfacing with the Kotemari core library.
    CLIコマンドのロジックを処理し、Kotemariコアライブラリとのインターフェースを提供します。
    """
    def __init__(self, project_root: str, config_path: Optional[str] = None, use_cache: bool = True, log_level: int = logging.WARNING):
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
            log_level: The logging level to pass to the Kotemari instance.
                       Kotemari インスタンスに渡すログレベル。
        """
        self.project_root = project_root
        self.config_path = config_path
        self.use_cache = use_cache # Store cache preference
        self.log_level = log_level # Store log level
        # Lazy initialization of Kotemari instance
        # Kotemari インスタンスの遅延初期化
        self._kotemari_instance: Optional[Kotemari] = None
        self.console = Console()

    def _get_kotemari_instance(self, ctx: typer.Context) -> Kotemari:
        """Gets or initializes the Kotemari instance, using log level from callback."""
        if self._kotemari_instance:
            return self._kotemari_instance

        # Retrieve log_level from the context object set in the callback
        # コールバックで設定されたコンテキストオブジェクトから log_level を取得
        global_state = ctx.obj
        if not global_state or not hasattr(global_state, 'log_level'):
            # Fallback if state is somehow missing (shouldn't happen with callback)
            # 状態が何らかの理由で見つからない場合のフォールバック（コールバックでは発生しないはず）
            logger.warning("Global state or log_level not found in context, falling back to controller default.")
            determined_log_level = self.log_level
        else:
            determined_log_level = global_state.log_level
            logger.debug(f"Using log level from context: {logging.getLevelName(determined_log_level)}")

        # Initialize Kotemari instance if not already done
        # まだ初期化されていない場合は Kotemari インスタンスを初期化
        try:
            self._kotemari_instance = Kotemari(
                project_root=self.project_root, # Use resolved path from __init__
                config_path=self.config_path,
                log_level=determined_log_level # Pass the determined log level
            )
            logger.info(f"Kotemari instance created with log level: {logging.getLevelName(determined_log_level)}")
        except Exception as e:
            logger.error(f"Failed to initialize Kotemari: {e}", exc_info=True)
            console.print(f"[bold red]Initialization Error:[/bold red] {e}")
            raise typer.Exit(code=1)
        return self._kotemari_instance

    def analyze(self, ctx: typer.Context):
        """
        Analyzes the project and displays a summary.
        プロジェクトを分析し、要約を表示します。
        """
        instance = self._get_kotemari_instance(ctx)
        try:
            logger.info("Starting project analysis via CLI controller...")
            analyzed_files = instance.analyze_project(force_reanalyze=False)
            logger.info(f"Analysis complete. Found {len(analyzed_files)} files.")
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
            logger.info(f"Fetching dependencies for {target_file_path}...")
            instance.analyze_project() # Ensure analysis results are loaded/up-to-date
            
            dependencies = instance.get_dependencies(target_file_path)
            logger.info(f"Found {len(dependencies)} dependencies for {target_file_path}.")
            
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
                # This condition might be redundant given the check above
                # 上記のチェックを考えると、この条件は冗長かもしれません
                return

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
            # Removed hint about running analyze, as it's called within the method now
            # メソッド内で呼び出されるようになったため、analyze の実行に関するヒントを削除
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
            logger.info(f"Generating context for files: {', '.join(target_file_paths)}")
            instance.analyze_project() # Ensure analysis results are loaded/up-to-date
            context_data = instance.get_context(target_file_paths)
            logger.info("Context generated successfully.")

            # Use rich.Syntax for potential highlighting (detect language if possible)
            # 潜在的なハイライトのために rich.Syntax を使用します（可能であれば言語を検出）
            # Simple print for now
            # 今はシンプルな print
            # self.console.print(Panel(context_string, title="Generated Context", border_style="blue"))
            # self.console.print(context_string) # Old: Direct print
            self.console.print(context_data.context_string) # Corrected: print the string attribute

        except FileNotFoundErrorInAnalysis as e:
            console.print(f"[bold red]Error generating context:[/bold red] {e}")
            # Removed hint about analysis, as it's called within the method
            # メソッド内で呼び出されるため、分析に関するヒントを削除
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
            logger.info("Listing project files via CLI controller...")
            analyzed_files: list[FileInfo] = self._get_kotemari_instance(ctx).analyze_project()
            logger.debug(f"display_list: Got {len(analyzed_files)} files.")
            if not analyzed_files:
                self.console.print("No files found in the project (after applying ignore rules).")
                return

            self.console.print("Files (respecting ignore rules):")
            # Use the instance's project_root consistently
            # インスタンスの project_root を一貫して使用
            project_root_instance = self._get_kotemari_instance(ctx).project_root
            for file_info in sorted(analyzed_files, key=lambda f: f.path):
                # Calculate relative path correctly
                # 相対パスを正しく計算
                try:
                    relative_path = file_info.path.relative_to(project_root_instance)
                    self.console.print(f"  {relative_path}")
                except ValueError:
                    # Handle case where file path is not under project root (should not happen with proper analysis)
                    # ファイルパスがプロジェクトルートの下にない場合の処理（適切な分析では発生しないはず）
                    logger.warning(f"File path {file_info.path} is not relative to project root {project_root_instance}. Skipping display.")
                    self.console.print(f"  {file_info.path} (Absolute Path)") # Display absolute path as fallback

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
            logger.info("Displaying project file tree via CLI controller...")
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

            # Use the instance's project_root consistently
            # インスタンスの project_root を一貫して使用
            for file_info in sorted(analyzed_files, key=lambda f: f.path):
                try:
                    relative_path = file_info.path.relative_to(project_root_instance)
                    parts = list(relative_path.parts)
                    current_node = tree
                    current_path = project_root_instance
                    for i, part in enumerate(parts):
                        current_path = current_path / part
                        if i == len(parts) - 1: # File node
                            # Add file node to its parent directory node
                            # ファイルノードを親ディレクトリノードに追加
                            parent_node = nodes.get(current_path.parent, tree)
                            parent_node.add(f":page_facing_up: {part}")
                        else: # Directory node
                            if current_path not in nodes:
                                # Add directory node if it doesn't exist
                                # ディレクトリノードが存在しない場合は追加
                                parent_node = nodes.get(current_path.parent, tree)
                                new_node = parent_node.add(f":folder: [bold]{part}")
                                nodes[current_path] = new_node
                            current_node = nodes[current_path]
                except ValueError:
                    logger.warning(f"Skipping file for tree display: {file_info.path} is not relative to {project_root_instance}")

            self.console.print(tree)
            logger.debug("display_tree: Finished displaying tree.")

        except Exception as e:
            logger.error(f"Error during tree display: {e}", exc_info=True)
            console.print(f"[bold red]An unexpected error occurred while displaying the tree:[/bold red] {e}")
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