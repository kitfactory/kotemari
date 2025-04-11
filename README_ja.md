# Kotemari 🌳 - Python プロジェクトの構造を瞬時に理解！

**Kotemari は、Python プロジェクトの依存関係構造を簡単に理解し、活用するのに役立ちます。** ✨

特定のモジュールをインポートしているファイルを知りたいと思ったことはありませんか？ あるいは、LLM プロンプトのために関連するすべてのコードを収集する必要がありましたか？ Kotemari はあなたの Python プロジェクトを分析し、依存関係をリアルタイムで追跡し、わずか数行のコードでコンテキストを提供します！

## 🤔 なぜ Kotemari？

*   ** とてつもなく簡単:** 数分で始められます。インストールして、プロジェクトを指定し、分析するだけ！ 🚀
*   **⚡️ リアルタイム認識:** ファイルの変更を自動的に検出し、依存関係をその場で更新します。
*   **🧠 インテリジェント分析:** Python のインポートを理解し、正確な依存関係グラフを構築します。
*   **🏎️ 効率的:** キャッシュを使用して、再分析を高速化します。
*   **🎯 多用途:** コードの理解、リファクタリング支援、LLM 用のコンテキスト生成などに最適です！
*   ** `.gitignore` を尊重:** 既存の無視ルールと連携します。

## ✨ 主な機能

*   **自動依存関係分析:** Python ファイルを解析して `import` 文を見つけます。
*   **リアルタイムファイル監視:** プロジェクトの変更（作成、変更、削除）を監視します。
*   **依存関係の伝播:** 依存関係の変更によって影響を受けるファイルのステータスを更新します。
*   **コンテキスト生成:** ファイルとその依存関係を含む整形されたコンテキスト文字列を作成します（LLM に役立ちます）。
*   **キャッシュ:** 分析結果を保存して、後続の実行を高速化します。
*   **`.gitignore` との統合:** `.gitignore` ファイルで定義されたルールを尊重します。

## 📦 インストール

```bash
pip install kotemari
```
*（注意: Kotemari はまだ PyPI で公開されていません。当面はソースからインストールしてください。）*

開発版をインストールするには:
```bash
git clone https://github.com/your-username/kotemari.git # 実際のリポジトリ URL に置き換えてください
cd kotemari
pip install -e .
```

## 🚀 基本的な使い方

Kotemari の使い方は信じられないほど簡単です！

```python
import logging
from pathlib import Path
from kotemari import Kotemari

# オプション: Kotemari が何をしているかを確認するためにログを設定します
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 1. プロジェクトのルートディレクトリで Kotemari を初期化します
project_path = Path("./path/to/your/python_project") # <-- これをあなたのプロジェクトパスに変更してください！
kotemari = Kotemari(project_path)

# 2. プロジェクトを分析します（初回は少し時間がかかる場合があります）
print("プロジェクトを分析中...")
kotemari.analyze_project()
print("分析完了！")

# 3. 分析されたすべてのファイルをリストします
print("\n分析されたファイル:")
for file_info in kotemari.list_files():
    print(f"- {file_info.path.relative_to(project_path)}")

# 4. 特定のファイルの依存関係を取得します
target_file = project_path / "src" / "module_a.py" # 例のファイル
print(f"\n{target_file.name} の依存関係:")
try:
    dependencies = kotemari.get_dependencies(target_file)
    if dependencies:
        for dep_path in dependencies:
            print(f"- {dep_path.relative_to(project_path)}")
    else:
        print("- 依存関係は見つかりませんでした。")
except FileNotFoundError:
    print(f"- ファイル {target_file.name} は分析結果に見つかりませんでした。")

# 5. 特定のファイルに依存するファイルを取得します（逆依存関係）
dependent_on_file = project_path / "src" / "utils.py" # 例のファイル
print(f"\n{dependent_on_file.name} に依存するファイル:")
try:
    reverse_deps = kotemari.get_reverse_dependencies(dependent_on_file)
    if reverse_deps:
        for rev_dep_path in reverse_deps:
            print(f"- {rev_dep_path.relative_to(project_path)}")
    else:
        print("- このファイルに依存するファイルはありません。")
except FileNotFoundError:
    print(f"- ファイル {dependent_on_file.name} は分析結果に見つかりませんでした。")

# 6. ファイルとその依存関係の整形済みコンテキストを取得します
context_file = project_path / "src" / "main_logic.py" # 例のファイル
print(f"\n{context_file.name} のコンテキストを生成中 (最大 4000 トークン):")
try:
    # max_tokens はコンテキストサイズを制限するのに役立ちます（LLM に便利です）
    context = kotemari.get_context(context_file, max_tokens=4000)
    print("--- コンテキスト開始 ---")
    print(context)
    print("--- コンテキスト終了 ---")
except FileNotFoundError:
    print(f"- ファイル {context_file.name} が見つかりませんでした。")
except Exception as e:
    print(f"コンテキスト生成中にエラーが発生しました: {e}")


# 7. オプション: バックグラウンドでファイル変更の監視を開始します
print("\nファイルウォッチャーを開始します（停止するには Ctrl+C を押してください）...")
kotemari.start_watching()

# ウォッチャーが動作するようにスクリプトを実行し続けます
try:
    # 例: 変更を待つか、他のロジックを実行します
    import time
    while True:
        # 変更により依存関係が古くなったかどうかを確認します
        # (このチェックをアプリケーションループに統合することもできます)
        # stale_files = [f for f in kotemari.list_files() if f.dependencies_stale]
        # if stale_files:
        #    print(f"\n依存関係が古くなっているファイルが検出されました: {[f.path.name for f in stale_files]}")
        #    # ここで再分析やコンテキストの再生成を行うことができます
        time.sleep(5)
except KeyboardInterrupt:
    print("\nウォッチャーを停止中...")
    kotemari.stop_watching()
    print("ウォッチャーが停止しました。")

print("\nKotemari の例が終了しました。")

```

**説明:**

1.  **`Kotemari(project_root)`:** プロジェクトディレクトリにリンクされたインスタンスを作成します。
2.  **`analyze_project()`:** ファイルをスキャンし、インポートを解析し、初期の依存関係グラフを構築します。キャッシュを使用するため、`force_reanalyze=True` が使用されない限り、後続の呼び出しは高速です。
3.  **`list_files()`:** 正常に分析されたすべてのファイルの `FileInfo` オブジェクトのリストを返します。
4.  **`get_dependencies(path)`:** 指定された `path` が直接インポートするファイルを表す `Path` オブジェクトのセットを返します。
5.  **`get_reverse_dependencies(path)`:** 指定された `path` を直接インポートするファイルを表す `Path` オブジェクトのセットを返します。
6.  **`get_context(path, max_tokens)`:** 指定された `path` とその直接の依存関係の内容を取得し、明確にフォーマットして、単一の文字列を返します。`max_tokens` は、大きすぎる出力を防ぐための概算の制限を提供します（LLM プロンプトに役立ちます）。ターゲットファイルのコンテンツを優先します。
7.  **`start_watching()` / `stop_watching()`:** ファイルシステムイベントを監視するバックグラウンドスレッドを管理します。関連する変更が発生すると、Kotemari は内部状態を更新します（例: 変更された依存関係を持つファイルを `dependencies_stale=True` としてマークするなど）。

## ⚙️ 設定（オプション）

*（`kotemari.toml` や初期化パラメータなどを介した設定オプションの詳細は、該当する場合にここに追加されます。）*

## 🙌 貢献

貢献を歓迎します！ इश्यू、機能リクエスト、またはプルリクエストを気軽に提出してください。

*（貢献ガイドラインはここに追加されます。）*

## 📄 ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細については [LICENSE](LICENSE) ファイルを参照してください。

## 💻 サポートされている環境

*   **Python:** 3.8+
*   **OS:** Windows, macOS, Linux (主に Windows でテスト済み)

---

Kotemari で Python プロジェクト分析を簡素化しましょう！ 🌳 