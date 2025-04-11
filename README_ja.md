# Kotemari 🪄

[![PyPI version](https://img.shields.io/pypi/v/kotemari.svg?style=flat-square)](https://pypi.python.org/pypi/kotemari)
[![Build Status](https://img.shields.io/github/actions/workflow/status/<YOUR_GITHUB_USERNAME>/kotemari/ci.yml?branch=main&style=flat-square)](https://github.com/<YOUR_GITHUB_USERNAME>/kotemari/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/<YOUR_GITHUB_USERNAME>/kotemari?style=flat-square)](https://codecov.io/gh/<YOUR_GITHUB_USERNAME>/kotemari)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

Kotemari (こてまり) は、Python プロジェクトの構造を分析し、依存関係を理解し、GPT のような大規模言語モデル (LLM) 向けのコンテキストをインテリジェントに生成するための Python ツールです。🧠 関連するコードスニペットと依存関係のみを提供することで、LLM プロンプトに集中するのに役立ちます。また、リアルタイムのファイル監視機能も備えており、分析を簡単に最新の状態に保つことができます！ ✨

## 🤔 Kotemari を使う理由

大規模なコードベースと LLM を扱うのは難しい場合があります。プロジェクト全体のコンテキストを提供することは、多くの場合非効率的でコストがかかります。Kotemari はこれを解決します:

*   **🎯 スマートなコンテキスト生成:** LLM プロンプトに最適な、必要なファイルとその依存関係のみを含む簡潔なコンテキスト文字列を作成します。
*   **🔄 リアルタイム更新:** プロジェクトのファイルの変更を監視し、依存関係の理解をバックグラウンドで自動的に更新します。
*   **🔍 詳細なプロジェクト分析:** Python の `import` 文を分析して、プロジェクトファイル間の依存関係をマッピングします。
*   **⚙️ 柔軟な設定:** `.gitignore` を尊重し、`.kotemari.yml` 設定ファイル（オプション）によるさらなるカスタマイズを可能にします。
*   **💻 シンプルな CLI:** 分析、ファイル一覧表示、依存関係表示、コンテキスト生成のための使いやすいコマンドを提供します。

Kotemari は、あなたのコードに関する LLM との対話を **よりシンプルかつ効果的** にします。わずか数コマンドで関連性の高いコンテキストを取得しましょう！ 🎉

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

## ✨ 使い方 (CLI)

Kotemari は簡単な対話のためのコマンドラインインターフェースを提供します。

```bash
# まず仮想環境を有効化します！
source .venv/bin/activate # Windows の場合は .venv\Scripts\activate

# ヘルプを表示
kotemari --help

# カレントディレクトリのプロジェクトを分析
# (これにより、初期の理解とキャッシュが構築されます)
kotemari analyze

# 追跡されているすべてのファイルを表示 (.gitignore と .kotemari.yml を尊重します)
kotemari list

# プロジェクト構造をツリーとして表示
kotemari tree

# 特定のファイルの依存関係を表示
kotemari dependencies src/kotemari/core.py

# 特定のファイルのコンテキストを生成 (依存関係を含む)
kotemari context src/kotemari/gateway/cli_parser.py src/kotemari/controller/cli_controller.py

# より詳細なログのために verbose フラグを使用
kotemari analyze -v   # INFO レベルのログ
kotemari analyze -vv  # DEBUG レベルのログ
```

*(継続的なバックグラウンド監視のための `watch` コマンドは開発中であり、現在は実験的とマークされています)*

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