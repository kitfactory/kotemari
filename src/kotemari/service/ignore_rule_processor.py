from pathlib import Path
from typing import List, Callable
import pathspec
import logging
import os

from ..gateway.gitignore_reader import GitignoreReader
from ..domain.project_config import ProjectConfig # For future use
from ..utility.path_resolver import PathResolver

logger = logging.getLogger(__name__)

class IgnoreRuleProcessor:
    """
    Processes ignore rules from .gitignore files and potentially project configuration.
    Provides a function to check if a path should be ignored.
    .gitignore ファイルおよび（将来的には）プロジェクト設定からの無視ルールを処理します。
    パスが無視されるべきかどうかをチェックする関数を提供します。
    """

    def __init__(self, project_root: Path, config: ProjectConfig, path_resolver: PathResolver):
        """
        Initializes the IgnoreRuleProcessor.
        Loads .gitignore rules.
        IgnoreRuleProcessor を初期化します。
        .gitignore ルールを読み込みます。

        Args:
            project_root (Path): The root directory of the project.
                                 プロジェクトのルートディレクトリ。
            config (ProjectConfig): The project configuration (potentially containing ignore rules).
                                    プロジェクト設定（無視ルールを含む可能性がある）。
            path_resolver (PathResolver): An instance of PathResolver.
                                          PathResolver のインスタンス。
        """
        self.project_root = path_resolver.resolve_absolute(project_root)
        self.config = config
        self.path_resolver = path_resolver
        self._gitignore_specs: List[pathspec.PathSpec] = self._load_gitignore_specs()
        # TODO: Load ignore rules from self.config as well
        # TODO: self.config からも無視ルールを読み込む

        logger.info(f"IgnoreRuleProcessor initialized for project: {self.project_root}")
        logger.info(f"Loaded {len(self._gitignore_specs)} .gitignore spec(s).")

    def _load_gitignore_specs(self) -> List[pathspec.PathSpec]:
        """
        Loads PathSpec objects from all .gitignore files found in the project hierarchy.
        プロジェクト階層で見つかったすべての .gitignore ファイルから PathSpec オブジェクトを読み込みます。

        Returns:
            List[pathspec.PathSpec]: A list of loaded PathSpec objects.
                                     読み込まれた PathSpec オブジェクトのリスト。
        """
        # Search starts from the project root itself
        # 検索はプロジェクトルート自体から開始します
        specs = GitignoreReader.find_and_read_all(self.project_root)
        if not isinstance(specs, list) or not all(isinstance(s, pathspec.PathSpec) for s in specs):
            logger.warning(f"GitignoreReader.find_and_read_all did not return a list of PathSpec objects. Got: {type(specs)}")
            # Attempt to handle if it returned lines or a single spec incorrectly
            # 不正に 行または単一のスペックが返された場合に処理を試みます
            if isinstance(specs, pathspec.PathSpec):
                return [specs]
            # If it's something else, return empty list to avoid errors
            # 他の何かである場合は、エラーを回避するために空のリストを返します
            return []
        return specs

    def get_ignore_function(self) -> Callable[[str], bool]:
        """
        Returns a function that checks if a given path should be ignored based on all rules.
        すべてのルールに基づいて、指定されたパスを無視すべきかどうかをチェックする関数を返します。

        Returns:
            Callable[[str], bool]: A function that takes a path string and returns True if it should be ignored.
                                   パス文字列を受け取り、無視すべき場合に True を返す関数。
        """
        # Use the pre-compiled specs from __init__
        # __init__ から事前にコンパイルされたスペックを使用します
        compiled_specs = self._gitignore_specs
        project_root_str = str(self.project_root)

        if not compiled_specs:
            logger.debug("No ignore specs found or configured.")
            return lambda _: False # No specs means ignore nothing

        logger.debug(f"Using {len(compiled_specs)} compiled PathSpec object(s) for ignore checks.")

        # The function returned will perform the check using PathSpec
        # 返される関数は PathSpec を使用してチェックを実行します
        def should_ignore_path(path_str: str) -> bool:
            try:
                # Normalize the input path and ensure it's absolute
                # 入力パスを正規化し、絶対パスであることを確認します
                absolute_path = Path(path_str).resolve()

                # pathspec expects paths relative to the directory containing the .gitignore
                # (or in our case, relative to the project root).
                # pathspec は .gitignore を含むディレクトリからの相対パスを期待します
                # （または我々の場合は、プロジェクトルートからの相対パス）。
                relative_path_str = os.path.relpath(absolute_path, project_root_str)
                # Use forward slashes for pathspec matching consistency
                # pathspec マッチングの一貫性のためにスラッシュを使用します
                relative_path_posix = Path(relative_path_str).as_posix()

                # Check against all loaded PathSpec objects
                # ロードされたすべての PathSpec オブジェクトに対してチェックします
                for spec in compiled_specs:
                    if spec.match_file(relative_path_posix):
                        logger.debug(f"Path '{absolute_path}' (relative: '{relative_path_posix}') matched ignore spec.")
                        return True # Ignored if any spec matches

                logger.debug(f"Path '{absolute_path}' did not match any ignore specs.")
                return False # Not ignored if no specs match
            except ValueError:
                 # Path is likely outside the project root
                 # パスはおそらくプロジェクトルートの外にあります
                 logger.warning(f"Path '{path_str}' seems to be outside the project root '{project_root_str}'. Not ignoring.")
                 return False
            except Exception as e:
                 # Catch unexpected errors during path processing or matching
                 # パス処理またはマッチング中の予期しないエラーをキャッチします
                 logger.error(f"Error checking ignore status for path '{path_str}': {e}", exc_info=True)
                 return False # Default to not ignoring on error


        return should_ignore_path

    def should_ignore(self, file_path: Path) -> bool:
        """
        Checks if a given file path should be ignored.
        指定されたファイルパスを無視すべきかどうかをチェックします。

        Args:
            file_path (Path): The absolute path to the file to check.
                              チェックするファイルへの絶対パス。

        Returns:
            bool: True if the file should be ignored, False otherwise.
                  ファイルを無視すべき場合は True、そうでない場合は False。
        """
        # Resolve the path to ensure it's absolute and normalized
        # パスが絶対パスで正規化されていることを確認するために解決します
        absolute_path = file_path.resolve()
        # Get the ignore function and call it
        # 無視関数を取得して呼び出します
        ignore_func = self.get_ignore_function()
        # Pass the string representation of the absolute path
        # 絶対パスの文字列表現を渡します
        is_ignored = ignore_func(str(absolute_path))
        logger.debug(f"Ignore check for {absolute_path}: {'Ignored' if is_ignored else 'Not Ignored'}")
        return is_ignored

# Example usage (for testing or demonstration)
# 使用例 (テストまたはデモンストレーション用)
# ... existing code ... 