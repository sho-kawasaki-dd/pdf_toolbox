PDFフラット化 Phase 3 を実装してください。

## 目的

Phase 1 / 2 は実装済みです。Phase 3 は品質固定と出荷文書に集中してください。

進め方は次の順序で固定します。

- fixture を増やして flatten の回帰対象を注釈だけでなくフォームまで広げる
- presenter / view の未整備テストを追加する
- README、設計書、リリースノート、HTML を更新する

壊れた Appearance Stream 系は、生成が不安定なら「クラッシュしないことを保証する異常 fixture」にフォールバックする前提で組んでください。

## 実装ステップ

### 1. flatten 用 fixture を追加する

`tests/conftest.py` に flatten 用 fixture を追加してください。

対象:

- form / widget 付き PDF
- broken appearance 系 PDF

最低条件:

- text field を含む
- checkbox か radio を含む
- `doc.bake()` が widget 側も平坦化することを自動テストに載せる

### 2. flatten processor 回帰テストを補強する

`tests/model/flatten/test_flatten_processor.py` を補強してください。これは 1 に依存します。

既存の annotated PDF に加えて、次の fixture を使った回帰ケースを追加してください。

- form fixture
- broken appearance fixture

主保証:

- 注釈が残らない
- widget が編集対象として残らない
- 異常 appearance でもクラッシュせず `finished` まで進む

### 3. flatten presenter テストを新設する

`tests/presenter/test_flatten_presenter.py` を新設してください。

参照元:

- `tests/presenter/test_compress_presenter.py`
- `tests/presenter/test_merge_presenter.py`

固定する観点:

- 初期 state
- PDF 追加
- フォルダ追加
- DnD
- 非対応入力の通知
- casefold 重複排除
- 削除 / 全削除
- execute 開始
- 上書き確認 yes / no 分岐
- polling
- 完了ダイアログ
- `is_busy`
- `has_active_session`
- `on_closing`

### 4. flatten view テストを新設する

`tests/view/flatten/test_flatten_view.py` を新設してください。3 と 4 は並行可能です。

参照元:

- `tests/view/compress/test_compress_view.py`

固定する観点:

- 生成確認
- 初期ボタン状態
- `update_flatten_ui` 反映
- 選択状態での remove 有効化
- 実行中の add / remove / clear / back-home 無効化
- PDF / フォルダの drop 受理
- 非 file drop の拒否
- `back_to_home_requested` シグナル

### 5. 既存の統合テストを必要最小限だけ補う

flatten 関連の既存統合テストを棚卸しし、足りないケースだけを追加してください。

方針:

- `tests/presenter/test_app_coordinator.py` は busy、active session、window closing 委譲がかなり揃っているため、重複は避ける
- `tests/view/test_main_window.py` は flatten wiring の smoke coverage だけを必要最小限で補う

### 6. 利用者向け文書を更新する

次の文書を更新してください。

`README.md`:

- バージョン更新
- ホーム画面の機能数
- 機能概要
- 起動確認
- よくあるトラブル

`docs/user-manual.md`:

- PDFフラット化の新章を追加
- 用途
- 基本操作
- 出力命名
- 上書き確認
- フォルダ再帰
- 実行中制約
- 暗号化 PDF とロック中ファイルの扱い

### 7. 開発者向け文書とリリース管理を更新する

これは 3 と 4 の完了後に行ってください。

`docs/developer-architecture.md`:

- flatten の Presenter / Model / View 構成
- worker と polling
- `fitz.Document.bake()` の責務
- 失敗系

`docs/release_note.md`:

- 先頭に `v1.1.0` を追加

`pyproject.toml`:

- バージョンを `1.0.3` から `1.1.0` へ更新

### 8. HTML を必ず再生成する

これは 6 と 7 に依存します。

`scripts/build-docs-html.ps1` を実行して、次の HTML を再生成してください。

- `README.html`
- `docs/user-manual.html`
- `docs/developer-architecture.html`
- `docs/release_note.html`

差分も確認してください。

## 関連ファイル

- `tests/conftest.py`
- `tests/model/flatten/test_flatten_processor.py`
- `tests/presenter/test_compress_presenter.py`
- `tests/presenter/test_merge_presenter.py`
- `presenter/flatten_presenter.py`
- `view/flatten/flatten_view.py`
- `tests/presenter/test_app_coordinator.py`
- `tests/view/test_main_window.py`
- `README.md`
- `docs/user-manual.md`
- `docs/developer-architecture.md`
- `docs/release_note.md`
- `pyproject.toml`
- `scripts/build-docs-html.ps1`

## 検証

狭い順で実施してください。

```bash
pytest tests/model/flatten/test_flatten_session.py tests/model/flatten/test_flatten_processor.py
pytest tests/presenter/test_flatten_presenter.py
pytest tests/view/flatten/test_flatten_view.py
pytest tests/presenter/test_app_coordinator.py -k flatten
pytest tests/view/test_main_window.py -k flatten
pytest tests/ -k flatten
powershell -ExecutionPolicy Bypass -File scripts/build-docs-html.ps1
```

最後に手動で次を確認してください。

- ホーム遷移
- PDF / フォルダ DnD
- 既存 `_flattened.pdf` の yes / no 分岐
- 暗号化 PDF 混在
- 注釈付き PDF
- フォーム付き PDF
- broken appearance 系 PDF
- 終了確認からの安全停止

## 決定事項

- fixture scope は、注釈 + フォーム + 壊れた Appearance Stream 系まで含める
- Phase 3 に `docs/release_note.md` と `pyproject.toml` の更新を含める
- HTML 再生成は必須とし、pandoc 前提で進める

## 実行ルール

- 既存スタイルに合わせて最小差分で実装すること
- 壊れた Appearance Stream 系は、生成が不安定なら「クラッシュしないことを保証する異常 fixture」にフォールバックすること
- 既存の統合テストとは責務を重複させず、flatten 固有の不足分だけを追加すること
- 関連テストと HTML 再生成を実行し、結果を簡潔にまとめること
- 未実施の手動確認項目があれば最後に明示すること
