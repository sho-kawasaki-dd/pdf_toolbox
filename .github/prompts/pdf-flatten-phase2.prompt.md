---
name: 'PDF Flatten Phase 2'
description: 'PDFフラット化 Phase 2 の UI と統合実装を、このリポジトリの方針に従って進める'
argument-hint: '必要なら追加の制約や補足を書く'
agent: 'agent'
model: 'GPT-5 (copilot)'
---

PDFフラット化 Phase 2 を実装してください。

## 目的

Phase 2 は UI と統合に集中します。方針は確定済みです。

- 上書き確認は一括要約表示にする
- 「いいえ」を選んだ場合は衝突分だけ skip する
- 実行中のウィンドウ終了は、安全キャンセル完了後に close する

実装上の注意点として、`flatten_processor.py` の `prepare_batch` は `conflicts` を分離しますが、「overwrite 実行」または「skip 計上」へ変換する受け皿がまだありません。ここだけは Presenter 実装を成立させるための最小限の隣接調整として扱ってください。

## 実装ステップ

### 1. 実行契約を固定する

`presenter/flatten_presenter.py` に Presenter ローカルの plan 解決 helper を置く前提で進めてください。

- `conflicts` を `allow_overwrite=True` の job に変換する
- または `type=skipped` の preflight issue に変換する

この切り替えで `flatten_processor.py` の `start_flatten` 契約を崩さず、skip 件数にも自然に載せてください。

### 2. FlattenView を新設する

新規作成する `view/flatten/flatten_view.py` では、`compress_view.py` を縮小テンプレートとして使ってください。

同居させる要素:

- `FlattenInputItem`
- `FlattenUiState`
- `DroppableInputList`
- `FlattenView`

画面要素は次だけに絞ってください。

- 入力一覧
- PDF追加
- フォルダ追加
- 選択削除
- 一覧クリア
- 進捗バー
- 進捗文言
- 集計文言
- 実行ボタン
- ホームへ戻る

設定 UI は持ち込まないでください。共通部品抽出もこの Phase では行わないでください。

### 3. MainWindow の受け口を追加する

`main_window.py` に次を追加してください。

- `FlattenView` の import
- `self.flatten_view`
- stack 登録
- `set_flatten_presenter`
- `show_flatten`
- `update_flatten_ui`

確認ダイアログは既存の `ask_yes_no` と `ask_ok_cancel` をそのまま使ってください。新 API は不要です。

### 4. FlattenPresenter を実装する

新規作成する `presenter/flatten_presenter.py` は、`compress_presenter.py` を主テンプレート、`merge_presenter.py` を終了処理テンプレートとして使ってください。

最低限含めるメソッド:

- `has_active_session`
- `is_busy`
- `add_pdf_files`
- `add_folder`
- `handle_dropped_paths`
- `remove_selected_inputs`
- `clear_inputs`
- `execute_flatten`
- `on_closing`
- `_append_inputs`
- `_poll_flatten_results`
- `_build_completion_message`
- `_build_ui_state`

実装ルール:

- 重複判定は `as_posix().casefold()` に統一する
- 存在する PDF とフォルダだけ受理する
- `execute_flatten` では `prepare_batch` を一度だけ走らせる
- `conflicts` があれば、件数と先頭数件だけを `ask_yes_no` で表示する
- 「はい」なら overwrite job 化する
- 「いいえ」なら skip issue 化して、非衝突 job だけ続行する

### 5. 実行中 UX を Presenter に反映する

実行中は次をすべて無効化してください。

- 入力変更
- 再実行
- ホーム遷移

`progress_text` は次を切り替えてください。

- `待機中`
- `進捗: X / Y (Z%)`
- `キャンセル中...`

完了メッセージには、成功 / 失敗 / スキップ件数を含めてください。失敗例と skip 例は 2〜3 件だけ出してください。

終了時は `merge` と同じ `_close_after_cancel` パターンに統一してください。

- `ask_ok_cancel`
- `request_cancel`
- ポーリング継続
- 停止後に `destroy_window`

### 6. Home と Coordinator を統合する

`home_view.py` の `FEATURES` に flatten を追加してください。

- ラベルは `PDFフラット化`
- アイコンは `pdf_flattener_icon.png`

`app_coordinator.py` には次を追加してください。

- `FlattenPresenter` の生成
- `show_flatten` へのルーティング
- `back_to_home` 接続
- `on_back_to_home` の busy/session ガード
- `on_window_closing` の委譲

戻る操作は他機能と同じ規則にしてください。

- 実行中は block
- アイドルかつセッションありなら保持確認を出す

### 7. 既存スモークテストだけ更新する

`test_home_view.py` では次を確認してください。

- flatten カードの活性
- ラベル
- アイコン
- クリックイベント
- マスコット位置が `(2, 0)` へ移ること

`test_main_window.py` では次を追加してください。

- `show_flatten`
- `set_flatten_presenter`
- `update_flatten_ui`

`test_app_coordinator.py` では次を追加してください。

- flatten 遷移
- busy 中 `back-to-home` block
- active session 確認
- window closing 委譲

flatten presenter/view の網羅テストは Phase 3 に残してください。

### 8. 手動確認項目を守る

Phase 2 の完了条件として、次を手動確認対象として扱ってください。

- ホームカードからの遷移
- PDF 単体追加
- フォルダ追加
- DnD
- 重複投入時の無視
- 既存 `_flattened.pdf` ありでの一括確認
- 「いいえ」時の衝突分 skip 継続
- 実行中のホーム無効
- 実行中 close の安全キャンセル後終了

## 関連ファイル

- `flatten_processor.py`
- `flatten_session.py`
- `presenter/flatten_presenter.py`
- `compress_presenter.py`
- `merge_presenter.py`
- `app_coordinator.py`
- `view/flatten/flatten_view.py`
- `compress_view.py`
- `main_window.py`
- `home_view.py`
- `test_home_view.py`
- `test_main_window.py`
- `test_app_coordinator.py`

## 検証

まず次を実行してください。

```bash
pytest test_home_view.py test_main_window.py test_app_coordinator.py
```

実装と同時に軽い presenter スモークを追加するなら、先に次を回してください。

```bash
pytest tests/presenter/test_flatten_presenter.py
```

その後に上の既存スモークを再実行してください。

さらに手動で次を確認してください。

- 上書き確認が「件数 + 先頭数件」表示になっていること
- 「いいえ」で衝突分だけ skip されること
- 実行中 close が即終了ではなく cancel 完了待ちになること

## スコープ

含む:

- flatten の Presenter
- View
- MainWindow / Home / Coordinator 統合
- 既存スモーク更新

含まない:

- flatten 専用の網羅テスト追加
- ドキュメント更新
- processor 全面再設計
- UI 共通部品の抽出

## 実行ルール

- 既存スタイルに合わせて最小差分で実装すること
- `flatten_processor.py` の既存契約を壊さないこと
- 関連テストを実行して、結果を簡潔にまとめること
- 未実施の手動確認項目があれば、最後に明示すること
