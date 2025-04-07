import typer
from typing_extensions import Annotated
from pathlib import Path
import logging
from typing import List, Optional

from ..controller.cli_controller import CliController

# Basic logger setup (adjust level and format as needed)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = typer.Typer(help="Kotemari: Analyze Python projects and manage context for LLMs.")

# Initialize controller (consider how to pass dependencies like Kotemari instance)
# For now, we might instantiate Kotemari inside each command or pass it via state
# Controllerを初期化します（Kotemariインスタンスなどの依存関係を渡す方法を検討します）
# 現時点では、各コマンド内で Kotemari をインスタンス化するか、state を介して渡すことが考えられます
# Note: Direct instantiation here might not be ideal for testing/dependency injection
# 注意: ここでの直接的なインスタンス化は、テスト/依存性注入には理想的ではない可能性があります
# controller = CliController() # Placeholder

# --- Common Type Annotations with Options --- 
# Define Annotated types for common options to reuse them
# 再利用するために共通オプションの Annotated 型を定義します
ProjectType = Annotated[
    Path,
    typer.Option(
        "--project-root", "-p", 
        help="Path to the project root directory.",
        exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True
    )
]

ConfigType = Annotated[
    Optional[Path], # Use Optional from typing
    typer.Option(
        "--config", "-c", 
        help="Path to the Kotemari configuration file (.kotemari.yml).",
        exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True
    )
]

VerboseType = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable verbose output.")
]

# --- Commands --- 

@app.command()
def analyze(
    project_root: Annotated[
        Path,
        typer.Argument(
            help="Path to the project root directory to analyze.",
            exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True,
            show_default=True # Show default value in help
        )
    ] = Path("."), # Default to current directory
    config_path: ConfigType = None,       # Use the defined Annotated type
    use_cache: Annotated[bool, typer.Option(help="Use cached analysis results if available and valid.")] = True,
    verbose: VerboseType = False          # Use the defined Annotated type
):
    """Analyze the project structure, dependencies, and file information."""
    if verbose:
        logging.getLogger("kotemari").setLevel(logging.DEBUG)
        logger.info(f"Verbose mode enabled.")
    
    controller = CliController(
        project_root=str(project_root), 
        config_path=str(config_path) if config_path else None,
        use_cache=use_cache
    )
    logger.info(f"Analyzing project at: {project_root}")
    controller.analyze_and_display()

@app.command()
def dependencies(
    target_file: Annotated[Path, typer.Argument(help="Path to the Python file to get dependencies for.", 
                                                exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)],
    project_root: ProjectType = Path("."),
    config_path: ConfigType = None,
    verbose: VerboseType = False
):
    """Show dependencies for a specific Python file within the project."""
    if verbose:
        logging.getLogger("kotemari").setLevel(logging.DEBUG)
        logger.info(f"Verbose mode enabled.")

    controller = CliController(project_root=str(project_root), config_path=str(config_path) if config_path else None)
    logger.info(f"Getting dependencies for: {target_file}")
    controller.show_dependencies(str(target_file))

@app.command()
def context(
    target_files: Annotated[List[Path], typer.Argument(help="Paths to the target files to include in the context.",
                                                      exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)], # Corrected type hint
    project_root: ProjectType = Path("."),
    config_path: ConfigType = None,
    # include_dependencies: Annotated[bool, typer.Option(help="Include related files based on dependencies.")] = False, # Future feature
    verbose: VerboseType = False
):
    """Generate a context string from specified files for LLM input."""
    if verbose:
        logging.getLogger("kotemari").setLevel(logging.DEBUG)
        logger.info(f"Verbose mode enabled.")

    controller = CliController(project_root=str(project_root), config_path=str(config_path) if config_path else None)
    logger.info(f"Generating context for: {', '.join(map(str, target_files))}")
    target_file_strs = [str(p) for p in target_files]
    controller.generate_context(target_file_strs)

# New CLI command to list files in the project directory
@app.command("list")
def list_files(project_root: str):
    """Lists all files in the given project root.
    指定されたプロジェクトルート内の全ファイルを一覧表示します。

    Args:
        project_root (str): The path to the project directory.
                              プロジェクトディレクトリへのパス。
    """
    from pathlib import Path
    p = Path(project_root)
    if not p.exists():
        typer.echo(f"Project directory {project_root} does not exist.")
        raise typer.Exit(code=1)
    files = [f.relative_to(p).as_posix() for f in p.glob("**/*") if f.is_file()]
    typer.echo("Files:")
    for file in sorted(files):
        typer.echo(file)

# New CLI command to display the tree structure of the project directory
@app.command("tree")
def tree_files(project_root: str):
    """Displays the tree structure of the project directory.
    プロジェクトディレクトリのツリー構造を表示します。

    Args:
        project_root (str): The path to the project directory.
                              プロジェクトディレクトリへのパス。
    """
    from pathlib import Path
    p = Path(project_root)
    if not p.is_absolute():
        p = p.resolve()
    if not p.exists():
        typer.echo(f"Project directory {project_root} does not exist.")
        raise typer.Exit(code=1)

    def rec_tree(path: Path, prefix: str = ""):
        """Recursively prints the tree structure.
        ツリー構造を再帰的に表示します。

        Args:
            path (Path): Current directory path.
                         現在のディレクトリのパス。
            prefix (str): The prefix for the current tree level.
                         現在のツリーレベルのプレフィックス。
        """
        children = list(path.iterdir())
        children.sort(key=lambda x: x.name)
        for i, child in enumerate(children):
            connector = "└── " if i == len(children)-1 else "├── "
            typer.echo(prefix + connector + child.name)
            if child.is_dir():
                extension = "    " if i == len(children)-1 else "│   "
                rec_tree(child, prefix + extension)

    typer.echo(f"{p.name}\n")
    rec_tree(p)

# --- Entry point for CLI --- 
def main():
    app()

if __name__ == "__main__":
    main() 