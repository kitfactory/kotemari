from pathlib import Path
from typing import List, Optional
import logging

from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich import box

from ..core import Kotemari
from ..domain.dependency_info import DependencyType
import typer # Typer needed for exit

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
            analysis_results = instance.analyze_project()
            
            logger.info("Analysis complete.")

            # Display summary in a table
            table = Table(title="Analysis Summary", show_header=False, box=box.ROUNDED)
            # table.add_row("Project Root", str(instance.project_root))
            # table.add_row("Config File", str(instance.config_path) if instance.config_path else "Default")
            # table.add_row("Cache Status", "Enabled" if instance.use_cache else "Disabled")
            # table.add_row("Cache File", str(instance.cache_manager.cache_file_path) if instance.use_cache else "N/A")
            table.add_row("Total Files Analyzed", str(len(analysis_results))) # Corrected: Get length of the list directly

            console.print(table)
        except FileNotFoundError as e:
            logger.error(f"Target file not found in analysis: {e}")
            self.console.print(f"[bold red]Error:[/bold red] Target file not found: {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Error during analysis: {e}")
            self.console.print(f"[bold red]Error:[/bold red] Analysis failed: {e}")
            raise typer.Exit(code=1)

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

        except FileNotFoundError as e:
            logger.error(f"Target file not found in analysis: {e}")
            self.console.print(f"[bold red]Error:[/bold red] Target file not found: {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Error getting dependencies: {e}")
            self.console.print(f"[bold red]Error:[/bold red] Failed to get dependencies: {e}")
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

        except FileNotFoundError as e:
            logger.error(f"Target file not found for context generation: {e}")
            self.console.print(f"[bold red]Error:[/bold red] Target file not found: {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Error generating context: {e}")
            self.console.print(f"[bold red]Error:[/bold red] Failed to generate context: {e}")
            raise typer.Exit(code=1)

    # TODO: Implement methods for list, tree, watch commands
    #       list, tree, watch コマンド用のメソッドを実装します

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