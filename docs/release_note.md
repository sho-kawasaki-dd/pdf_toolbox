# リリースノート

## v1.2.0

リリース日: 2026-04-27

### v1.2.0 概要

PDF 圧縮に Ghostscript エンジンを追加し、Windows 向け配布版へ bundled Ghostscript を含める前提で、Native / Ghostscript の 2 系統を切り替えられるようにしました。

あわせて、PDF フラット化後に Ghostscript 圧縮と任意の pikepdf 既定可逆最適化を流せる後処理パイプラインを追加し、フラット化成功後の圧縮だけが失敗した場合は flattened PDF を最終成果物として残す partial success 契約へ変更しました。

### v1.2.0 修正内容

- `model/external_tools.py` に外部ツール解決を集約し、Ghostscript は `winreg -> PATH -> bundled vendor binary`、pngquant は `PATH -> bundled vendor binary -> Pillow fallback` の順で解決するようにしました
- `model/compress/ghostscript_compressor.py` を追加し、Ghostscript プリセット / カスタム DPI / 互換性 floor / 基底フラグ / 後段 pikepdf 最適化を 1 つの経路へまとめました
- `view/compress/compress_view.py` と `presenter/compress_presenter.py` を更新し、圧縮画面を Native / Ghostscript タブ構成へ変更しました
- `model/flatten/flatten_session.py`、`model/flatten/flatten_processor.py`、`presenter/flatten_presenter.py`、`view/flatten/flatten_view.py` を更新し、フラット化後の Ghostscript 圧縮、partial success、warning 表示を追加しました
- compression / flatten / external tools の model・presenter・view テストを拡張し、Ghostscript 未検出状態、command builder、dispatch、flatten fallback publish を固定しました
- `README.md`、`docs/user-manual.md`、`docs/developer-architecture.md` を 1.2.0 の仕様へ更新し、HTML 文書も再生成対象に含めました
- `pyproject.toml`、`pdf_toolbox.spec`、`pdf_toolbox.iss`、`build-exe.ps1` の版数を 1.2.0 へ更新しました

### v1.2.0 影響範囲

- 利用者向け影響: Windows 配布版では Ghostscript を追加導入しなくても Ghostscript 圧縮と flatten 後処理を使えます。より新しい Ghostscript を使いたい場合は、システムへインストールした版が優先されます
- 互換性: Native 圧縮と既存の split / merge / extract / PDF→JPEG の基本操作は維持されますが、圧縮画面はタブ構成へ変わります
- 保守面: 外部バイナリ解決、Ghostscript command builder、flatten partial-success 契約がテストと文書に固定され、今後の改修で回帰を検出しやすくなります

### v1.2.0 確認済み事項

- `tests/model/test_external_tools.py`
- `tests/model/compress/test_ghostscript_compressor.py`
- `tests/model/compress/test_compression_dispatch.py`
- `tests/model/compress/test_compression_session.py`
- `tests/model/compress/test_compression_processor.py`
- `tests/model/compress/test_native_compressor.py`
- `tests/model/flatten/test_flatten_session.py`
- `tests/model/flatten/test_flatten_processor.py`
- `tests/presenter/test_compress_presenter.py`
- `tests/presenter/test_flatten_presenter.py`
- `tests/view/compress/test_compress_view.py`
- `tests/view/flatten/test_flatten_view.py`
- `tests/view/test_main_window.py`
- `tests/presenter/test_app_coordinator.py`
- `tests/test_imports.py`

## v1.1.0

リリース日: 2026-04-25

### v1.1.0 概要

PDF フラット化機能を追加し、注釈やフォーム付き PDF を編集不能な配布用 PDF として書き出せるようにしました。

あわせて、フォーム widget と broken appearance 系 PDF を含む回帰テスト、flatten presenter / view の単体テスト、利用者向け文書と開発者向け文書の更新を行いました。

### v1.1.0 修正内容

- `model/flatten/` に対して、フォーム widget 平坦化と broken appearance 系 PDF の回帰テストを追加しました
- `tests/conftest.py` に form / widget PDF と broken appearance PDF の fixture を追加しました
- `tests/presenter/test_flatten_presenter.py` と `tests/view/flatten/test_flatten_view.py` を追加し、flatten の状態遷移、上書き確認、DnD、実行中制約を固定しました
- `tests/presenter/test_app_coordinator.py` と `tests/view/test_main_window.py` の flatten smoke coverage を補強しました
- `README.md`、`docs/user-manual.md`、`docs/developer-architecture.md` を flatten 追加後の内容へ更新し、HTML も再生成対象に含めました

### v1.1.0 影響範囲

- 利用者向け影響: 注釈やフォームを含む PDF を `_flattened.pdf` として簡単に固定化できるようになります
- 互換性: 既存の split / merge / extract / compress / PDF→JPEG の操作手順は変わりません
- 保守面: flatten の worker / polling / failure 契約がテストと設計文書に固定され、今後の改修で回帰を検出しやすくなります

### v1.1.0 確認済み事項

- `tests/model/flatten/test_flatten_session.py`
- `tests/model/flatten/test_flatten_processor.py`
- `tests/presenter/test_flatten_presenter.py`
- `tests/view/flatten/test_flatten_view.py`
- `tests/presenter/test_app_coordinator.py -k flatten`
- `tests/view/test_main_window.py -k flatten`

## v1.0.3

リリース日: 2026-04-07

### v1.0.3 概要

PDF 圧縮機能で、CMYK JPEG 画像を含む PDF を非可逆圧縮した際に、画像の色が不安定になったり、後段の JPEG/PNG 保存処理が不安定になったりするケースへの対策を追加しました。

今回の更新では、PDF から抽出した CMYK 画像を RGB 系へ正規化してから後段の圧縮処理へ渡すようにし、ICC プロファイルを持つ画像ではその色情報を優先して扱います。

### v1.0.3 修正内容

- `model/compress/native_compressor.py` に、ICC プロファイルを考慮した CMYK → RGB 正規化処理を追加しました
- PDF 内画像の読み出し時と JPEG 保存前の両方で CMYK 画像を安全に扱うようにしました
- PNG 量子化前の画像モード正規化にも CMYK 分岐を追加し、JPEG 経路・PNG 経路の双方で同じ前提を保つようにしました
- CMYK JPEG を含むサンプル PDF フィクスチャと回帰テストを追加しました

### v1.0.3 影響範囲

- 利用者向け影響: CMYK JPEG を含む PDF でも、圧縮時の色崩れや保存失敗が起きにくくなります
- 互換性: UI 操作、圧縮モード、出力先ルールに変更はありません
- 保守面: PDF 圧縮パイプラインの入力画像モードが整理され、色空間差分による不具合を追跡しやすくなります

### v1.0.3 確認済み事項

- `tests/model/compress/test_native_compressor.py` の CMYK 関連テストを通過
- `tests/conftest.py` の CMYK サンプル PDF フィクスチャで回帰確認を追加

## v1.0.2

リリース日: 2026-04-02

### v1.0.2 概要

PDF 結合機能で、出力 PDF は生成されているにもかかわらず、GUI 上では「結合準備中」のまま完了判定されず、ツールバー操作も復帰しない不具合を修正しました。

あわせて、同じ構造の非同期ポーリングを持つ PDF 抽出機能にも予防修正を適用しました。

### v1.0.2 修正内容

- PDF 結合の Presenter で、バックグラウンド処理開始直後に初回ポーリングを必ず 1 回実行するよう修正しました
- PDF 結合で、処理が非常に短時間で完了した場合でも、完了通知、進捗表示、ボタン状態の復帰が正しく行われるようにしました
- PDF 抽出にも同様の初回ポーリング保証を追加し、同型の race condition を予防しました
- PDF 結合と PDF 抽出の Presenter テストに、即時完了ケースの回帰テストを追加しました

### v1.0.2 影響範囲

- 利用者向け影響: PDF 結合完了後に画面が準備中のまま固まることがある問題が解消されます
- 互換性: 既存の操作手順、UI 文言、出力仕様に変更はありません
- 保守面: 非同期処理の完了検知が安定し、短時間ジョブでも UI 状態が取り残されにくくなります

### v1.0.2 確認済み事項

- `tests/presenter/test_merge_presenter.py` を通過
- `tests/presenter/test_extract_presenter.py` を通過
- `tests/presenter/` 一式を通過
