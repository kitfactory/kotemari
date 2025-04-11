\
    *   `[ ]` **12-5: テストの作成と実行:**
        *   `[x]` 12-5-1: 逆依存インデックスの構築・更新ロジックに対するユニットテストを作成する。 # Updated based on recent work
        *   `[x]` 12-5-2: ファイル変更 → 依存関係の波及 → 影響を受けるファイルの `FileInfo` 更新（またはフラグ設定）という一連の流れを確認する結合テストを作成する。 # Updated based on recent work
        *   `[x]` 12-5-3: 循環依存など、複雑な依存関係シナリオでのテストを追加する。 # Added circular dependency test

### Step 13: テストカバレッジの向上

*   **ゴール:** ライブラリ全体のテストカバレッジを向上させ、特にカバレッジが低いモジュール (`core.py`, `project_analyzer.py` など) の信頼性を高める。目標カバレッジを設定する (例: 70% 以上)。
*   **進め方:**
    1.  カバレッジレポート (`coverage html` などで生成) を詳細に分析し、テストされていないコード行やブランチを特定する。
    2.  特に `core.py`, `project_analyzer.py`, `gateway/`, `service/` 以下のカバレッジが低いモジュールに注力する。
    3.  特定された未テスト箇所に対して、ユニットテストまたは結合テストを優先度を付けて追加していく。
    4.  定期的にカバレッジを計測し、進捗を確認する。
*   **チェックリスト:**
    *   `[ ]` カバレッジレポート生成コマンドを設定 (`pyproject.toml` や CI スクリプト)。
    *   `[ ]` `core.py` の未テスト箇所に対するテスト追加:
        *   `[ ]` `__init__` のエラーケース (不正なパスなど)。
        *   `[ ]` `analyze_project` の `force_reanalyze=True` ケース。
        *   `[ ]` `list_files`, `get_tree` の詳細な出力内容検証。
        *   `[ ]` `get_dependencies`, `get_context` の `stale` フラグ未対応部分と基本動作テスト (Step 12-4-3 完了後)。
        *   `[ ]` `_process_event` の `moved` イベント処理。
        *   `[ ]` `start_watching`/`stop_watching` の詳細な動作 (スレッド/キュー連携など)。
        *   `[ ]` 各メソッドのエラーハンドリング/例外発生ケース。
    *   `[ ]` `project_analyzer.py` の未テスト箇所に対するテスト追加。
    *   `[ ]` `gateway/` 以下の未テスト箇所に対するテスト追加 (`FileSystemAccessor`, `GitignoreReader` など)。
    *   `[ ]` `service/` 以下の未テスト箇所に対するテスト追加 (`AstParser`, `FileSystemEventMonitor`, `PythonParser` など)。
    *   `[ ]` 設定した目標カバレッジの達成。

## 3. 注意事項 