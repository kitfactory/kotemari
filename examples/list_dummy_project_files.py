# examples/list_dummy_project_files.py

import sys
from pathlib import Path
import logging

# Add the 'src' directory to the Python path to allow importing 'kotemari'
# 'kotemari' をインポートできるように、'src' ディレクトリを Python パスに追加します。
project_dir = Path(__file__).resolve().parent.parent
src_dir = project_dir / "src"
sys.path.insert(0, str(src_dir))
# print(f"DEBUG: Source directory added to sys.path: {src_dir}", file=sys.stderr)
# print(f"DEBUG: Current sys.path: {sys.path}", file=sys.stderr)

# Import the main facade
# メインファサードをインポートします
from kotemari import Kotemari

# Configure basic logging to see output from Kotemari
# Kotemari からの出力を確認するために基本的なロギングを設定します
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


def main():
    """Example usage: List files in the dummy project."""
    # Path to the dummy project relative to this script's location
    # このスクリプトの場所からの相対的なダミープロジェクトへのパス
    dummy_project_path = project_dir / "tests" / "dummy_python_proj"

    print(f"Target Project Root: {dummy_project_path}")

    if not dummy_project_path.is_dir():
        print(f"Error: Dummy project directory not found at {dummy_project_path}", file=sys.stderr)
        print("Please ensure the dummy project exists in the 'tests' directory.", file=sys.stderr)
        sys.exit(1)

    try:
        # Initialize Kotemari with the dummy project path
        # ダミープロジェクトパスで Kotemari を初期化します
        kotemari = Kotemari(project_root=dummy_project_path)

        # Analyze the project (this loads file info and applies ignore rules)
        # プロジェクトを分析します（これによりファイル情報が読み込まれ、無視ルールが適用されます）
        print("\nAnalyzing project...")
        analysis_results = kotemari.analyze_project()
        print(f"Found {len(analysis_results)} non-ignored files.")

        # List the files (relative paths by default)
        # ファイルをリスト表示します（デフォルトでは相対パス）
        print("\nListing non-ignored files (relative paths):")
        file_list = kotemari.list_files()

        if file_list:
            for file_path in file_list:
                print(f" - {file_path}")
        else:
            print("(No non-ignored files found)")

        # Example: List absolute paths
        # 例: 絶対パスをリスト表示します
        print("\nListing non-ignored files (absolute paths):")
        abs_file_list = kotemari.list_files(relative=False)
        if abs_file_list:
            for file_path in abs_file_list:
                print(f" - {file_path}")
        else:
            print("(No non-ignored files found)")

        # Example: Generate and print the file tree
        # 例: ファイルツリーを生成して表示します
        print("\nGenerating file tree:")
        try:
            tree_output = kotemari.get_tree()
            print(tree_output)
        except RuntimeError as e:
            # This shouldn't happen if analyze_project was called, but handle just in case
            # analyze_project が呼び出されていればこれは起こらないはずですが、念のため処理します
            print(f"Error generating tree: {e}", file=sys.stderr)

    except Exception as e:
        logging.exception("An error occurred during the example execution:")
        print(f"\nAn error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 