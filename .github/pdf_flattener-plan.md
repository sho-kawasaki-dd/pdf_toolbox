## Plan: PDFフラット化追加

PyMuPDF の [fitz.Document.bake()](http://_vscodecontentref_/0) を使って、注釈とウィジェットをコンテンツへ焼き付ける新機能 `PDFフラット化` を、既存の [compress](http://_vscodecontentref_/1) 系のバッチ処理パターンを再利用して追加する。入力は PDF ファイルとフォルダの DnD / ダイアログに対応し、出力は元 PDF と同じフォルダへ `_flattened.pdf` を付けて保存する。既存ファイルがある場合は実行前または対象ごとに上書き確認を行い、ホーム画面 2 行 3 列目には追加済みの [pdf_flattener_icon.png](http://_vscodecontentref_/2) を使う。

**Steps**

1. Phase 1: モデル層を追加する。`d:\programming\py_apps\pdf_toobox\model\flatten\` を新設し、`FlattenSession` に入力パス、進捗、出力名生成、衝突候補の整理を持たせる。[CompressionSession](http://_vscodecontentref_/3) の [input_paths](http://_vscodecontentref_/4) / 進捗集計 / ファイル名正規化の責務を参考にしつつ、今回の仕様に合わせて PDF とフォルダのみを扱う状態モデルへ絞る。
2. Phase 1: `FlattenProcessor` を追加する。`fitz.open()` → `doc.bake()` → `save()` の単位処理を持ち、フォルダ入力は再帰的に PDF を列挙してジョブ化する。フォルダ探索、PDF 判定、暗号化判定、衝突確認、`bake()`、保存までをバックグラウンドスレッドで処理し、UI スレッドではポーリング結果の反映だけを行う。スレッド実行、結果キュー、`is_running` フラグ、`poll_results()`、`request_cancel()` は `MergeProcessor` / `ExtractProcessor` と同系のインターフェースにそろえる。保存は元ファイルと同じフォルダへ `_flattened.pdf` を付け、一時ファイルへ保存後に置換する。キャンセルは協調キャンセルとし、実行中の 1 ファイル処理完了境界で安全に停止する。
3. Phase 1: 失敗系を明示する。存在しないパス、PDF 以外、不正 PDF、パスワード保護または暗号化された PDF、`bake()` 実行例外、保存失敗、出力先ファイルのロック、出力パス長超過を個別メッセージとして返し、バッチ全体は継続する。`fitz.open()` 後に `doc.needs_pass` / `doc.is_encrypted` を確認し、保護された PDF は安全に失敗またはスキップとして扱う。`PermissionError` 発生時は「ファイルが他のアプリで開かれています」と分かる専用メッセージを返す。Windows 環境のパス長制限を考慮し、最終出力パスだけでなく一時ファイルパスも検証対象に含め、制限超過時は明示的な失敗として扱う。ここは `pdf_to_jpeg_processor.py` の `fitz.FileDataError` ハンドリング、`merge_processor.py` の finished/progress/failure/cancelled キュー形式、`split/pdf_processor.py` の `PermissionError` 文言を参照する。
4. Phase 2: Presenter を追加する。`d:\programming\py_apps\pdf_toobox\presenter\flatten_presenter.py` を作成し、`CompressionPresenter` の入力管理パターンをベースに `add_pdf_files()`、`add_folder()`、`handle_dropped_paths()`、`remove_selected_inputs()`、`clear_inputs()`、`execute_flatten()`、`on_closing()` を持たせる。DnD とダイアログの受け口を一本化し、入力受付は PDF とフォルダのみ、重複排除は既存 presenter と同様に `Path(...).casefold()` ベースで処理する。実行中は入力変更とホームへの戻る操作を無効化し、進捗表示は worker のポーリング結果のみで更新する。終了操作では確認ダイアログを出し、承認時は `request_cancel()` を発行して安全停止完了後にのみウィンドウを閉じる。
5. Phase 2: 上書き確認の UX を定義して実装する。既存出力が 1 件以上ある場合、実行開始前に対象一覧の要約を出して一括確認する設計を第一候補にし、[MainWindow](http://_vscodecontentref_/20) に確認ダイアログ API が足りなければ最小限追加する。確認拒否時は衝突分をスキップし、それ以外の非衝突ジョブは継続処理できる形にする。
6. Phase 2: View を追加する。`d:\programming\py_apps\pdf_toobox\view\flatten\flatten_view.py` を新設し、[CompressionView](http://_vscodecontentref_/21) のレイアウトを縮小した単純版として、入力一覧、PDF追加、フォルダ追加、選択削除、一覧クリア、進捗表示、実行ボタン、ホームへ戻る導線を持たせる。ラベルは `PDFフラット化` とし、DnD ヒントには PDF / フォルダ対応を明記する。
7. Phase 2: アプリ統合を行う。`home_view.py` の `FEATURES` に `("flatten", "pdf_flattener_icon.png", "PDFフラット化", True)` を追加し、マスコットカードが次行へ移る前提でテストも更新する。`main_window.py` に `FlattenView` の保持・表示・UI 更新メソッドを追加し、必要なら終了時に close handler を安全にバイパスできる最小限の API を追加する。`app_coordinator.py` に `FlattenPresenter` の生成、feature key ルーティング、back-to-home、window closing 判定を追加する。戻る操作は他機能と同様に実行中は無効化する。

- アプリ終了時のみ、処理中断の確認を行い、承認時は協調キャンセルで安全停止してから終了する。
- Windows のパス長制限を考慮し、出力パスまたは一時ファイルパスが長すぎる場合は自動フォールバックせず明示的な失敗として扱う。

8. Phase 3: テストを追加する。モデル層はセッションの出力名生成、フォルダ列挙、衝突判定、進捗集計、予約名処理、出力パス長検証を検証する。プロセッサ層は成功、不正 PDF、非 PDF 混在、フォルダ再帰、暗号化 PDF、既存出力への確認分岐、`PermissionError`、キャンセル要求、キャンセル完了後の安全停止を検証する。Presenter 層は DnD/ダイアログ入力、重複排除、実行開始、ポーリング完了メッセージ、実行中の入力変更禁止、実行中の戻る無効化、終了確認、キャンセル後の終了を検証する。View / Home 統合では新カードの表示、ラベル、アイコン、シグナル、マスコット位置変更を確認する。
9. Phase 3: ドキュメントを更新する。[README.md](http://_vscodecontentref_/26)、[user-manual.md](http://_vscodecontentref_/27)、[developer-architecture.md](http://_vscodecontentref_/28) に `PDFフラット化` の用途、入力形式、出力命名、上書き確認、[fitz.Document.bake()](http://_vscodecontentref_/29) 利用を反映し、必要なら HTML ドキュメント再生成手順も計画へ含める。
10. Phase 3: 全体検証を実施する。追加した個別テストを先に回し、その後関連スイートとドキュメント生成を確認する。最後にホーム画面からの遷移、DnD、フォルダ入力、既存出力あり/なし、暗号化 PDF 混在、既存 `_flattened.pdf` を他アプリで開いた状態、終了確認からのキャンセル、終了確認からの安全停止を手動確認する。

**Relevant files**

- [home_view.py](http://_vscodecontentref_/30) — [FEATURES](http://_vscodecontentref_/31) 定義、マスコット配置ロジック、ホームカード追加
- [app_coordinator.py](http://_vscodecontentref_/32) — [FEATURE_LABELS](http://_vscodecontentref_/33)、[\_on_feature_selected()](http://_vscodecontentref_/34)、[on_back_to_home()](http://_vscodecontentref_/35)、[on_window_closing()](http://_vscodecontentref_/36) の新機能統合
- [main_window.py](http://_vscodecontentref_/37) — `FlattenView` の生成、`set_flatten_presenter()`、`show_flatten()`、`update_flatten_ui()`、確認ダイアログ API 追加候補
- [compress_presenter.py](http://_vscodecontentref_/38) — バッチ入力・DnD・ポーリング・完了ダイアログの参照実装
- [compress_view.py](http://_vscodecontentref_/39) — [DroppableInputList](http://_vscodecontentref_/40) と一覧中心 UI の参照実装
- [compression_session.py](http://_vscodecontentref_/41) — 入力正規化、進捗集計、ファイル名正規化、衝突処理の参照実装
- [merge_processor.py](http://_vscodecontentref_/42) — バックグラウンドワーカー、結果キュー、進捗通知の参照実装
- [pdf_to_jpeg_processor.py](http://_vscodecontentref_/43) — [fitz.FileDataError](http://_vscodecontentref_/44) を含む PyMuPDF エラーハンドリング参照
- [pdf_flattener_icon.png](http://_vscodecontentref_/45) — 新機能カードのアイコン
- [test_home_view.py](http://_vscodecontentref_/46) — ホーム画面カードとマスコット配置テストの更新
- [test_compress_presenter.py](http://_vscodecontentref_/47) — Presenter テスト構造の参照
- [test_merge_processor.py](http://_vscodecontentref_/48) — Processor テスト構造の参照

**Verification**

1. `pytest test_home_view.py tests/presenter/test_flatten_presenter.py tests/model/flatten/test_flatten_session.py tests/model/flatten/test_flatten_processor.py`
2. `pytest test_app_coordinator.py tests/view/test_main_window.py`
3. フォルダ入力を含む手動確認: ホーム画面の `PDFフラット化` カードから遷移し、PDF 単体・PDF を含むフォルダ・非 PDF 混在フォルダの DnD とダイアログ選択を確認する。
4. 手動確認: `_flattened.pdf` の生成先が元ファイルと同じフォルダであること、既存出力がある場合に上書き確認が出ること、拒否時は非衝突ジョブだけ継続することを確認する。
5. 生成物確認: 出力 PDF を PyMuPDF で再オープンし、注釈 / ウィジェットが見た目として残り、編集可能注釈としては消えることを確認するための回帰用サンプル PDF を用意して検証する。
6. ドキュメント更新時は `powershell -ExecutionPolicy Bypass -File scripts/build-docs-html.ps1` を実行し、HTML の再生成差分を確認する。

**Decisions**

- 機能ラベルは `PDFフラット化`、ホーム画面の feature key は `flatten` を前提とする。
- 入力は複数 PDF の一括処理に対応し、DnD とダイアログの両方で受け付ける。
- DnD / ダイアログでは PDF ファイルに加えてフォルダ投入を許可し、フォルダ内 PDF は再帰的に探索する。
- 出力は元ファイルを上書きせず、同じフォルダへ `_flattened.pdf` を付けて保存する。
- 既存出力がある場合は上書き確認を行う。自動連番は今回のスコープに含めない。
- ホーム画面 2 行 3 列目には [pdf_flattener_icon.png](http://_vscodecontentref_/49) を使い、既存マスコットカードは次の行へ移動する。
- `doc.bake()` の対象選択 UI は設けず、注釈とウィジェットを一括で焼き付ける単機能とする。

**Further Considerations**

1. テスト用に注釈付き PDF とフォーム付き PDF の専用 fixture を追加する。既存 fixture だけでは `doc.bake()` の回帰を十分に担保できない可能性が高い。
2. 可能であれば Appearance Stream が壊れている、または欠落している注釈を含む PDF fixture を 1 つ追加し、PyMuPDF 更新時の耐性変化を検知できるようにする。
3. 上書き確認の粒度は一括確認を推奨する。対象ごとの確認ダイアログ連打はバッチ処理 UX を悪化させるため、要件変更がなければ避ける。
