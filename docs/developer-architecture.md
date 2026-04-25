# 開発者向け設計ドキュメント

このアプリは PySide6 ベースのデスクトップアプリで、MVP（Model / View / Presenter）を基本構成として実装されています。
文書の目的は、責務境界、依存関係、変更時の着地点を明確にすることです。

---

## 0. 目的

この文書では次の点を整理します。

- どの層に何を置くか
- どのファイルがどの機能の正本か
- 変更時にどこまで追うべきか

## 1. 全体構成

### 1.1 エントリーポイント

- `main.py`
  - `QApplication` を生成する
  - フォントとアプリアイコンを設定する
  - スプラッシュ画面を表示する
  - `MainWindow` と `AppCoordinator` を生成する
  - Qt イベントループを開始する

### 1.2 主要レイヤ

- View
  - `view/main_window.py`: 画面スタック、ダイアログ、タイマー、分割画面ショートカット
  - `view/home_view.py`: 機能カード一覧
  - `view/*`: 機能別画面
- Presenter
  - `presenter/app_coordinator.py`: 画面遷移と終了制御
  - `presenter/*_presenter.py`: 各機能の入力検証、状態同期、非同期結果処理
- Model
  - `model/pdf_document.py`: PDF プレビュー共通基盤
  - `model/*/session.py`: UI 非依存の状態管理
  - `model/*/processor.py`: バックグラウンド処理

### 1.3 機能一覧

- `split`: 1 PDF を複数 PDF に分割
- `merge`: 複数 PDF を 1 PDF に結合
- `extract`: 複数 PDF から任意ページを抽出して 1 PDF を作成
- `compress`: PDF / フォルダ / ZIP の一括圧縮
- `pdf-to-jpeg`: 単一 PDF の全ページ JPEG 書き出し

## 2. 依存関係の考え方

依存の向きは次のとおりです。

- `main.py` が View と Presenter を組み立てる
- Presenter は View と Model の両方を参照する
- View は Presenter へイベントを渡す
- Model は View を知らない

運用ルール:

- 業務ルールは View に書かない
- Qt ウィジェットの細かい API は Presenter に持ち込まない
- バックグラウンド処理は Processor に閉じ込める
- 画面遷移と終了制御は `AppCoordinator` に集約する

## 3. 画面構成と起動フロー

### 3.1 起動時の流れ

1. `main.py` が `QApplication` を生成する
2. スプラッシュを表示する
3. `MainWindow` を生成する
4. `AppCoordinator` が各 Presenter を組み立てる
5. ホーム画面を表示する

### 3.2 画面スタック

`MainWindow` は `QStackedWidget` を使って、次の画面を切り替えます。

- Home
- Split
- Merge
- Compress
- Extract
- PDF to JPEG

### 3.3 ホーム画面の正本

ホーム画面に表示する機能カードの正本は `view/home_view.py` の `FEATURES` です。
文書の機能一覧と画面表記がズレた場合は、まずここを基準に確認します。

## 4. 共通アーキテクチャパターン

### 4.1 Session

Session は各機能の UI 非依存状態を保持します。

主な責務:

- 入力パスや選択状態の保持
- 実行可否の判定
- 出力先や命名規則の保持
- ズームや選択順序などの画面状態の保持

### 4.2 Processor

Processor はファイル I/O や重い処理をバックグラウンドで実行します。

共通する特徴:

- 別スレッドで動く
- 結果はキューへ積む
- Presenter 側からポーリングされる
- 実行中フラグを持つ

結果メッセージは機能ごとに少し異なりますが、おおむね次の種別で運用されます。

- `progress`
- `finished` または `success`
- `failure` または `error`
- `cancelled`

### 4.3 Presenter

Presenter は View と Model の境界です。

主な責務:

- 入力検証
- Session 更新
- Processor 起動
- 結果キューのポーリング
- `UiState` の組み立て
- ダイアログ表示の判断

### 4.4 View

View は表示とイベント通知だけを担います。

主な責務:

- ウィジェット構築
- Presenter へのイベント委譲
- `update_*_ui()` による一括描画
- ダイアログとファイル選択の窓口
- `schedule()` によるタイマー提供

## 5. 機能別の責務整理

### 5.1 PDF 分割

- Presenter: `presenter/split_presenter.py`
- Model: `model/split/split_session.py`, `model/split/pdf_processor.py`, `model/pdf_document.py`
- View: `view/split/*`

主なポイント:

- `SplitSession` が分割点、セクション、ファイル名、ズームを保持する
- 分割点から `sections_data` を再構築する
- ファイル名はサニタイズされ、Windows 予約名も補正対象になる
- 分割画面だけ専用ショートカットがある

### 5.2 PDF 結合

- Presenter: `presenter/merge_presenter.py`
- Model: `model/merge/merge_session.py`, `model/merge/merge_processor.py`, `model/merge/thumbnail_loader.py`
- View: `view/merge/*`

主なポイント:

- 入力は PDF のみ
- 入力順の並び替えがそのまま結合順になる
- サムネイル読み込みと結合処理は別系統の非同期処理として動く
- 保存先が既存ファイルの場合は実行前に上書き確認する

### 5.3 PDF 抽出

- Presenter: `presenter/extract_presenter.py`
- Model: `model/extract/extract_session.py`, `model/extract/extract_processor.py`, `model/extract/page_thumbnail_loader.py`
- View: `view/extract/*`

主なポイント:

- Source と Target の 2 面構成で操作する
- Source は元 PDF 群、Target は出力 PDF のページ順を表す
- `ExtractSession` は Source 選択、Target 順序、ズーム、保存先を保持する
- 同じページを Target に重複追加できる
- `ExtractProcessor` は `ExtractPageSpec` の列から新しい PDF を組み立てる

### 5.4 PDF 圧縮

- Presenter: `presenter/compress_presenter.py`
- Model: `model/compress/compression_session.py`, `model/compress/compression_processor.py`, `model/compress/native_compressor.py`, `model/compress/settings.py`
- View: `view/compress/*`

主なポイント:

- 入力は PDF、ZIP、フォルダ
- 圧縮モードは `lossy`、`lossless`、`both`
- 既定値は `model/compress/settings.py` に集約される
- `model/compress/native_compressor.py` は、PDF 内ラスター画像を読み出した段階で CMYK JPEG を RGB へ正規化し、ICC プロファイルがある場合はそれを優先して変換する
- `model/compress/native_compressor.py` の非可逆圧縮は、PDF 画像の soft mask を復元し、透過付き画像を JPEG へ潰さず PNG 経路で再圧縮する
- PNG 量子化で `pngquant` を使うときは、`shutil.which("pngquant")` で解決した実行ファイルパスを shell なしで起動し、専用一時ディレクトリ、タイムアウト、Windows の `CREATE_NO_WINDOW` を付けて実行する
- `pngquant` が利用できない、失敗する、空出力を返す場合は画像単位で Pillow フォールバックへ降格し、バッチ全体の継続性を優先する
- 実行結果は成功、失敗、スキップを集計して完了ダイアログに出す

### 5.5 PDF → JPEG

- Presenter: `presenter/pdf_to_jpeg_presenter.py`
- Model: `model/pdf_to_jpeg/pdf_to_jpeg_session.py`, `model/pdf_to_jpeg/pdf_to_jpeg_processor.py`, `model/pdf_document.py`
- View: `view/pdf_to_jpeg/*`

主なポイント:

- 入力は単一 PDF のみ
- プレビューには `PdfDocument` を使い、書き出し自体は専用 Processor が担う
- 出力ファイル名は `PDF名_001.jpg` 形式
- 出力先は常に `保存先/PDF名/`
- 透明要素を含むページは白背景へ合成して JPEG 保存する

### 5.6 PDFフラット化

- Presenter: `presenter/flatten_presenter.py`
- Model: `model/flatten/flatten_session.py`, `model/flatten/flatten_processor.py`
- View: `view/flatten/*`

主なポイント:

- 入力は PDF とフォルダで、フォルダは再帰探索して `.pdf` のみを拾う
- `FlattenSession` は入力一覧、進捗件数、出力命名規則、Windows path 制約判定を保持する
- `FlattenProcessor.prepare_batch()` は探索、非 PDF / missing input の skip、既存出力との conflict 分離、出力パス長の preflight failure 化を担当する
- `FlattenProcessor.start_flatten()` は worker thread を起動し、result queue へ success / failure / skipped / progress / finished / cancelled を順次積む
- Presenter は `MainWindow.schedule()` を使って polling し、進捗文言、完了ダイアログ、cancel 後 close を制御する
- 実際の平坦化責務は `fitz.Document.bake()` に寄せ、annotation と widget を通常ページ内容へ焼き込んだ後、テンポラリ保存から `os.replace()` で確定する
- 失敗系として、invalid PDF、encrypted PDF、保存先 PermissionError、MAX_PATH 超過、broken appearance 系を failure / skip 集計へ落とし、バッチ全体の継続性を優先する

## 6. 画面遷移と終了制御

`presenter/app_coordinator.py` が画面遷移の共通ルールを持ちます。

主な責務:

- ホーム画面で選ばれた機能に応じて `MainWindow` の表示先を切り替える
- 各画面の「ホームへ戻る」を受け取り、実行中かどうかを確認する
- アクティブセッションがある場合は確認ダイアログを出す
- ウィンドウ終了時に、適切な Presenter の `on_closing()` を呼ぶ

実行中に共通して守るルール:

- 実行中はホームへ戻れない
- 終了時は確認ダイアログを出す
- 必要なポーリングタイマーを停止してから終了する

## 7. ショートカットとフォーカス制御

専用ショートカットは現時点で PDF 分割画面のみです。
`view/main_window.py` で `QShortcut` を `split_view` に登録し、表示画面に応じて有効化を切り替えています。

分割画面には 2 種類のキー処理があります。

- 画面全体ショートカット
  - `PageUp`, `PageDown`, `Ctrl+PageUp`, `Ctrl+PageDown`, `Home`, `End`, `Shift+Enter`, `Ctrl+Up`, `Ctrl+Down`
- 個別ウィジェットのキー処理
  - プレビュー: `Enter`, `Delete`, `z`, `Z`, `d`
  - ファイル名入力欄: `Tab`, `Enter`, `Shift+Enter`, `Delete`, `FocusOut`

キー操作を変えた場合は、利用者向け文書とショートカット文書も更新する必要があります。

## 8. 変更時の見方

### 8.1 画面ラベルや導線を変える場合

- `view/home_view.py`
- `view/main_window.py`
- `presenter/app_coordinator.py`
- `README.md`
- `docs/user-manual.md`

### 8.2 実行ルールや入出力仕様を変える場合

- 該当機能の `model/*/session.py`
- 該当機能の `model/*/processor.py`
- 該当機能の `presenter/*_presenter.py`
- `docs/user-manual.md`
- `docs/developer-architecture.md`

### 8.3 分割画面のキー操作を変える場合

- `view/main_window.py`
- `view/split/components/preview.py`
- `view/split/components/controls.py`
- `docs/keyboard-shortcuts.md`

## 9. テスト

`tests/` は概ね本体構成に対応しています。

- `tests/model/`: Session や処理ロジックの確認
- `tests/presenter/`: Presenter の入力検証、状態遷移、ダイアログ条件
- `tests/view/`: View の基本動作、画面構築、シグナル接続

新しい機能を足す場合は、少なくとも次の観点を押さえます。

- 入力不足時のエラー表示
- 正常系の状態遷移
- 実行中の UI 制限
- 出力先や命名規則の保持

## 10. ドキュメント更新方針

この文書は設計と責務の正本です。
操作手順は `docs/user-manual.md`、ショートカット一覧は `docs/keyboard-shortcuts.md`、概要と導線は `README.md` に寄せます。

同じ説明を複製しすぎないことを優先し、必要に応じて相互参照します。
