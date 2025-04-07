from pathlib import Path
from typing import List, Dict, Optional

from kotemari.domain.context_data import ContextData
from kotemari.domain.file_content_formatter import FileContentFormatter, BasicFileContentFormatter
from kotemari.gateway.file_system_accessor import FileSystemAccessor
# TODO: Import Kotemari core or relevant parts if needed for dependency lookup
# from kotemari.core import Kotemari # Or specific cache/dependency access mechanism

class ContextBuilder:
    """
    Use case class responsible for building context from specified files.
    指定されたファイルからコンテキストを構築する責務を持つユースケースクラス。

    It retrieves file contents, potentially identifies related files based on dependencies (future enhancement),
    and formats the combined content.
    ファイルの内容を取得し、依存関係に基づいて関連ファイルを特定（将来的な拡張）し、
    結合された内容をフォーマットします。

    Attributes:
        file_accessor: An instance for accessing the file system.
                       ファイルシステムにアクセスするためのインスタンス。
        formatter: An instance for formatting the combined file content.
                   結合されたファイル内容をフォーマットするためのインスタンス。
        # kotemari_core: Optional[Kotemari] = None # To access dependencies/cache
    """

    def __init__(
        self,
        file_accessor: Optional[FileSystemAccessor] = None,
        formatter: Optional[FileContentFormatter] = None,
        # kotemari_core: Optional[Kotemari] = None # Inject if needed
    ):
        # English: Use default implementations if none are provided.
        # 日本語: 提供されない場合はデフォルトの実装を使用します。
        self.file_accessor = file_accessor or FileSystemAccessor()
        self.formatter = formatter or BasicFileContentFormatter()
        # self.kotemari_core = kotemari_core

    def build_context(self, target_files: List[Path], project_root: Path) -> ContextData:
        """
        Builds the context string from the content of the target files.
        ターゲットファイルの内容からコンテキスト文字列を構築します。

        Currently, it only includes the content of the explicitly provided target files.
        Future versions might include related files based on dependencies.
        現在は、明示的に提供されたターゲットファイルの内容のみを含みます。
        将来のバージョンでは、依存関係に基づいて関連ファイルが含まれる可能性があります。

        Args:
            target_files: A list of absolute paths to the target files.
                          ターゲットファイルへの絶対パスのリスト。
            project_root: The absolute path to the project root directory.
                          プロジェクトルートディレクトリへの絶対パス。

        Returns:
            A ContextData object containing the formatted context string and related info.
            フォーマットされたコンテキスト文字列と関連情報を含むContextDataオブジェクト。

        Raises:
            FileNotFoundError: If any of the target files do not exist.
                               ターゲットファイルのいずれかが存在しない場合。
            IOError: If there is an error reading any of the files.
                     ファイルの読み取り中にエラーが発生した場合。
        """
        # English: Validate that all target files exist first.
        # 日本語: まず、すべてのターゲットファイルが存在することを確認します。
        for file_path in target_files:
            if not self.file_accessor.exists(str(file_path)):
                raise FileNotFoundError(f"Target file not found: {file_path}")

        # TODO: Implement logic to find related files based on dependencies using self.kotemari_core
        #       依存関係に基づいて関連ファイルを見つけるロジックを self.kotemari_core を使用して実装します
        all_files_to_include = set(target_files)
        related_found: List[Path] = []

        # English: Read content for all files to include.
        # 日本語: 含めるすべてのファイルのコンテンツを読み取ります。
        file_contents: Dict[Path, str] = {}
        try:
            for file_path in sorted(list(all_files_to_include)): # Sort for consistent read order
                # English: Pass project_root to read_file for potential relative path resolution within accessor
                # 日本語: アクセサ内での潜在的な相対パス解決のために project_root を read_file に渡します
                # Corrected call: project_root is not needed here as PathResolver handles it.
                # 修正後の呼び出し: PathResolver が処理するため、ここでは project_root は不要です。
                file_contents[file_path] = self.file_accessor.read_file(str(file_path))
        except FileNotFoundError as e:
            # English: File existence is checked before this loop, but handle just in case.
            # 日本語: ファイルの存在はこのループの前にチェックされますが、念のため処理します。
            logger.error(f"Error reading file, should have existed: {e}")
        except (IOError) as e:
            # English: Re-raise IOErrors during reading phase.
            # 日本語: 読み取りフェーズ中のIOErrorを再発生させます。
            # Consider more specific error handling or logging here.
            # ここでより具体的なエラー処理またはロギングを検討します。
            raise IOError(f"Error reading file content: {e}") from e


        # English: Format the collected content.
        # 日本語: 収集したコンテンツをフォーマットします。
        # Refine formatter call if relative paths are needed for headers
        # ヘッダーに相対パスが必要な場合は、フォーマッター呼び出しを調整します
        context_string = self.formatter.format_content(file_contents)

        # English: Create the ContextData object.
        # 日本語: ContextDataオブジェクトを作成します。
        return ContextData(
            target_files=target_files, # Original targets
            context_string=context_string,
            related_files=related_found if related_found else None, # Files added beyond targets
            context_type="basic_concatenation" # Example type
        ) 