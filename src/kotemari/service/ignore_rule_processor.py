from pathlib import Path
from typing import List, Callable
import pathspec
import logging

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
        return GitignoreReader.find_and_read_all(self.project_root)

    def get_ignore_function(self) -> Callable[[Path], bool]:
        """
        Returns a function that checks if a given absolute path should be ignored.
        The returned function considers .gitignore rules (and potentially config rules later).
        与えられた絶対パスが無視されるべきかどうかをチェックする関数を返します。
        返される関数は、.gitignore ルール（および将来的には設定ルール）を考慮します。

        Returns:
            Callable[[Path], bool]: A function that takes an absolute Path and returns True if it should be ignored.
                                     絶対パスを受け取り、無視すべき場合に True を返す関数。
        """
        def is_ignored(abs_path: Path) -> bool:
            """
            Checks if the path matches any ignore rule.
            パスがいずれかの無視ルールに一致するかどうかをチェックします。
            """
            if not abs_path.is_absolute():
                logger.warning(f"Received non-absolute path in ignore check: {abs_path}. Resolving relative to project root.")
                abs_path = self.path_resolver.resolve_absolute(abs_path, self.project_root)

            # pathspec expects paths relative to the directory containing the .gitignore file.
            # However, gitignore patterns often match against the path relative to the repository root.
            # We will match against the path relative to our project_root.
            # pathspec は .gitignore ファイルを含むディレクトリからの相対パスを期待します。
            # しかし、gitignore パターンはリポジトリルートからの相対パスに対して照合されることがよくあります。
            # ここでは、project_root からの相対パスに対して照合します。
            try:
                relative_path = abs_path.relative_to(self.project_root)
            except ValueError:
                # The path is outside the project root, typically should not happen during scan
                # パスがプロジェクトルートの外にあります。通常、スキャン中には発生しません。
                logger.warning(f"Path {abs_path} is outside the project root {self.project_root}. Not ignoring by default.")
                return False

            # Check against .gitignore specs
            # .gitignore スペックに対してチェックする
            # pathspec handles directory matching correctly (e.g., `dir/` matches the directory)
            # pathspec はディレクトリのマッチングを正しく処理します（例: `dir/` はディレクトリに一致）
            is_gitignored = any(spec.match_file(relative_path.as_posix()) for spec in self._gitignore_specs)
            if is_gitignored:
                logger.debug(f"Path ignored by .gitignore: {relative_path}")
                return True

            # TODO: Check against config ignore rules
            # TODO: 設定の無視ルールに対してチェックする

            return False

        return is_ignored 