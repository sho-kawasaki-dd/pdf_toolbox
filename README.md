# PDF Toolbox (PySide6)

PDFの分割、結合、圧縮、PDF→JPEG書き出しを行うデスクトップアプリケーションです。  
`main.py` から起動し、MVP（Model / View / Presenter）構成で実装されています。

対象読者:

- 日常的にPDFを扱うユーザー
- アプリを改修・保守する開発者

## 主な機能

- PDF分割: ページ単位のセクション分割、分割点編集、出力ファイル名編集
- PDF結合: 複数PDFの並び替え、サムネイル確認、1つのPDFへの結合
- PDF圧縮: PDF / フォルダ / ZIP を対象にしたバッチ圧縮
- PDF→JPEG: 単一PDFの全ページを JPEG へ一括書き出し

PDF→JPEG の初版仕様:

- 入力は単一PDFのみ
- 対象ページは全ページ固定
- 出力ファイル名は `PDF名_001.jpg` 形式の3桁ゼロ埋め
- 出力先は指定フォルダ直下ではなく `保存先/PDF名/` サブフォルダ配下
- 既存JPEGと衝突する場合は実行前に確認し、承認後は一括上書き
- 透明要素を含むページは白背景へ合成して JPEG 保存

## ドキュメント

- 非開発者向け取扱説明書: [docs/user-manual.md](docs/user-manual.md)
- ショートカット一覧: [docs/keyboard-shortcuts.md](docs/keyboard-shortcuts.md)
- 開発者向け設計・フロー図: [docs/developer-architecture.md](docs/developer-architecture.md)

読み進め方の目安:

- はじめて使う: `user-manual` → `keyboard-shortcuts`
- 改修する: `developer-architecture` → 該当ソースコード
- 画面遷移や導線を変える: `presenter/app_coordinator.py` と `view/main_window.py`

## 最短で起動する（ソース実行）

1. Pythonを用意（`pyproject.toml` では `>=3.14`）
2. 任意の仮想環境を有効化
3. 依存をインストール

   ```bash
   pip install -U pyside6 pillow pymupdf pikepdf
   ```

4. アプリを起動

   ```bash
   python main.py
   ```

5. 起動表示を確認
   - 起動時に中央へスプラッシュが表示されます
   - スプラッシュは最小1秒表示され、初期化完了後に自動で閉じます
   - ホーム画面から各機能カードへ遷移できます

### PDF→JPEG の最短操作

1. ホーム画面で「PDF → JPEG」を選択
2. 単一PDFを選択し、先頭ページプレビューを確認
3. JPEG品質を調整
4. 保存先フォルダを選択
5. 「JPEG書き出しを実行」を押す
6. `保存先/PDF名/PDF名_001.jpg` 形式で出力されることを確認

## Windowsで実行ファイルを作成する（onedir）

1. 仮想環境を有効化し、依存をインストール

   ```bash
   pip install -U pyside6 pillow pymupdf pikepdf pyinstaller
   ```

2. PowerShell スクリプトを実行

   ```powershell
   .\scripts\build-exe.ps1
   ```

3. 生成物を確認
   - 実行ファイル: `dist/` 配下のビルド成果物
   - 補助ファイル: ビルドスクリプトが利用する spec / assets 一式

4. 動作確認
   - アプリを起動
   - ホーム画面から各機能へ遷移できることを確認
   - PDF→JPEG では PDF選択 → プレビュー → 保存先選択 → 実行 まで確認

補足:

- 初回起動時に SmartScreen 警告が表示される場合があります
- onedir は onefile より起動が安定しやすく、トラブルシュートが容易です

## 実行ファイル配布版を使う場合

配布された実行ファイル（例: `.exe`）を起動してください。  
操作方法はソース実行版と同じです。

配布版での確認ポイント:

- セキュリティ警告が表示された場合は、配布元の案内に従って実行許可を行います
- 保存先に書き込み権限があるフォルダを選択してください
- PDF→JPEG では出力先サブフォルダが自動生成されます

## よくあるトラブル

- PDF→JPEG の実行前に上書き確認が出る
  - 既存の `PDF名_001.jpg` などが出力先サブフォルダに存在しています
  - 内容を確認し、問題なければ上書きを承認してください
- JPEG出力の背景が白になる
  - 透明要素を含むページは、初版仕様として白背景へ合成して保存します
- 保存エラーが出る
  - 出力先ファイルを他アプリで開いていないか確認
  - 書き込み権限のあるフォルダを選択

## ドキュメント更新ルール

- UI操作やキー操作を変更したら、`docs/user-manual.md` と `docs/keyboard-shortcuts.md` を更新
- MVPの責務や処理フローを変更したら、`docs/developer-architecture.md` を更新
- 導線や起動手順を変更したら、この `README.md` を更新

### Markdown から HTML を再生成する

PowerShell で次を実行すると、`README.md` と `docs/*.md` を `github-markdown.css` を参照する HTML に変換できます。

```powershell
./scripts/build-docs-html.ps1
```
