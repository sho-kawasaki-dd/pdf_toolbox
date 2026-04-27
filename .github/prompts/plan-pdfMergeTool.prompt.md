## 実装プロンプト群: PDF結合機能のフェーズ分割

既存の PDF Toolbox リポジトリへ PDF 結合機能を追加するための親プロンプトです。規模が大きくなったため、実装を 4 フェーズへ分割しています。各フェーズは前段の成果物を前提にし、既存の split / compress 機能と同じ設計思想、責務分離、テスト方針に合わせて進めてください。

### 共通前提

- Python 3.13+
- GUI: PySide6
- PDF 操作: PyMuPDF（fitz）
- 既存アーキテクチャを踏襲すること
- コメント、Docstring、GUI 表示文言は日本語
- 変数名、関数名、クラス名は英語
- PEP 8 準拠
- すべての関数・メソッドに型ヒントを付けること
- GUI から直接 PyMuPDF を呼ばないこと
- model / presenter / view を分離すること
- merge 機能だけ別流儀にせず、既存の split / compress と同じ統合ポイントに載せること
- 非同期処理は既存との整合を優先して Thread + Queue + poll_results 方式で実装すること
- GUI 更新は必ずメインスレッド側で行うこと
- 処理中終了時は実際に停止できるよう、cancel_event または同等のキャンセル機構を持たせること

### 既存実装で必ず踏襲する参照先

- 画面遷移と終了制御: [presenter/app_coordinator.py](presenter/app_coordinator.py#L1)
- stacked widget と schedule / cancel_schedule: [view/main_window.py](view/main_window.py#L1)
- ホーム画面の機能カード: [view/home_view.py](view/home_view.py#L1)
- Presenter の基本パターン: [presenter/compress_presenter.py](presenter/compress_presenter.py#L1)
- バックグラウンド処理パターン: [model/compress/compression_processor.py](model/compress/compression_processor.py#L1)

### フェーズ一覧

1. [フェーズ1: 基盤と一覧操作](phase1-pdfMergeTool-foundation.prompt.md)
2. [フェーズ2: サムネイル表示](phase2-pdfMergeTool-thumbnails.prompt.md)
3. [フェーズ3: 結合実行とキャンセル](phase3-pdfMergeTool-mergeExecution.prompt.md)
4. [フェーズ4: テスト強化と仕上げ](phase4-pdfMergeTool-testsAndPolish.prompt.md)

### 推奨実行順

1. フェーズ1で merge 機能の骨格、画面遷移、一覧編集、保存先 UI を作る。
2. フェーズ2で PDF1ページ目のサムネイル表示とその非同期化・キャッシュを追加する。
3. フェーズ3で実際の PDF 結合、進捗、完了 / エラー通知、終了時キャンセルを実装する。
4. フェーズ4で不足テスト、回帰防止、UX の最終調整を行う。

### フェーズ境界ルール

- 後続フェーズの機能を前倒しで大量実装しないこと。
- 各フェーズ完了時点で、アプリ全体が壊れていない状態を維持すること。
- フェーズごとにその段階で必要なテストを追加し、最終フェーズで不足分を埋めること。
- サムネイル生成は view に直接書かず、将来の再利用を見据えた責務に切り出すこと。
- キャンセル可能な停止はフェーズ3で実装し、フェーズ1・2では API の受け皿だけ用意してよい。

### 最終的な必須到達点

- PDF ファイルのみ受け入れるドラッグ&ドロップ対応リスト
- 上へ / 下へボタンとリスト内ドラッグ&ドロップの両方による順序変更
- 選択ファイルの削除
- PDF1ページ目サムネイル表示
- 重複ファイル追加の防止
- 結合後 PDF の保存ファイルパス選択
- 結合実行
- 完了時 / エラー時のダイアログ通知
- 実行中終了時の警告とキャンセル付き終了
- 実行中の編集操作無効化
- model / presenter / view 各層のテスト追加
