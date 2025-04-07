# Kotemari (こてまり): LLMのためのコードベース理解ツール <0xF0><0x9F><0xA6><0xB1>✨

**Kotemari は、コードベースを分析し、依存関係を理解し、大規模言語モデル (LLM) のための正確でコンテキスト豊富なプロンプトを生成するために設計された Python ライブラリおよび CLI ツールです。** コードスニペットを手動で収集する時間を減らし、より多くの時間を結果を得るために使いましょう！ <0xF0><0x9F><0xA4><0xAF>

プロジェクトの構造と依存関係に基づいて必要なコンテキストを自動的に提供することで、コーディングタスクのための Retrieval-Augmented Generation (RAG) のプロセスを簡素化します。

## <0xF0><0x9F><0x9A><0x80> 主な機能

*   **<0xF0><0x9F><0x94><0x8D> プロジェクト分析 (`analyze`):** `.gitignore` や `.kotemari.yml` 設定を尊重してプロジェクトをスキャンし、ファイルの要約を提供します。
*   **<0xF0><0x9F><0x93><0x82> ファイル一覧 (`list`):** プロジェクト内の関連ファイル（無視ルール適用後）を一覧表示します。
*   **<0xF0><0x9F><0xAA><0xB3> ディレクトリツリー (`tree`):** プロジェクトファイルのクリーンなツリー構造（無視ルール適用後）を表示します。
*   **<0xF0><0x9F><0xAA><0xB2> 依存関係マッピング (`dependencies`):** Python の import 文を解析し、特定のファイルの依存関係を表示します（内部/外部モジュールを識別 - *注意: 内部モジュールの検出は改善中です*）。
*   **<0xE2><0x9C><0xA8> コンテキスト生成 (`context`):** 指定されたファイルの内容 *および* その関連する依存関係を自動的に収集し、LLM への入力に最適な包括的なコンテキスト文字列を作成します。
*   **<0xF0><0x9F><0x92><0xBE> キャッシュ:** プロジェクト構造情報をキャッシュすることで、後続の分析を高速化します。
*   **<0xF0><0x9F><0x91><0x80> ファイル監視 (`watch` - *実験的*):** ファイルの変更を監視し、分析を自動的に更新したりキャッシュをクリアしたりできます（開発ワークフローに役立ちます）。

## <0xF0><0x9F><0x9A><0x80> Kotemari を使う理由

*   **<0xE2><0x9C><0x85> 簡単なコンテキスト取得:** コードの手動コピー＆ペーストはもう不要！ Kotemari が関連ファイルと依存関係を見つける面倒な作業を行います。
*   **<0xF0><0x9F><0xA7><0xAE> 正確なプロンプト:** LLM に *適切な* コンテキストを提供することで、より良いコード生成、説明、デバッグ支援につながります。
*   **<0xF0><0x9F><0xA7><0xAD> 合理化されたワークフロー:** シンプルな CLI を介して開発プロセスにスムーズに統合されます。
*   **<0xF0><0x9F><0xAA><0xA1> 設定可能:** `.gitignore` とオプションの `.kotemari.yml` ファイルを使用して分析を微調整できます。

## <0xE2><0x9A><0x99><0xEF><0xB8><0x8F> インストール

pip を使って Kotemari を簡単にインストールできます:

```bash
pip install kotemari
```

## <0xF0><0x9F><0x92><0xBB> 基本的な使い方 (CLI)

プロジェクトのルートディレクトリに移動し、`kotemari` コマンドを使用します:

```bash
# プロジェクトを分析 (デフォルトでキャッシュを使用)
kotemari analyze

# 関連ファイルの一覧表示
kotemari list .

# プロジェクトツリーの表示
kotemari tree .

# 特定ファイルの依存関係を表示
kotemari dependencies src/my_module/main.py

# ファイルのコンテキストを生成 (依存関係を含む)
kotemari context src/my_module/main.py

# 複数ファイルのコンテキストを生成
kotemari context src/my_module/main.py src/my_module/utils.py

# キャッシュを使用せずに分析
kotemari analyze --no-use-cache 
```

その他のオプションについては、`kotemari --help` または `kotemari [COMMAND] --help` を使用してください。

## <0xF0><0x9F><0x92><0xBB> ライブラリとしての利用 (Python)

Kotemari は Python スクリプト内で直接使用することもできます:

```python
from pathlib import Path
from kotemari import Kotemari

# プロジェクトルートディレクトリを指定して初期化
project_path = Path("/path/to/your/project")
kotemari = Kotemari(project_root=project_path, use_cache=True)

# 1. プロジェクトを分析 (他のほとんどの操作の前に必要)
try:
    analyzed_files = kotemari.analyze_project()
    print(f"分析されたファイル数: {len(analyzed_files)}")
except Exception as e: # KotemariError またはそのサブクラスを捕捉
    print(f"分析中のエラー: {e}")
    exit()

# 2. 分析されたファイルを一覧表示
try:
    file_list = kotemari.list_files(relative=True)
    print("\n分析されたファイル:")
    for f in file_list:
        print(f"- {f}")
except Exception as e: # 例: analyze が呼ばれていない場合の AnalysisError
    print(f"ファイル一覧表示中のエラー: {e}")

# 3. 特定ファイルの依存関係を取得
try:
    # 存在しないファイルや分析対象外のファイルを指定するとエラーになります
    dependencies = kotemari.get_dependencies("src/module/my_file.py") 
    print("\nsrc/module/my_file.py の依存関係:")
    for dep in dependencies:
        print(f"- {dep.module_name} ({dep.dependency_type.name})")
except Exception as e: # 例: FileNotFoundErrorInAnalysis
    print(f"依存関係取得中のエラー: {e}")

# 4. ファイルのコンテキストを生成 (依存関係を含む)
try:
    # 存在しないファイルや分析対象外のファイルを指定するとエラーになります
    context = kotemari.get_context(["src/module/my_file.py"])
    print("\n生成されたコンテキスト:")
    print("-"*20)
    print(context)
    print("-"*20)
except Exception as e: # 例: FileNotFoundErrorInAnalysis, ContextGenerationError
    print(f"コンテキスト生成中のエラー: {e}")

# ツリー構造を取得することも可能 (ライブラリ利用では稀)
# try:
#     tree_str = kotemari.get_tree()
#     print("\nプロジェクトツリー:")
#     print(tree_str)
# except Exception as e:
#     print(f"ツリー取得中のエラー: {e}")

```

## <0xF0><0x9F><0x92><0xBB> 要件

*   **Python:** 3.9 以上
*   **オペレーティングシステム:** OS 非依存 (Windows, Linux, macOS でテスト済み)

## <0xF0><0x9F><0x93><0x9C> ライセンス

このプロジェクトは **MIT ライセンス** の下でライセンスされています。詳細は `LICENSE` ファイル（作成予定）をご覧ください。

## <0xF0><0x9F><0xAA><0xA1> 貢献

貢献を歓迎します！ Issue の報告やプルリクエストはお気軽にどうぞ。

*(より詳細な貢献ガイドラインは後日追加予定です。)*

---

Kotemari で快適なコーディングを！ <0xF0><0x9F><0xA6><0xB1>

# プロジェクトタイトル

このプロジェクトへようこそ。

## サポート環境
- Windows (Powershell)
- Python仮想環境 (.venv)

## 利用方法
仮想環境を有効にするには、以下のコマンドを実行してください:
.\.venv\Scripts\Activate.ps1 