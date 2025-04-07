"""
Custom exceptions for the Kotemari library.
Kotemariライブラリ用のカスタム例外。
"""

class KotemariError(Exception):
    """Base class for all Kotemari specific errors.
    すべてのKotemari固有のエラーの基底クラス。
    """
    pass

class ConfigurationError(KotemariError):
    """Error related to configuration loading or validation.
    設定の読み込みまたは検証に関連するエラー。
    """
    pass

class FileSystemError(KotemariError):
    """Error related to file system operations (read, write, scan).
    ファイルシステム操作（読み取り、書き込み、スキャン）に関連するエラー。
    """
    pass

class ParsingError(KotemariError):
    """Error related to parsing files (e.g., Python AST, .gitignore).
    ファイル解析（例：Python AST、.gitignore）に関連するエラー。
    """
    pass

class AnalysisError(KotemariError):
    """Error occurring during the project analysis phase.
    プロジェクト解析フェーズ中に発生するエラー。
    """
    pass

class CacheError(KotemariError):
    """Error related to cache operations (read, write, validation).
    キャッシュ操作（読み取り、書き込み、検証）に関連するエラー。
    """
    pass

class ContextGenerationError(KotemariError):
    """Error occurring during the context generation phase.
    コンテキスト生成フェーズ中に発生するエラー。
    """
    pass

class DependencyError(KotemariError):
    """Error related to dependency analysis or retrieval.
    依存関係の分析または取得に関連するエラー。
    """
    pass

class FileNotFoundErrorInAnalysis(KotemariError):
    """Specific error when a target file is not found in the analyzed results.
    解析結果に対象ファイルが見つからない場合 स्पेसिफिक エラー。
    """
    pass 