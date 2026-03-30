# PDF Toolbox (PySide6)

PDF を扱う日常作業をまとめて支援する Windows 向けデスクトップアプリケーションです。
`main.py` から起動し、MVP（Model / View / Presenter）構成で実装されています。

## このアプリでできること

- PDF 分割: 1 つの PDF をセクション単位で複数ファイルへ分割
- PDF 結合: 複数 PDF を並び替えて 1 つの PDF に結合
- PDF 抽出: 複数 PDF から任意ページだけを集めて新しい PDF を作成
- PDF 圧縮: PDF / フォルダ / ZIP を対象にした一括圧縮
- PDF → JPEG: 単一 PDF の全ページを JPEG として書き出し

用語の違い:

- 分割: 1 つの PDF を区切って複数ファイルにする機能
- 抽出: 複数 PDF から必要なページだけを集めて 1 つの PDF にする機能

## ドキュメント

- 利用者向け取扱説明書: [docs/user-manual.md](docs/user-manual.md)
- 分割画面ショートカット一覧: [docs/keyboard-shortcuts.md](docs/keyboard-shortcuts.md)
- 開発者向け設計ドキュメント: [docs/developer-architecture.md](docs/developer-architecture.md)

読み進め方の目安:

- はじめて使う: `docs/user-manual.md`
- 分割画面のキー操作を確認したい: `docs/keyboard-shortcuts.md`
- 改修や保守を始める: `docs/developer-architecture.md`

## ホーム画面の構成

起動後のホーム画面には、次の 5 つの機能カードが表示されます。

- PDF 分割
- PDF 結合
- PDF 抽出
- PDF 圧縮
- PDF → JPEG

起動時にはスプラッシュ画面が表示され、最小 2 秒表示された後にメインウィンドウへ切り替わります。

## 最短で起動する

1. Python を用意します。
   `pyproject.toml` の設定は `>=3.14` です。
2. 任意の仮想環境を有効化します。
3. 依存関係をインストールします。

   ```bash
   pip install -U pyside6 pillow pymupdf pikepdf
   ```

4. アプリを起動します。

   ```bash
   python main.py
   ```

5. 起動確認を行います。
   - スプラッシュ画面が表示される
   - ホーム画面に 5 つの機能カードが並ぶ
   - 各カードから対応する画面へ遷移できる

## 機能の概要

### PDF 分割

- 単一 PDF をページ境界で区切って複数ファイルへ保存します
- 分割点の追加・削除、セクションごとのファイル名編集に対応します
- プレビュー、ページ移動、ズーム、キーボード操作を備えています

### PDF 結合

- 複数 PDF を一覧へ追加して順番を並び替えられます
- 結合前にサムネイルで内容を確認できます
- 出力先 PDF を指定して 1 つのファイルへまとめます

### PDF 抽出

- 複数 PDF を Source に追加し、必要ページだけを Target に集めます
- クリック、Ctrl/Shift を使った複数選択、ダブルクリック、ドラッグ＆ドロップに対応します
- Target 側で順番を並び替え、1 つの PDF として保存します

### PDF 圧縮

- 入力として PDF、フォルダ、ZIP を受け付けます
- 圧縮モードは非可逆、可逆、両方の 3 種類です
- 非可逆圧縮では、PDF 内の透過付き PNG や soft mask 付き画像は透過を保ったまま PNG 経路で再圧縮します
- PNG 量子化では、`pngquant` が利用可能な環境ではそれを優先し、利用できない場合や実行失敗時は Pillow フォールバックで処理を継続します
- `pngquant` の呼び出しは shell を介さず、解決済み実行パス・専用一時ディレクトリ・タイムアウト付きで実行されます
- 複数入力をまとめて処理し、成功・失敗・スキップ件数を集計表示します

### PDF → JPEG

- 入力は単一 PDF のみです
- 全ページを `PDF名_001.jpg` 形式で連番出力します
- 保存先は `保存先/PDF名/` サブフォルダです
- 透明要素を含むページは白背景に合成して保存します

## Windows で実行ファイルを作成する

1. 仮想環境を有効化し、必要パッケージを入れます。

   ```bash
   pip install -U pyside6 pillow pymupdf pikepdf pyinstaller
   ```

2. PowerShell からビルドスクリプトを実行します。

   ```powershell
   .\scripts\build-exe.ps1
   ```

3. 生成物を確認します。
   - 実行ファイルは `dist/` 配下に出力されます
   - `pdf_toolbox.spec`、`assets/`、`fonts/` などの補助ファイルを使います

4. 動作確認を行います。
   - ホーム画面が表示される
   - 5 機能へ遷移できる
   - 代表機能として、分割または PDF→JPEG を最後まで実行できる

補足:

- 初回起動時は SmartScreen 警告が表示される場合があります
- onedir 形式は onefile より起動時の切り分けがしやすい構成です

## 実行ファイル配布版を使う場合

配布された `.exe` を起動してください。
基本的な操作フローはソース実行版と同じです。

確認ポイント:

- 保存先として書き込み権限のあるフォルダを選ぶ
- 処理中は対象画面の入力変更やホーム遷移が制限される場合がある
- PDF → JPEG では保存先の下に PDF 名のサブフォルダが自動生成される

## よくあるトラブル

- 実行ボタンが押せない
  - 入力ファイルや保存先が不足しています
  - 画面ごとの必須項目を設定してください
- 上書き確認が出る
  - 既存の出力ファイルと名前が重なっています
  - 内容を確認したうえで上書きするか、別の保存先を選んでください
- 実行中にホームへ戻れない
  - 実行中のジョブ保護のため、各 Presenter が遷移を制御しています
- JPEG の背景が白になる
  - 透明要素を含むページを白背景に合成して保存する仕様です

## ドキュメント更新ルール

- UI 操作やボタン名を変えたら `docs/user-manual.md` を更新する
- 分割画面のキー操作を変えたら `docs/keyboard-shortcuts.md` を更新する
- MVP の責務、処理フロー、画面遷移を変えたら `docs/developer-architecture.md` を更新する
- 起動手順、配布方法、文書導線を変えたらこの `README.md` を更新する

## Markdown から HTML を再生成する

PowerShell で次を実行すると、`README.md` と `docs/*.md` から HTML を再生成できます。

```powershell
./scripts/build-docs-html.ps1
```
