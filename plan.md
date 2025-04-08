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

- [ ] 11-1: **基盤構築フェーズ**
    - [x] 11-1-1: 既存のファイルキャッシュ関連クラス (`CacheStorage`, `CacheUpdater`, `CacheMetadata`) の削除または大幅な役割変更・リファクタリング。
    - [x] 11-1-2: `Kotemari` クラス内でのメモリキャッシュ (`_analysis_results`) 管理機構の整備。
    - [x] 11-1-3: スレッドセーフなメモリキャッシュアクセスを実現するためのロック機構 (`threading.Lock` など) の導入。
    - [x] 11-1-4: `watchdog` を利用したファイルシステム変更監視の開始/停止機能 (`start_watching`, `stop_watching`) の実装。
    - [x] 11-1-5: 変更イベント（ファイルパス、イベント種別）を処理するためのキュー (`queue.Queue`) の導入。
    - [x] 11-1-6: キューを処理するバックグラウンドスレッド/プロセスの実装。初期段階では、変更検知時に**プロジェクト全体の再分析**を行い、メモリキャッシュをアトミックに更新する。
    - [ ] 11-1-7: メモリキャッシュの内容をファイルに永続化/復元する機能の実装（起動時のロード、定期的/終了時のセーブ）。これにより初回起動時の分析時間を短縮する。
    - [x] 11-1-8: 基盤部分に関するテストコードの作成/修正。
- [ ] 11-2: **差分更新ロジック実装フェーズ**
    - [ ] 11-2-1: ファイル作成/削除イベントに対応するメモリキャッシュ更新ロジックの実装（全体の再計算ではなく、該当情報の追加/削除）。
    - [ ] 11-2-2: ファイル変更イベントに対応する**差分分析**ロジックの設計・実装。変更されたファイルのみを再分析（ハッシュ計算、AST解析など）し、メモリキャッシュ内の該当 `FileInfo` を更新する。
    - [ ] 11-2-3: **依存関係の波及**を考慮した更新ロジックの設計・実装（高難易度）。ファイルAの変更がファイルBの依存関係情報 (`FileInfo.dependencies`) に影響する場合、ファイルBのキャッシュ情報も更新する。
    - [ ] 11-2-4: バックグラウンド処理を、全体再分析から上記 11-2-1 〜 11-2-3 の差分更新ロジックに置き換える。
    - [ ] 11-2-5: 差分更新の正確性、パフォーマンス、競合状態などに関するテストを拡充する。

## 3. 注意事項

*   各ステップの粒度は目安であり、状況に応じて調整可能です。
*   複雑な機能（`ContextBuilder` の関連ファイル選択ロジックなど）は、初期はシンプルな実装とし、後で改良することも検討します。
*   エラーハンドリングは各ステップで例外 (`Exception`, `KotemariError`) を用いて適切に実装します。 