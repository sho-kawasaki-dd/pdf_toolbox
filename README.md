# PDF Splitter (CustomTkinter)

PDFをページ単位のセクションに分割して保存する、デスクトップアプリケーションです。  
`main.py` から起動し、MVP（Model / View / Presenter）構成で実装されています。

対象読者:

- 日常的にPDF分割を行うユーザー
- アプリを改修・保守する開発者

## 主な機能

- PDFを開いてページをプレビュー
- 分割点の追加・削除
- セクションごとの出力ファイル名編集
- 全ページを1ページずつ分割
- バックグラウンドで分割処理を実行

## ドキュメント

- 非開発者向け取扱説明書: [docs/user-manual.md](docs/user-manual.md)
- ショートカット一覧: [docs/keyboard-shortcuts.md](docs/keyboard-shortcuts.md)
- 開発者向け設計・フロー図: [docs/developer-architecture.md](docs/developer-architecture.md)

読み進め方の目安:

- はじめて使う: `user-manual` → `keyboard-shortcuts`
- 改修する: `developer-architecture` → 該当ソースコード
- 起動表示を改修する: `main.py` と `view/startup_splash.py`

## 最短で起動する（ソース実行）

1. Pythonを用意（`pyproject.toml` では `>=3.14`）
2. 任意の仮想環境を有効化
3. 依存をインストール

   ```bash
   pip install -U customtkinter pillow pymupdf
   ```

4. アプリを起動

   ```bash
   python main.py
   ```

5. 起動表示を確認

   - 起動時に中央へスプラッシュが表示されます（白背景 + アプリアイコン）
   - スプラッシュは最小1秒表示され、初期化完了後に自動で閉じます

補足:

- 起動後、まず「PDFを開く」で対象ファイルを選択します
- 分割実行時に保存先フォルダを都度選択します

## Windowsで実行ファイルを作成する（onedir）

1. 仮想環境を有効化し、依存をインストール

   ```bash
   pip install -U customtkinter pillow pymupdf pyinstaller
   ```

2. `PDFSplitter.spec` を使ってビルド

   ```bash
   pyinstaller --noconfirm --clean PDFSplitter.spec
   ```

   または PowerShell スクリプトを実行:

   ```powershell
   .\scripts\build-exe.ps1
   ```

3. 生成物を確認

   - 実行ファイル: `dist/PDFSplitter/PDFSplitter.exe`
   - specファイル: `PDFSplitter.spec`

4. 動作確認

   - `dist/PDFSplitter/PDFSplitter.exe` を起動
   - 起動時にスプラッシュが表示されることを確認
   - 「PDFを開く」→分割→保存まで実行できることを確認

補足:

- 初回起動時に SmartScreen 警告が表示される場合があります
- onedir は onefile より起動が安定しやすく、トラブルシュートが容易です

## 実行ファイル配布版を使う場合

配布された実行ファイル（例: `.exe`）を起動してください。  
操作方法はソース実行版と同じです。

配布版での確認ポイント:

- セキュリティ警告が表示された場合は、配布元の案内に従って実行許可を行います
- 保存先に書き込み権限があるフォルダを選択してください

## よくあるトラブル

- 分割時に保存エラーが出る
  - 出力先PDFを他アプリで開いていないか確認
  - 書き込み権限のあるフォルダを選択
- 分割結果のファイル名が意図と異なる
  - 無効文字や予約語が自動整形される仕様です（詳細は取扱説明書）

## ドキュメント更新ルール

- UI操作やキー操作を変更したら、`docs/user-manual.md` と `docs/keyboard-shortcuts.md` を更新
- MVPの責務や処理フローを変更したら、`docs/developer-architecture.md` を更新
- 導線や起動手順を変更したら、この `README.md` を更新

### Markdown から HTML を再生成する

PowerShell で次を実行すると、`README.md` と `docs/*.md` を `github-markdown.css` を参照する HTML に変換できます。

```powershell
./scripts/build-docs-html.ps1
```
