# Kotemari 🪄

[![PyPI version](https://img.shields.io/pypi/v/kotemari.svg?style=flat-square)](https://pypi.python.org/pypi/kotemari)
[![Build Status](https://img.shields.io/github/actions/workflow/status/<YOUR_GITHUB_USERNAME>/kotemari/ci.yml?branch=main&style=flat-square)](https://github.com/<YOUR_GITHUB_USERNAME>/kotemari/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/<YOUR_GITHUB_USERNAME>/kotemari?style=flat-square)](https://codecov.io/gh/<YOUR_GITHUB_USERNAME>/kotemari)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

Kotemari (こてまり) は、Python プロジェクトの構造を分析し、依存関係を理解し、GPT のような大規模言語モデル (LLM) 向けのコンテキストをインテリジェントに生成するための Python ライブラリです。🧠 その主な目的は、他の開発ツール（IDE 拡張機能、分析スクリプト、チャットインターフェースなど）に統合され、オンデマンドでプロジェクトの洞察とコンテキストを提供することです。また、リアルタイムのファイル監視機能も備えており、分析を簡単に最新の状態に保つことができます！ ✨

## 🤔 Kotemari を使う理由

プロジェクト理解機能をツールに統合したり、LLM 向けのコンテキスト生成を自動化したりするのは複雑になることがあります。Kotemari は、堅牢な Python API を提供することでこれを簡素化します:

*   **🎯 スマートなコンテキストを提供:** シンプルな API 呼び出しを通じて、必要なファイルとその依存関係のみを含む簡潔なコンテキスト文字列を生成します。
*   **🔄 最新の状態を維持:** バックグラウンドでのファイル監視と自動的なキャッシュ/依存関係の更新を提供し、API が提供する情報が最新であることを保証します。
*   **🔍 詳細な洞察を提供:** Python の `import` 文の分析から得られる詳細な依存関係情報（直接および逆方向）にアクセスするメソッドを公開します。
*   **⚙️ 柔軟性を提供:** Python の引数またはオプションの `.kotemari.yml` ファイルを通じて簡単に設定可能で、`.gitignore` ルールを尊重します。
*   **🧩 統合を可能に:** カスタムの Python アプリケーションや開発ワークフローに簡単に組み込めるように設計されています。

Kotemari は、**シンプルで効果的な Python API** を通じて、洗練されたプロジェクト分析機能を提供することで、あなたのツールを強化します。🎉

## 🚀 インストール

Kotemari は現在開発中です。開発版をインストールするには:

1.  **リポジトリをクローン:**
    ```bash
    git clone https://github.com/<YOUR_GITHUB_USERNAME>/kotemari.git
    cd kotemari
    ```
2.  **仮想環境を作成:**
    ```bash
    # venv を使用する場合
    python -m venv .venv
    source .venv/bin/activate # Windows の場合は `.venv\Scripts\activate` を使用

    # または uv (推奨)
    uv venv
    source .venv/bin/activate # Windows の場合は `.venv\Scripts\activate` を使用
    ```
3.  **編集可能モードでパッケージをインストール:**
    ```bash
    # pip を使用する場合
    pip install -e .[dev]

    # または uv を使用する場合
    uv pip install -e .[dev]
    ```

*(リリースされると、インストールは `pip install kotemari` のように簡単になります)*

## ✨ 使い方 (Python API)

Python コードで Kotemari を使用するのは簡単です:

```python
import logging
from pathlib import Path
from kotemari import Kotemari

# オプション: Kotemari の内部動作を確認するためにロギングを設定
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')

# 1. プロジェクトのルートディレクトリで Kotemari を初期化
project_path = Path("./your/project/path") # <-- ここを変更してください！
kotemari = Kotemari(project_path)

# 2. プロジェクトを分析（初期キャッシュと依存関係グラフを構築）
print("プロジェクトを分析中...")
kotemari.analyze_project()
print("分析完了！")

# 3. 分析されたファイルのリストを取得 (FileInfo オブジェクト)
print("\n分析されたファイル:")
all_files = kotemari.list_files()
for file_info in all_files[:5]: # 簡潔にするために最初の5つを表示
    print(f"- {file_info.path.relative_to(project_path)} (ハッシュ: {file_info.hash[:7]}...)")

# 4. 特定のファイルの依存関係を取得
target_file = project_path / "src/module_a.py" # 例
print(f"\n{target_file.name} の依存関係:")
try:
    dependencies = kotemari.get_dependencies(target_file)
    if dependencies:
        for dep_path in dependencies:
            print(f"- {dep_path.relative_to(project_path)}")
    else:
        print("- 直接的な依存関係は見つかりませんでした。")
except FileNotFoundError:
    print(f"- ファイル {target_file.name} は分析結果に見つかりませんでした。")

# 5. 特定のファイルに依存するファイルを取得（逆依存関係）
dependent_on_file = project_path / "src/utils.py" # 例
print(f"\n{dependent_on_file.name} に依存するファイル:")
try:
    reverse_deps = kotemari.get_reverse_dependencies(dependent_on_file)
    if reverse_deps:
        for rev_dep_path in reverse_deps:
            print(f"- {rev_dep_path.relative_to(project_path)}")
    else:
        print("- このファイルに直接依存するファイルはありません。")
except FileNotFoundError:
    print(f"- ファイル {dependent_on_file.name} は分析結果に見つかりませんでした。")

# 6. LLM 向けの整形済みコンテキストを生成（対象ファイル + 依存関係）
context_file = project_path / "src/main_logic.py" # 例
print(f"\n{context_file.name} のコンテキストを生成中:")
try:
    context_string = kotemari.get_context(context_file)
    print("--- コンテキスト開始 ---")
    print(context_string[:500] + "... (切り詰め)") # 簡潔にするために開始部分を表示
    print("--- コンテキスト終了 ---")
except FileNotFoundError:
    print(f"- ファイル {context_file.name} が見つかりませんでした。")
except Exception as e:
    print(f"エラーが発生しました: {e}")

# 7. オプション: リアルタイム更新のためのバックグラウンドファイル監視を開始
# ファイルが変更されると、Kotemari は自動的に内部状態を更新します。
print("\nファイルウォッチャーを開始します（バックグラウンドで実行）...")
kotemari.start_watching()

# --- ここにあなたのアプリケーションロジック --- 
# これで kotemari のメソッド（list_files, get_dependencies など）を呼び出して、
# ファイルの変更を反映した最新の結果を取得できます。

print("ウォッチャーが実行中です。プロジェクトファイルを変更して更新を確認してください（INFO が有効な場合はログを確認）。")
input("監視を停止して終了するには Enter キーを押してください...\n")

print("ウォッチャーを停止中...")
kotemari.stop_watching()
print("ウォッチャーが停止しました。")
```

### 主要な API メソッド:

*   **`Kotemari(project_root, config_path=None, use_cache=True, log_level=logging.WARNING)`:** アナライザを初期化します。
*   **`analyze_project()`:** 初回の完全な分析を実行します。
*   **`list_files()`:** 追跡されているすべてのファイルの `List[FileInfo]` を返します。
*   **`get_dependencies(file_path: Path)`:** 対象ファイルがインポートするファイルの `Set[Path]` を返します。
*   **`get_reverse_dependencies(file_path: Path)`:** 対象ファイルをインポートするファイルの `Set[Path]` を返します。
*   **`get_context(file_path: Path, include_dependencies=True, formatter=...)`:** コンテキスト文字列を生成します。
*   **`start_watching()` / `stop_watching()`:** バックグラウンドファイルモニターを制御します。
*   **`clear_cache()`:** キャッシュされた分析結果を削除します。

## 🛠️ CLI の使用法（オプション）

Kotemari は、簡単な確認や単純なタスクのための基本的なコマンドラインインターフェースも提供します:

```bash
# 環境を有効化
source .venv/bin/activate # または .venv\Scripts\activate

# 基本コマンド
kotemari analyze
kotemari list
kotemari tree
kotemari dependencies <path/to/file.py>
kotemari context <path/to/file1.py> [<path/to/file2.py>...]

# ヘルプを表示
kotemari --help
kotemari analyze --help
```

## 🔧 開発

貢献に興味がありますか？

1.  **環境をセットアップ** (インストールのセクションを参照)。
2.  **テストを実行:**
    ```bash
    pytest
    ```
3.  **コードカバレッジを確認:**
    ```bash
    pytest --cov=src/kotemari
    ```

貢献ガイドラインについては `CONTRIBUTING.md` (作成予定) を参照してください。

## 📄 ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細については [LICENSE](LICENSE) ファイルを参照してください。

## 💻 サポートされている環境

*   **Python:** 3.8+
*   **OS:** Windows, macOS, Linux (主に Windows でテスト済み)

---

Kotemari で Python プロジェクト分析を簡素化しましょう！ 🌳 