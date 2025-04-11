from pathlib import Path
from typing import List, Optional
import pathspec
import logging

logger = logging.getLogger(__name__)

class GitignoreReader:
    """
    Utility class to find and read .gitignore files in a project hierarchy.
    プロジェクト階層内の .gitignore ファイルを見つけて読み取るためのユーティリティクラス。
    """

    def __init__(self, project_root: Path):
        """
        Initializes the reader with the project root.
        プロジェクトルートでリーダーを初期化します。

        Args:
            project_root: The root directory of the project.
        """
        self.project_root = project_root.resolve()

    def find_gitignore_files(self) -> List[Path]:
        """
        Finds all .gitignore files starting from the project root up to its parent,
        and also includes .git/info/exclude if it exists.
        プロジェクトルートから親に向かってすべての .gitignore ファイルを検索し、
        .git/info/exclude が存在すればそれも含めます。

        Returns:
            List[Path]: A list of absolute paths to the found .gitignore files,
                      sorted for consistency.
                      見つかった .gitignore ファイルへの絶対パスのリスト（一貫性のためにソート済み）。
        """
        gitignore_files: List[Path] = []
        current_dir = self.project_root

        # Traverse upwards from project_root to find .gitignore files
        # project_root から上に向かって .gitignore ファイルを検索します
        while True:
            gitignore_path = current_dir / ".gitignore"
            if gitignore_path.is_file():
                gitignore_files.append(gitignore_path)
                logger.debug(f"Found .gitignore: {gitignore_path}")

            # Stop condition: Check if current_dir is the root or has no parent we should check
            # 停止条件: current_dir がルートであるか、チェックすべき親がないかを確認します
            if current_dir == self.project_root.anchor or current_dir.parent == current_dir:
                 break

            # Move to parent directory
            # 親ディレクトリに移動します
            current_dir = current_dir.parent
            # Avoid issues if project_root itself is the filesystem root or drive root
            if current_dir == self.project_root.parent and current_dir == current_dir.parent:
                 # This condition might be complex depending on OS and root definition
                 # この条件はOSやルート定義によって複雑になる可能性があります
                 pass # Allow one more check at parent if needed, loop condition handles termination


        # Read .git/info/exclude if exists
        git_info_exclude = self.project_root / ".git" / "info" / "exclude"
        if git_info_exclude.is_file():
            gitignore_files.append(git_info_exclude)
            logger.debug(f"Found .git/info/exclude: {git_info_exclude}")

        logger.info(f"Found {len(gitignore_files)} .gitignore files to consider.")
        return sorted(gitignore_files) # Return sorted list for consistency


    @staticmethod
    def read_gitignore_patterns(gitignore_path: Path) -> List[str]:
        """
        Reads patterns from a single .gitignore file, handling comments and empty lines.
        単一の .gitignore ファイルからパターンを読み取り、コメントと空行を処理します。

        Args:
            gitignore_path (Path): The path to the .gitignore file.
                                   .gitignore ファイルへのパス。

        Returns:
            List[str]: A list of non-empty, non-comment lines (patterns).
                       空でなくコメントでもない行（パターン）のリスト。
        """
        patterns: List[str] = []
        if not gitignore_path.is_file():
            logger.warning(f"Attempted to read non-existent gitignore file: {gitignore_path}")
            return patterns

        try:
            with gitignore_path.open('r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith('#'):
                        patterns.append(stripped_line)
            logger.debug(f"Read {len(patterns)} patterns from {gitignore_path}")
        except IOError as e:
            logger.error(f"Error reading gitignore file {gitignore_path}: {e}")
        except UnicodeDecodeError as e:
             logger.error(f"Encoding error reading gitignore file {gitignore_path}: {e}")

        return patterns

    @staticmethod
    def read(gitignore_path: Path) -> Optional[pathspec.PathSpec]:
        """
        Reads a single .gitignore file and returns a PathSpec object.
        Returns None if the file does not exist or cannot be read.
        単一の .gitignore ファイルを読み込み、PathSpec オブジェクトを返します。
        ファイルが存在しないか読み取れない場合は None を返します。

        Args:
            gitignore_path (Path): The absolute path to the .gitignore file.
                                   .gitignore ファイルへの絶対パス。

        Returns:
            Optional[pathspec.PathSpec]: A PathSpec object compiled from the gitignore rules,
                                         or None if the file is not found or empty.
                                         gitignore ルールからコンパイルされた PathSpec オブジェクト。
                                         ファイルが見つからないか空の場合は None。
        """
        if not gitignore_path.is_file():
            logger.debug(f".gitignore file not found at {gitignore_path}")
            return None

        try:
            with gitignore_path.open('r', encoding='utf-8') as f:
                patterns = f.readlines()
            # Filter out empty lines and comments
            # 空行とコメントを除外する
            patterns = [p.strip() for p in patterns if p.strip() and not p.strip().startswith('#')]
            if not patterns:
                logger.debug(f".gitignore file at {gitignore_path} is empty or contains only comments.")
                return None
            # pathspec uses the directory of the gitignore file as the root for pattern matching
            # pathspec は gitignore ファイルのディレクトリをパターンマッチングのルートとして使用します
            spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
            logger.debug(f"Successfully read and compiled .gitignore from {gitignore_path}")
            return spec
        except Exception as e:
            logger.warning(f"Error reading or parsing .gitignore file at {gitignore_path}: {e}", exc_info=True)
            return None

    @staticmethod
    def find_and_read_all(start_dir: Path) -> List[pathspec.PathSpec]:
        """
        Finds all .gitignore files from the start_dir up to the filesystem root
        and returns a list of PathSpec objects.
        start_dir からファイルシステムのルートまで、すべての .gitignore ファイルを検索し、
        PathSpec オブジェクトのリストを返します。

        Note:
            Git's behavior involves reading .gitignore from the current directory and all parent directories.
            The order might matter, but pathspec typically handles the combination.
            For simplicity here, we just collect all specs found.
            Git の動作では、現在のディレクトリとすべての親ディレクトリから .gitignore を読み取ります。
            順序が重要になる場合がありますが、pathspec は通常、組み合わせを処理します。
            ここでは簡単にするために、見つかったすべてのスペックを収集するだけです。

        Args:
            start_dir (Path): The directory to start searching upwards from.
                              上方向に検索を開始するディレクトリ。

        Returns:
            List[pathspec.PathSpec]: A list of PathSpec objects found.
                                     見つかった PathSpec オブジェクトのリスト。
        """
        specs = []
        current_dir = start_dir.resolve()
        while True:
            gitignore_file = current_dir / ".gitignore"
            spec = GitignoreReader.read(gitignore_file)
            if spec:
                specs.append(spec)

            if current_dir.parent == current_dir: # Reached the root
                break
            current_dir = current_dir.parent

        # The specs list is ordered from deepest to shallowest .gitignore
        # specs リストは、最も深い .gitignore から最も浅いものへと順序付けられています
        logger.debug(f"Found {len(specs)} .gitignore files starting from {start_dir}")
        return specs 