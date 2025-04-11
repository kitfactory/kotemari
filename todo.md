# 実装計画 (plan.md)

本ドキュメントは、「こてまり」ライブラリの実装に向けた開発計画を記述します。設計文書（要件定義書、アーキテクチャ設計書、機能仕様書）に基づき、段階的に実装を進めます。

## 1. 開発の進め方

*   **段階的実装:** 最小限のコア機能から始め、徐々に機能を追加・拡張していきます。
*   **テスト重視:** 各ステップでユニットテストを作成し、品質を確保します。`pytest` と `pytest-cov` を利用し、カバレッジを確認します。
*   **依存関係に基づく実装:** 基本的に、利用される側（末端）のクラス・機能から先に実装し、テストを行います。その後、それらを利用する上位のクラス・機能を実装します。
*   **バージョン管理:** Gitを使用します (`main`, `develop`, featureブランチ)。
*   **パッケージ管理:** 仮想環境 (`.venv`) 下で `uv` を使用します。
*   **ドキュメント連携:** 実装の進行に合わせて、関連ドキュメントを更新します。

## 2. 実装ステップ (チェックリスト)

以下に実装ステップの概要を示します。各ステップは独立したフィーチャーブランチで作業することを想定しています。完了したタスクにはチェックを入れてください (`- [x]`)。

### Step 0: プロジェクト準備

*   **ゴール:** 開発環境と基本的なプロジェクト構造を準備する。
*   **チェックリスト:**
    *   `[x]` Gitリポジトリの初期化 (`git init`)。
    *   `[x]` `.gitignore` ファイルの作成 (Python標準、`.venv/`, キャッシュディレクトリ、IDE設定ファイルなど)。
    *   `[x]` `pyproject.toml` の作成と基本設定 (pytest連携含む)。
    *   `[x]` 開発依存ライブラリのインストール (`uv add --dev pytest pytest-cov`)。
    *   `[x]` 基本的なディレクトリ構造 (`src/kotemari/`) と `src/kotemari/__init__.py` の作成。
    *   `[x]` `pyproject.toml` にプロジェクト基本情報（名前、バージョン、作者など）を追記。

### Step 1: ドメインモデルと基本ユーティリティ/ゲートウェイ

*   **ゴール:** システムの基礎となるデータ構造と、基本的なファイルアクセス、パス解決機能を実装する。
*   **チェックリスト:**
    *   `[x]` **Domain:** `ProjectConfig`, `FileInfo` (初期版: path, mtime, size), `ContextData` (初期版), `CacheMetadata`, `DependencyInfo` (初期版) データクラス実装 (`src/kotemari/domain/`)。
    *   `[x]` **Utility:** `PathResolver` (パス正規化、絶対パス変換) 実装 (`src/kotemari/utility/`)。
    *   `[x]` **Gateway:** `FileSystemAccessor` (ファイル読み込み、ディレクトリ走査) の基本部分実装 (`src/kotemari/gateway/`)。
    *   `[x]` Step 1 のユニットテスト作成と実行。

### Step 2: 設定管理と除外ルール

*   **ゴール:** 設定ファイル (`.kotemari.yml`) と `.gitignore` を読み込み、ファイル除外ルールを適用できるようにする。
*   **依存ライブラリ:** `pyyaml`
*   **チェックリスト:**
    *   `[x]` `uv add pyyaml` を実行。(実際には `pathspec` も追加)
    *   `[x]` **Gateway:** `GitignoreReader` (`.gitignore` 読み込み) 実装 (`src/kotemari/gateway/`)。
    *   `[x]` **UseCase:** `ConfigManager` (設定ファイル読み込み、`ProjectConfig` 生成) 実装 (`src/kotemari/usecase/`)。
    *   `[x]` **Service:** `IgnoreRuleProcessor` (除外ルール適用ロジック) 実装 (`src/kotemari/service/`)。
    *   `[x]` Step 2 のユニットテスト作成と実行。

### Step 3: 基本的なプロジェクト解析と情報収集

*   **ゴール:** プロジェクト内のファイル情報を収集し、除外ルールを適用してリスト化できるようにする。言語判定（簡易）とハッシュ計算も行う。
*   **チェックリスト:**
    *   `[x]` **Service:** ハッシュ計算機能実装 (`src/kotemari/service/hash_calculator.py` など)。
    *   `[x]` **Service:** 言語判定機能（拡張子ベース）実装 (`src/kotemari/service/language_detector.py` など)。
    *   `[x]` **UseCase:** `ProjectAnalyzer` (ファイル走査、`FileSystemAccessor`, `IgnoreRuleProcessor`, `ConfigManager`, 各Serviceを利用して `FileInfo` リスト生成) 実装 (`src/kotemari/usecase/`)。
    *   `[x]` Step 3 のユニットテスト作成と実行。

### Step 4: ファイル一覧・ツリー表示機能 (Kotemari ファサード導入)

*   **ゴール:** 解析結果を基に、ファイル一覧とツリー表示を提供できるようにする。ライブラリの窓口となる `Kotemari` ファサードを導入する。
*   **チェックリスト:**
    *   `[x]` **UseCase:** `Kotemari` ファサードクラス作成 (`src/kotemari/core.py` or `src/kotemari/__init__.py`)。
    *   `[x]` `Kotemari` に `__init__` メソッド実装 (プロジェクトルート、設定パスを受け取る)。
    *   `[x]` `Kotemari` に `analyze_project` メソッド実装 (`ProjectAnalyzer` 呼び出し)。
    *   `[x]` `Kotemari` に `list_files` メソッド実装 (`analyze_project` 結果を利用)。
    *   `[x]` `Kotemari` に `get_tree` メソッド実装 (`analyze_project` 結果を利用)。
    *   `[x]` Step 4 のユニットテスト作成と実行 (`Kotemari` クラス経由でのテスト)。

### Step 5: キャッシュ機能

*   **ゴール:** プロジェクト解析結果 (`List[FileInfo]`) をキャッシュし、再利用できるようにする。
*   **チェックリスト:**
    *   `[x]` **Gateway:** `CacheStorage` (ファイルベースのキャッシュ保存/読み込み) 実装 (`src/kotemari/gateway/`)。
    *   `[x]` **UseCase:** `CacheUpdater` (キャッシュの有効性チェック、更新処理) 実装 (`src/kotemari/usecase/`)。
    *   `[x]` `Kotemari` ファサード (`analyze_project` など) にキャッシュ利用オプションと `CacheUpdater` 連携を実装。
    *   `[x]` `Kotemari` ファサードに `clear_cache` メソッド実装。
    *   `[x]` Step 5 のユニットテスト作成と実行 (キャッシュ有無、有効期限など)。

### Step 6: ファイル変更監視機能の実装とテスト

*   **ゴール:** `watchdog` を利用してファイルシステムの変更をリアルタイムで検知し、関連するキャッシュを自動的に無効化できるようにする。
*   **依存ライブラリ:** `watchdog`
*   **チェックリスト:**
    *   `[x]` `uv add watchdog` を実行。
    *   `[x]` **Domain:** `FileSystemEvent` データクラス実装 (`src/kotemari/domain/`)。
    *   `[x]` **Service:** `FileSystemEventMonitor` 実装 (`watchdog` 利用、`IgnoreRuleProcessor` 連携、イベント通知) (`src/kotemari/service/`)。
    *   `[x]` **UseCase:** `CacheUpdater` 修正 (`invalidate_cache_on_event` メソッド実装、イベントに基づきキャッシュ無効化)。
    *   `[x]` `Kotemari` ファサードに `start_watching`, `stop_watching` メソッド実装 (`FileSystemEventMonitor` の制御)。
    *   `[x]` Step 6 のユニットテスト作成と実行 (イベント検知、無視ルールの適用、キャッシュ無効化、コールバック呼び出しなど)。
    *   `[x]` アーキテクチャ設計書 (architecture.md) の更新 (テスト完了)。

### Step 7: 構文解析と依存関係抽出 (Python) (旧Step 6)

*   **ゴール:** Pythonファイルの `import` 文を解析し、依存関係情報を抽出できるようにする。
*   **チェックリスト:**
    *   `[x]` **Service:** `AstParser` (Python `ast` モジュール利用) 実装 (`src/kotemari/service/`)。
    *   `[x]` **Domain:** `FileInfo` に `dependencies: List[DependencyInfo]` 属性を追加し、DependencyInfo の詳細（内部/外部の区別など）を拡充する。
    *   `[x]` **UseCase:** `ProjectAnalyzer` を修正し、Pythonファイルに対して `AstParser` を呼び出し、`FileInfo` に依存情報を格納する。
    *   `[x]` `Kotemari` ファサードに `get_dependencies` メソッド実装 (`analyze_project` 結果から依存情報を返す)。
    *   `[x]` Step 7 のユニットテスト作成と実行 (import文を持つファイルの依存関係抽出テスト)。

### Step 8: コンテキスト生成機能 (旧Step 7)

*   **ゴール:** 指定されたファイルとその依存関係（オプション）から、LLM に入力するためのコンテキスト文字列を生成する機能。
*   **チェックリスト:**
    *   `[x]` **Domain:** `ContextData` (コンテキストの種類、関連ファイルパスリスト、生成されたコンテキスト文字列) データクラス定義 (`src/kotemari/domain/`)。
    *   `[x]` **Domain:** `FileContentFormatter` (ファイルパスと内容を結合するフォーマッタ) インターフェース定義と基本的な実装 (`src/kotemari/domain/`)。
    *   `[x]` **UseCase:** `ContextBuilder` (関連ファイル選択ロジック、内容結合、`FileContentFormatter` 利用) 実装 (`src/kotemari/usecase/`)。
    *   `[x]` `Kotemari` ファサードに `get_context` メソッド実装 (`analyze_project`, `get_dependencies`, `ContextBuilder`, `CacheUpdater` 連携)。
    *   `[x]` 8. Unit Test: Create and pass unit tests for the `ContextBuilder` and `Kotemari.get_context` functionality.

### Step 9: CLIインターフェース (旧Step 8)

*   **ゴール:** コマンドラインから主要機能 (`analyze`, `list`, `tree`, `context`, `dependencies`) を利用できるようにする。
*   **依存ライブラリ:** `typer`
*   **チェックリスト:**
    *   `[x]` `uv add typer[all]` を実行。
    *   `[x]` **Gateway:** `CliParser` (typer を利用) 実装 (`src/kotemari/gateway/`) - analyze, dependencies, context, watch コマンドとオプション定義。
    *   `[x]` **Controller:** `CliController` 実装 (`src/kotemari/controller/`) - `CliParser` からの入力を受け取り、`Kotemari` ファサードのメソッド呼び出し、結果を整形して表示 (rich を利用)。
    *   `[x]` `pyproject.toml` にエントリポイント (`[project.scripts]`) を設定し、`kotemari` コマンドを実行可能にする。
    *   `[x]` Integration Test: CLIコマンド (`analyze`, `dependencies`, `context`) の基本的な動作を確認するテスト (pytest を使用し、subprocess で CLI を実行)。 (注: `dependencies` は既知の問題により xfail)

### Step 10: 仕上げ (旧Step 11)

*   **ゴール:** ライブラリとしての完成度を高め、リリース可能な状態にする。
*   **チェックリスト:**
    *   `[x]` エラーハンドリングの見直しとカスタム例外 (`KotemariError` など) の定義・適用。
    *   `[x]` ドキュメント整備 (`README.md`, `README_ja.md` 更新、利用ガイド、APIリファレンスなど)。
    *   `[x]` パッケージング設定 (`pyproject.toml`) の最終確認。
    *   `[ ]` リリース準備 (バージョン設定、changelogなど)。

### Step 11: 応答性向上のためのキャッシュアーキテクチャ改修 (メモリキャッシュ＋差分更新)

エディタ連携など、ライブラリとしての応答性を向上させるため、ファイルキャッシュ中心からメモリキャッシュ＋バックグラウンド差分更新アーキテクチャへ移行する。

- [x] 11-1: **基盤構築フェーズ**
    - [x] 11-1-1: 既存のファイルキャッシュ関連クラス (`CacheStorage`, `CacheUpdater`, `CacheMetadata`) の削除または大幅な役割変更・リファクタリング。
    - [x] 11-1-2: `Kotemari` クラス内でのメモリキャッシュ (`_analysis_results`) 管理機構の整備。
    - [x] 11-1-3: スレッドセーフなメモリキャッシュアクセスを実現するためのロック機構 (`threading.Lock` など) の導入。
    - [x] 11-1-4: `watchdog` を利用したファイルシステム変更監視の開始/停止機能 (`start_watching`, `stop_watching`) の実装。
    - [x] 11-1-5: 変更イベント（ファイルパス、イベント種別）を処理するためのキュー (`queue.Queue`) の導入。
    - [x] 11-1-6: キューを処理するバックグラウンドスレッド/プロセスの実装。初期段階では、変更検知時に**プロジェクト全体の再分析**を行い、メモリキャッシュをアトミックに更新する。
    - [x] 11-1-7: メモリキャッシュの内容をファイルに永続化/復元する機能の実装（起動時のロード、定期的/終了時のセーブ）。これにより初回起動時の分析時間を短縮する。
    - [x] 11-1-8: 基盤部分に関するテストコードの作成/修正。
- [x] 11-2: **差分更新ロジック実装フェーズ**
    - [x] 11-2-1: ファイル作成/削除イベントに対応するメモリキャッシュ更新ロジックの実装（全体の再計算ではなく、該当情報の追加/削除）。
    - [x] 11-2-2: ファイル変更イベントに対応する**差分分析**ロジックの設計・実装。変更されたファイルのみを再分析（ハッシュ計算、AST解析など）し、メモリキャッシュ内の該当 `FileInfo` を更新する。
    - [x] 11-2-3: バックグラウンド処理を、全体再分析から上記 11-2-1 〜 11-2-2 の差分更新ロジックに置き換える。(Implicitly done by 11-2-1, 11-2-2)
    - [x] 11-2-4: 差分更新の正確性、パフォーマンス、競合状態などに関するテストを拡充する。

### Step 12: 差分更新における依存関係の波及処理 (詳細化)

*   **ゴール:** ファイル変更時に、そのファイルに依存している他のファイルの情報を自動的に更新できるようにする（依存関係の波及）。
*   **実装方針:** 逆依存インデックス (`_reverse_dependency_index`) を利用して、変更の影響範囲を特定し、関連するファイルの情報を更新する。
*   **詳細チェックリスト:**
    *   `[x]` **12-1: 逆依存インデックスの属性定義:**
        *   `[x]` 12-1-1: `Kotemari` クラスまたは適切な内部クラスに、逆依存関係を保持する辞書属性 (`_reverse_dependency_index: Dict[Path, Set[Path]]`) を定義する。（キー: 依存されるファイルパス, 値: 依存しているファイルパスのセット）
        *   `[x]` 12-1-2: 逆依存インデックスへのアクセスを保護するための専用の `threading.Lock` を追加する。
    *   `[x]` **12-2: 逆依存インデックス構築ロジックの実装:**
        *   `[x]` 12-2-1: プロジェクト全体の分析 (`_analyze_project_internal`) の中で、分析結果 (`_analysis_results`) を走査し、各ファイルの依存関係情報 (`FileInfo.dependencies`) を基に `_reverse_dependency_index` を構築する `_build_reverse_dependency_index` メソッドを実装する。
        *   `[x]` 12-2-2: `_analyze_project_internal` の最後に `_build_reverse_dependency_index` を呼び出すようにする。
        *   `[x]` 12-2-3: `_build_reverse_dependency_index` の実装において、適切なロックを取得・解放するようにする。
    *   `[x]` **12-3: 差分更新時の逆依存インデックス更新ロジックの実装:**
        *   `[x]` 12-3-1: ファイル変更 (`modified`) 時に、ファイルの `FileInfo` が更新された後、古い依存関係と新しい依存関係に基づいて `_reverse_dependency_index` を更新するロジックを実装する (`_update_reverse_dependency_index` のようなヘルパーメソッドを検討)。 (Implemented via remove/add)
        *   `[x]` 12-3-2: ファイル作成 (`created`) 時に、新しい `FileInfo` の依存関係に基づいて `_reverse_dependency_index` を更新するロジックを実装する。
        *   `[x]` 12-3-3: ファイル削除 (`deleted`) 時に、関連するエントリを `_reverse_dependency_index` から削除するロジックを実装する。
        *   `[x]` 12-3-4: 上記の更新ロジックが `_process_event` 内の適切な箇所から、ロックを考慮して呼び出されるようにする。
    *   `[x]` **12-4: 依存関係波及処理の実装:**
        *   `[x]` 12-4-1: ファイル変更 (`modified`) イベントを処理する際、`_reverse_dependency_index` を参照して、変更されたファイルに依存しているファイル（影響を受けるファイル）のリストを取得する。
        *   `[x]` 12-4-2: 影響を受ける各ファイルについて、依存関係情報が古くなったことを示すフラグを立てるか、依存関係リストをクリアするなどして、再計算が必要であることを示す処理を実装する。（まずは `FileInfo` に `dependencies_stale: bool` のようなフラグを追加することを検討）(Flag implemented)
        *   `[ ]` 12-4-3: `get_dependencies` や `get_context` など、依存関係情報を利用するメソッド側で、`dependencies_stale` フラグが立っている場合は、依存関係の再計算を行うように修正する。（または、`_process_event` 内で直接再計算を行う）(Deferred)
    *   `[x]` **12-5: テストの作成と実行:**
        *   `[x]` 12-5-1: 逆依存インデックスの構築・更新ロジックに対するユニットテストを作成する。
        *   `[x]` 12-5-2: ファイル変更 → 依存関係の波及 → 影響を受けるファイルの `FileInfo` 更新（またはフラグ設定）という一連の流れを確認する結合テストを作成する。
        *   `[x]` 12-5-3: 循環依存など、複雑な依存関係シナリオでのテストを追加する。

### Step 13: テストカバレッジの向上

*   **ゴール:** テストカバレッジを向上させ、特にカバレッジの低いモジュール（`core.py`, `project_analyzer.py`, `file_system_accessor.py`, `gitignore_reader.py` など）の信頼性を高める。目標カバレッジを 85% 以上とする。
*   **アプローチ:**
    *   `pytest --cov` のレポートを確認し、カバレッジが低いファイルと行を特定する。
    *   未テストのブランチ、エラーハンドリング、エッジケースを中心にテストを追加する。
    *   必要に応じて既存のテストをリファクタリングし、より多くのコードパスをカバーできるようにする。
    *   特に `Kotemari` (`core.py`) のバックグラウンド処理やイベントハンドリング、`ProjectAnalyzer` のファイル処理ロジック、ゲートウェイ層のファイルI/Oや外部プロセス連携部分のテストを強化する。
*   **チェックリスト:**
    *   `[x]` **13-1:** `pytest --cov` を実行し、最新のカバレッジレポートを生成・確認する。
    *   `[x]` **13-2:** カバレッジが低い主要モジュール (`core.py`, `project_analyzer.py`, `file_system_accessor.py`, `gitignore_reader.py`) のテストケースを追加・修正する。
        *   `[x]` `core.py`: イベント処理 (`_process_event`) の各分岐、ロック機構、エラーハンドリング。
        *   `[x]` `project_analyzer.py`: `analyze` および `analyze_single_file` 内の各ステップ（ハッシュ、言語検出、依存関係解析）のエラーケース、無視ルールの適用漏れがないか。
        *   `[x]` `file_system_accessor.py`: ファイル/ディレクトリが存在しない場合、アクセス権がない場合などのエラーハンドリング。
        *   `[x]` `gitignore_reader.py`: 複雑な `.gitignore` パターン、複数 `.gitignore` ファイルのテスト。
    *   `[x]` **13-3:** 追加/修正したテストを実行し、すべてパスすることを確認する。
    *   `[x]` **13-4:** 再度 `pytest --cov` を実行し、カバレッジが目標値（85%）以上に向上したことを確認する。

### Step 14: ログ出力の整理と Verbose モード対応

*   **ゴール:** 不要なprint文を削除し、KotemariライブラリとCLIの両方でログレベルを適切に制御できるようにする。
*   **チェックリスト:**
    *   `[x]` **14-1: 不要な `print` 文の削除:**
        *   `[x]` プロジェクト全体のコード (`src/`, `tests/`) を確認し、デバッグ目的などで追加された不要な `print` 文を削除するか、適切な `logger.debug` 等に置き換える。
    *   `[x]` **14-2: `Kotemari` クラスのログレベル制御:**
        *   `[x]` `Kotemari.__init__` に `log_level` 引数があることを確認し、その役割を明確化する（ライブラリ内部のログ出力レベルを制御する）。
        *   `[x]` `Kotemari` クラス内部で使用するロガー (`logging.getLogger('kotemari')` など）を作成し、`__init__` で渡された `log_level` に基づいてレベルを設定するヘルパーメソッド (`_setup_logging` など) を実装または修正する。
        *   `[x]` `__init__` 内で `_setup_logging` を呼び出す。
        *   `[x]` デフォルト（例: `logging.WARNING` 以上）では `kotemari` ロガーのログがコンソール等に出力されないように、ハンドラ（例: `logging.NullHandler`）を設定する、またはレベルを適切に設定する。
    *   `[x]` **14-3: CLI の `--verbose` オプション対応:**
        *   `[x]` `gateway/cli_parser.py` の `main_callback` で `-v`/`-vv` オプションを処理し、対応するログレベル (`logging.INFO`, `logging.DEBUG`) を決定するロジックを確認・修正する (`_verbosity_callback` を利用)。
        *   `[x]` `controller/cli_controller.py` の `_get_kotemari_instance` メソッドで、`ctx.meta` からログレベルを取得し、`Kotemari` インスタンス化時に `log_level` 引数として渡すように修正する。
        *   `[x]` `controller/cli_controller.py` の `_setup_logging` メソッドが、`main_callback` で設定されたグローバルなロガー設定と競合しないか確認し、必要に応じて `kotemari` ロガーのみを設定するように修正する。
    *   `[x]` **14-4: テストの追加/修正:**
        *   `[x]` `Kotemari` クラスのログレベル設定に関するユニットテストを追加する。
        *   `[x]` `tests/integration/test_cli_integration.py` を修正し、`CliRunner` を用いて `-v`/`-vv` オプションを渡し、`stderr` に期待されるログ（INFO, DEBUGレベル）が出力されること、およびデフォルトでは出力されないことを検証するテストを追加・修正する。
    *   `[x]` **14-5: 計画粒度の確認:** Step 14 の各チェック項目が明確な指示になっており、実行可能であることを確認する。

## 3. 注意事項

*   各ステップの粒度は目安であり、状況に応じて調整可能です。
*   複雑な機能（`ContextBuilder` の関連ファイル選択ロジックなど）は、初期はシンプルな実装とし、後で改良することも検討します。
*   エラーハンドリングは各ステップで例外 (`Exception`, `KotemariError`) を用いて適切に実装します。 