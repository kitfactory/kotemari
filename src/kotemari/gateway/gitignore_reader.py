from pathlib import Path
from typing import List, Optional
import pathspec
import logging

logger = logging.getLogger(__name__)

class GitignoreReader:
    """
    Reads .gitignore files and creates a pathspec object for matching paths.
    .gitignore ファイルを読み込み、パスを照合するための pathspec オブジェクトを作成します。
    """

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