import typer
from typing_extensions import Annotated
from pathlib import Path
import logging
from typing import List, Optional

from ..controller.cli_controller import CliController

# Basic logger setup (adjust level and format as needed)
# Use a specific logger name to avoid interfering with other libraries
# 他のライブラリとの干渉を避けるために特定のロガー名を使用
kotemari_cli_logger = logging.getLogger("kotemari_cli")
logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(name)s: %(message)s') # Default level WARN

app = typer.Typer(help="Kotemari: Analyze Python projects and manage context for LLMs.")

# --- Common Type Annotations with Options ---
# Define Annotated types for common options BEFORE they are used in callback
ProjectType = Annotated[
    Path,
    typer.Option(
        "--project-root", "-p",
        help="Path to the project root directory.",
        exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True,
    )
]

ConfigType = Annotated[
    Optional[Path],
    typer.Option(
        "--config", "-c",
        help="Path to the Kotemari configuration file (.kotemari.yml).",
        exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True
    )
]

# Verbosity option using count for multiple levels (-v, -vv)
# 複数レベル（-v、-vv）のためのカウントを使用した冗長性オプション
Verbosity = Annotated[
    int,
    typer.Option("--verbose", "-v", count=True, help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
]

class GlobalState:
    """ Class to hold global state passed via ctx.obj """
    def __init__(self):
        self.controller: Optional[CliController] = None
        self.log_level: int = logging.WARNING # Store log level determined in callback

@app.callback()
def main_callback(
    ctx: typer.Context,
    project_root: ProjectType = Path("."), # Now ProjectType is defined
    config_path: ConfigType = None,       # Now ConfigType is defined
    use_cache: Annotated[bool, typer.Option(help="Use cached analysis results if available and valid.")] = True,
    verbosity: Verbosity = 0             # Use the new Verbosity type
):
    """
    Main callback for Kotemari CLI. Initializes the controller and sets logging level.
    Kotemari CLI のメインコールバック。コントローラーを初期化し、ログレベルを設定します。
    """
    # Determine log level based on verbosity count
    # 冗長性カウントに基づいてログレベルを決定
    if verbosity == 1:
        log_level = logging.INFO
    elif verbosity >= 2:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING # Default

    # # Remove existing handlers from root logger to avoid duplication in tests (Temporarily disabled for debugging)
    # # テストでの重複を避けるためにルートロガーから既存のハンドラーを削除 (デバッグのため一時的に無効化)
    # root_logger = logging.getLogger()
    # if root_logger.hasHandlers():
    #     for handler in root_logger.handlers[:]: # Iterate over a copy
    #         root_logger.removeHandler(handler)

    # Configure the root logger or a specific app logger
    # Simplify basicConfig call for debugging
    # ルートロガーまたは特定のアプリロガーを設定 (デバッグのため basicConfig 呼び出しを簡略化)
    # logging.basicConfig(level=log_level, format='[%(levelname)s] %(name)s: %(message)s', force=True)
    logging.basicConfig(level=log_level, format='[%(levelname)s] %(name)s: %(message)s') # Use default (no force=True)
    
    # Ensure the specific logger level is also set
    # 特定のロガーレベルも設定されていることを確認
    kotemari_cli_logger.setLevel(log_level) 
    kotemari_cli_logger.info(f"CLI Log level set to: {logging.getLevelName(log_level)}")

    # Initialize state and controller
    ctx.obj = GlobalState()
    # Pass the determined log_level to the controller/Kotemari instance
    # 決定された log_level をコントローラー/Kotemari インスタンスに渡す
    ctx.obj.log_level = log_level # Store log level in state
    ctx.obj.controller = CliController(
        project_root=str(project_root),
        config_path=str(config_path) if config_path else None,
        use_cache=use_cache,
        log_level=log_level # Pass log level to Controller constructor
    )
    kotemari_cli_logger.debug(f"Controller initialized in callback for project: {project_root} with log level {logging.getLevelName(log_level)}")

# --- Commands ---

@app.command()
def analyze(
    ctx: typer.Context,
    verbosity: Verbosity = 0 # Required for Typer to parse -v/-vv for this command
):
    """Analyze the project structure, dependencies, and file information."""
    controller: CliController = ctx.obj.controller
    if not controller:
        kotemari_cli_logger.error("Controller not initialized.")
        raise typer.Exit(code=1)
        
    # Controller already has project_root etc. from callback
    kotemari_cli_logger.info(f"Analyzing project at: {controller.project_root}") 
    controller.analyze(ctx)

@app.command()
def dependencies(
    ctx: typer.Context,
    target_file: Annotated[Path, typer.Argument(help="Path to the Python file to get dependencies for.", 
                                                exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)],
    verbosity: Verbosity = 0 # Add verbosity option
):
    """Show dependencies for a specific Python file within the project."""
    controller: CliController = ctx.obj.controller
    if not controller:
        kotemari_cli_logger.error("Controller not initialized.")
        raise typer.Exit(code=1)

    kotemari_cli_logger.info(f"Getting dependencies for: {target_file}")
    controller.show_dependencies(ctx, str(target_file))

@app.command()
def context(
    ctx: typer.Context,
    target_files: Annotated[List[Path], typer.Argument(help="Paths to the target files to include in the context.",
                                                      exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)],
    verbosity: Verbosity = 0 # Add verbosity option
):
    """Generate a context string from specified files for LLM input."""
    controller: CliController = ctx.obj.controller
    if not controller:
        kotemari_cli_logger.error("Controller not initialized.")
        raise typer.Exit(code=1)

    kotemari_cli_logger.info(f"Generating context for: {', '.join(map(str, target_files))}")
    target_file_strs = [str(p) for p in target_files]
    controller.generate_context(ctx, target_file_strs)

# New CLI command to list files in the project directory
@app.command("list")
def list_cmd(
    ctx: typer.Context,
    verbosity: Verbosity = 0 # Add verbosity option
):
    """Lists all files in the given project root (respecting ignore rules)."""
    controller: CliController = ctx.obj.controller
    if not controller:
        kotemari_cli_logger.error("Controller not initialized.")
        raise typer.Exit(code=1)
        
    kotemari_cli_logger.info(f"Listing files for: {controller.project_root}")
    controller.display_list(ctx)

# New CLI command to display the tree structure of the project directory
@app.command("tree")
def tree_cmd(
    ctx: typer.Context,
    verbosity: Verbosity = 0 # Add verbosity option
):
    """Displays the tree structure of the project directory (respecting ignore rules)."""
    controller: CliController = ctx.obj.controller
    if not controller:
        kotemari_cli_logger.error("Controller not initialized.")
        raise typer.Exit(code=1)

    kotemari_cli_logger.info(f"Displaying tree for: {controller.project_root}")
    controller.display_tree(ctx)

# --- Entry point for CLI --- 
def main():
    app()

if __name__ == "__main__":
    main() 