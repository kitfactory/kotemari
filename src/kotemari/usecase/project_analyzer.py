from pathlib import Path
from typing import List, Optional
import logging

from ..domain.file_info import FileInfo
# DependencyInfo は FileInfo 経由で利用されるため、直接インポートは必須ではない
# from ..domain.dependency_info import DependencyInfo
from ..domain.project_config import ProjectConfig
from ..gateway.file_system_accessor import FileSystemAccessor
from ..service.ignore_rule_processor import IgnoreRuleProcessor
from ..service.hash_calculator import HashCalculator
from ..service.language_detector import LanguageDetector
from ..service.ast_parser import AstParser # AstParser をインポート
from ..utility.path_resolver import PathResolver
from ..usecase.config_manager import ConfigManager
from ..domain.exceptions import AnalysisError, ParsingError, FileSystemError # カスタム例外をインポート

logger = logging.getLogger(__name__)

class ProjectAnalyzer:
    """
    Analyzes a software project by scanning its files, applying ignore rules,
    calculating hashes, detecting languages, and extracting dependencies (for supported languages like Python).
    ソフトウェアプロジェクトを分析します。ファイルをスキャンし、無視ルールを適用し、
    ハッシュを計算し、言語を検出し、依存関係を抽出します（Pythonなどのサポートされている言語の場合）。
    """

    def __init__(self,
                 project_root: Path | str,
                 path_resolver: Optional[PathResolver] = None,
                 config_manager: Optional[ConfigManager] = None,
                 fs_accessor: Optional[FileSystemAccessor] = None,
                 ignore_processor: Optional[IgnoreRuleProcessor] = None,
                 hash_calculator: Optional[HashCalculator] = None,
                 language_detector: Optional[LanguageDetector] = None,
                 ast_parser: Optional[AstParser] = None): # ast_parser を追加
        """
        Initializes the ProjectAnalyzer.
        Dependencies can be injected or created internally if not provided.
        ProjectAnalyzer を初期化します。
        依存関係は注入することも、提供されない場合は内部で作成することもできます。

        Args:
            project_root (Path | str): The root directory of the project.
                                       プロジェクトのルートディレクトリ。
            path_resolver (Optional[PathResolver]): PathResolver instance.
            config_manager (Optional[ConfigManager]): ConfigManager instance.
            fs_accessor (Optional[FileSystemAccessor]): FileSystemAccessor instance.
            ignore_processor (Optional[IgnoreRuleProcessor]): IgnoreRuleProcessor instance.
            hash_calculator (Optional[HashCalculator]): HashCalculator instance.
            language_detector (Optional[LanguageDetector]): LanguageDetector instance.
            ast_parser (Optional[AstParser]): AstParser instance for Python dependency analysis. # 説明を追加
                                                Python 依存関係分析用の AstParser インスタンス。
        """
        self.path_resolver = path_resolver or PathResolver()
        self.project_root = self.path_resolver.resolve_absolute(project_root)

        self.config_manager = config_manager or ConfigManager(self.path_resolver, self.project_root)
        self.config: ProjectConfig = self.config_manager.get_config()

        self.fs_accessor = fs_accessor or FileSystemAccessor(self.path_resolver)
        self.ignore_processor = ignore_processor or IgnoreRuleProcessor(self.project_root, self.config, self.path_resolver)
        self.hash_calculator = hash_calculator or HashCalculator()
        self.language_detector = language_detector or LanguageDetector()
        self.ast_parser = ast_parser or AstParser() # ast_parser を初期化

        logger.info(f"ProjectAnalyzer initialized for: {self.project_root}")

    def analyze(self) -> List[FileInfo]:
        """
        Performs the project analysis: scans files, filters ignored files,
        calculates hashes, detects languages, and extracts dependencies for Python files.
        プロジェクト分析を実行します: ファイルをスキャンし、無視されたファイルをフィルタリングし、
        ハッシュを計算し、言語を検出し、Python ファイルの依存関係を抽出します。

        Returns:
            List[FileInfo]: A list of FileInfo objects for the analyzed files.
                            分析されたファイルの FileInfo オブジェクトのリスト。
        """
        logger.info(f"Starting analysis of project: {self.project_root}")
        analyzed_files: List[FileInfo] = []
        ignore_func = self.ignore_processor.get_ignore_function()

        try:
            for file_info in self.fs_accessor.scan_directory(self.project_root, ignore_func=ignore_func):
                # --- ハッシュ計算 ---
                try:
                    file_hash = self.hash_calculator.calculate_file_hash(file_info.path)
                    file_info.hash = file_hash
                except Exception as e:
                    logger.warning(f"Could not calculate hash for {file_info.path}: {e}")
                    file_info.hash = None # Ensure hash is None on error

                # --- 言語検出 ---
                try:
                    language = self.language_detector.detect_language(file_info.path)
                    file_info.language = language
                    log_msg = f"Language for {file_info.path.name}: {language}" if language else f"Language not detected for: {file_info.path.name}"
                    logger.debug(log_msg)
                except Exception as e:
                    logger.warning(f"Could not detect language for {file_info.path}: {e}")
                    file_info.language = None # Ensure language is None on error


                # --- 依存関係抽出 (Python) ---
                if file_info.language == 'Python':
                    try:
                        content = self.fs_accessor.read_file(file_info.path)
                        if content is not None: # Check if file reading was successful
                             dependencies = self.ast_parser.parse_dependencies(content, file_info.path)
                             file_info.dependencies = dependencies
                             logger.debug(f"Found {len(dependencies)} dependencies in {file_info.path.name}")
                        else:
                             logger.warning(f"Could not read content of {file_info.path} to parse dependencies.")

                    except SyntaxError:
                        # AstParser already logs the detailed error
                        logger.warning(f"Skipping dependency parsing for {file_info.path.name} due to syntax errors.")
                        # dependencies will remain the default empty list
                    except Exception as e:
                        logger.error(f"Unexpected error parsing dependencies for {file_info.path}: {e}", exc_info=True)
                        # Optionally re-raise as AnalysisError or ParsingError?
                        # For now, log and continue, keeping dependencies empty.
                        # オプションで AnalysisError または ParsingError として再発生させますか？
                        # 今のところ、ログに記録して続行し、依存関係を空のままにします。
                        pass # Keep dependencies empty

                analyzed_files.append(file_info)
                logger.debug(f"Processed file: {file_info.path.relative_to(self.project_root)}")

        except FileNotFoundError as e:
            # This case should ideally be caught by fs_accessor.scan_directory raising FileSystemError
            # このケースは理想的には fs_accessor.scan_directory が FileSystemError を発生させることで捕捉されるべきです
            logger.error(f"Project root directory not found: {self.project_root}")
            # Re-raise as AnalysisError with a specific message
            # 特定のメッセージを持つ AnalysisError として再発生させます
            raise AnalysisError(f"Project root directory not found: {self.project_root}") from e
        except FileSystemError as e: # Catch errors from scan_directory (like dir not found)
            logger.error(f"OS error during file scanning in {self.project_root}: {e}", exc_info=True)
            # Re-raise as AnalysisError for the caller
            # 呼び出し元のために AnalysisError として再発生させます
            raise AnalysisError(f"Error scanning project directory: {e}") from e
        except Exception as e: # Catch other unexpected errors during the overall analysis
            logger.error(f"An unexpected error occurred during project analysis: {e}", exc_info=True)
            # Raise a general AnalysisError for unexpected issues
            # 予期しない問題に対して一般的な AnalysisError を発生させます
            raise AnalysisError(f"An unexpected error occurred during analysis: {e}") from e

        logger.info(f"Analysis complete. Found {len(analyzed_files)} non-ignored files.")
        return analyzed_files 