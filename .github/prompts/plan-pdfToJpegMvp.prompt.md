## Implement PDF to JPEG MVP

このリポジトリに、単一PDFを全ページJPEGへ書き出す最小機能を追加してください。既存のMVP構成と既存機能のUXパターンに合わせ、Model側で変換設定・出力命名・上書き判定を閉じ込め、Processorでバックグラウンド変換、Presenterで入力検証と進捗ポーリング、Viewで単一PDF入力と先頭ページプレビューを提供してください。

初版の仕様は次の通りです。

- 変換対象は単一PDFのみ
- 対象ページは全ページ固定
- 出力ファイル名は `PDF名_001.jpg` 形式の3桁ゼロ埋め
- 出力先はユーザー指定フォルダ直下ではなく、PDF名のサブフォルダ配下
- 同名JPEGが存在する場合は実行前に確認し、承認後は一括上書き
- 透明要素を含むページは白背景へ合成してJPEG保存
- この白背景仕様を操作画面に注記する
- MVPではDPI指定、サイズ変更、PNG出力、ページ範囲指定、命名テンプレート変更、ZIP出力、キャンセル機能は含めない

**Phased implementation plan**

無理なく実装できるよう、次のフェーズで進めてください。各フェーズは単独でレビューしやすく、途中で止めても破綻しない単位にしてください。

### Phase 1: Model と変換コアを完成させる

このフェーズでは、UIを先に広げず、変換ロジックと出力仕様を確定させてください。

1. `model/pdf_to_jpeg/` を新設し、SessionとProcessorを追加してください。
2. Sessionには、入力PDFパス、出力先フォルダ、出力サブフォルダ名、JPEG品質、進捗、実行可否判定、出力ファイル名生成規則を持たせてください。
3. 出力命名規則は `PDF名_001.jpg` 形式で固定してください。
4. 上書き確認のため、実変換前に競合候補一覧を収集できる構成にしてください。
5. ProcessorではPyMuPDFで各ページをレンダリングし、必要ならRGBAを白背景RGBへ合成してJPEG保存してください。
6. Processorは進捗、成功、失敗、完了の結果を、既存の圧縮機能や結合機能と同様にキュー経由で返してください。
7. `model/pdf_document.py` の既存読み込み・レンダリング責務を確認し、先頭ページプレビューには再利用できる部分だけを使ってください。
8. 書き出し処理はプレビュー都合の `frame_width` / `zoom` ベースAPIに寄せず、変換品質向けの専用処理として分けてください。

このフェーズの完了条件:

- 単体でJPEG書き出し処理が動く
- `PDF名_001.jpg` 形式の命名が確定している
- 競合ファイル一覧を事前取得できる
- 白背景合成を含む変換ロジックがテストできる

### Phase 2: Presenter と View を追加する

このフェーズでは、単一PDF入力のUIと、既存機能にそろえた操作フローを追加してください。

1. `view/pdf_to_jpeg/` 配下に新しい画面を追加してください。
2. 画面には、ヘッダー、単一PDF入力、選択中PDF表示、先頭ページプレビュー、JPEG品質スライダー、白背景注記、保存先選択、進捗表示、実行ボタンを含めてください。
3. 画面構成は既存の圧縮画面・結合画面と同系統にそろえてください。
4. View用のUiStateを定義し、入力済みか、保存先選択済みか、実行中か、何ページ目を処理中か、プレビュー画像があるか、注記文言、出力先表示文言などを1回の更新で反映できるようにしてください。
5. Presenterを追加し、PDF選択、保存先選択、品質変更、変換実行、結果ポーリング、完了通知、終了確認を扱ってください。
6. 競合ファイルがある場合は、件数または代表例を含めた上書き確認ダイアログを表示し、承認後に一括上書きで処理を開始してください。

このフェーズの完了条件:

- 単一PDFを選んで先頭ページプレビューを表示できる
- 保存先と品質を設定して変換を実行できる
- 実行中の進捗が画面に反映される
- 競合時に確認ダイアログが出る

### Phase 3: アプリ本体へ接続する

このフェーズでは、新機能を既存のホーム画面と画面遷移に統合してください。

1. `view/main_window.py` と `presenter/app_coordinator.py` に新画面と新Presenterを接続し、ホーム画面から遷移できるようにしてください。
2. 戻る操作と終了時の実行中制御は、既存3機能と同じルールに合わせてください。
3. `view/home_view.py` の `pdf-to-jpeg` カードを有効化し、準備中表示を解除してください。

このフェーズの完了条件:

- ホーム画面から PDF → JPEG 画面へ遷移できる
- 戻る操作と終了処理が既存機能と同じUXで動く
- 機能カードが準備中ではなく実際に使える

### Phase 4: テストとドキュメントを整備する

このフェーズでは、機能追加後の品質担保と説明の更新を行ってください。

1. テストを追加してください。Sessionの命名規則、出力サブフォルダ決定、上書き競合検出、品質値保持、Processorの白背景合成、Presenterの入力不足・保存先不足・上書き確認・進捗完了通知を優先してください。
2. Viewテストは既存粒度に合わせ、主要ボタン配線、プレビュー表示領域、進捗表示更新、実行中のボタン無効化を確認してください。
3. README、ユーザーマニュアル、開発者設計ドキュメントを更新し、PDF→JPEG機能の説明、制約、白背景仕様、出力フォルダ構成を反映してください。

このフェーズの完了条件:

- 主要ロジックと主要UI操作に対するテストがある
- 手動確認の観点がドキュメントと一致している
- ユーザー向け説明と開発者向け説明が更新されている

**Relevant files**

- `d:\programming\py_apps\pdf_toobox\presenter\app_coordinator.py` - 新Presenter生成、ホーム選択時の遷移、戻る/終了制御の追加
- `d:\programming\py_apps\pdf_toobox\view\home_view.py` - `pdf-to-jpeg` カードの有効化
- `d:\programming\py_apps\pdf_toobox\view\main_window.py` - 新画面生成、表示切替、Presenter接続、ダイアログ利用面の調整
- `d:\programming\py_apps\pdf_toobox\model\pdf_document.py` - 既存プレビュー基盤として再利用可否の確認対象
- `d:\programming\py_apps\pdf_toobox\model\compress\compression_processor.py` - バックグラウンド処理と結果ポーリング設計の参考
- `d:\programming\py_apps\pdf_toobox\presenter\compress_presenter.py` - 実行中制御、ポーリング、完了通知の参考
- `d:\programming\py_apps\pdf_toobox\presenter\merge_presenter.py` - 出力先確認と進捗反映の参考
- `d:\programming\py_apps\pdf_toobox\view\compress\compress_view.py` - ヘッダー、設定欄、進捗欄のUI参考
- `d:\programming\py_apps\pdf_toobox\view\merge\merge_view.py` - 出力欄と進捗欄のUI参考
- `d:\programming\py_apps\pdf_toobox\tests\presenter\` - 新Presenterテストの追加先
- `d:\programming\py_apps\pdf_toobox\tests\view\` - 新Viewテストの追加先
- `d:\programming\py_apps\pdf_toobox\README.md` - 機能概要と起動後導線の更新
- `d:\programming\py_apps\pdf_toobox\docs\user-manual.md` - 操作手順と白背景仕様の更新
- `d:\programming\py_apps\pdf_toobox\docs\developer-architecture.md` - 新機能の責務とフロー追加

**Verification**

1. Session単体テストで、`PDF名_001.jpg` からの連番生成、PDF名サブフォルダ生成、実行可否、JPEG品質保持、競合候補検出を確認してください。
2. Processor単体テストで、複数ページPDFからJPEGが生成されること、RGBAページが白背景RGBで保存されること、進捗イベントと完了イベントが返ることを確認してください。
3. Presenterテストで、入力不足時エラー、保存先不足時エラー、競合あり時の上書き確認、一括上書き承認後の開始、完了通知文言を確認してください。
4. Viewテストで、主要ボタン配線、プレビュー表示領域、進捗表示更新、実行中のボタン無効化を確認してください。
5. 手動確認で、ホームから遷移し、PDF選択、先頭ページプレビュー表示、保存先選択、変換実行、`output/PDF名/PDF名_001.jpg` 形式の出力、既存JPEG競合時の確認ダイアログ、完了通知を確認してください。
6. 手動確認で、透明背景を含むPDFページが白背景JPEGとして出力されることを確認してください。

**Implementation notes**

1. 変換品質の内部実装は、PyMuPDFのレンダリング倍率を固定値で持つか、将来のDPI追加を見越した設定名にするかを実装時に決めてください。初版はUIに出さず内部固定値で構いません。
2. 上書き確認ダイアログに表示する競合ファイル数と代表例の件数は、UI実装時に調整してください。初版は件数と先頭3件程度で十分です。
3. 先頭ページ以外のプレビューは初版では不要です。ただし、将来ページ移動を足しやすいようにViewレイアウトには余白を残してください。
4. 既存のMVP責務分離と画面遷移パターンを崩さないでください。
