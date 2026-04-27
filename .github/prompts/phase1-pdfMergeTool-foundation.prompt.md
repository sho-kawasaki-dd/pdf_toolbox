## フェーズ1: PDF結合機能の基盤と一覧操作

既存の PDF Toolbox リポジトリへ PDF 結合機能の骨格を追加してください。このフェーズでは、画面遷移、一覧管理、入力操作、保存先 UI、MVP の責務分離の土台を完成させます。実際の PDF 結合処理とサムネイル生成はまだ本実装しなくてかまいませんが、後続フェーズで差し込みやすい構造にしてください。

### このフェーズの目的

- merge 機能を既存アプリへ自然に統合する
- PDF 入力一覧の追加、削除、順序変更を完成させる
- 保存先選択 UI を実装する
- model / presenter / view の責務分離を固める

### このフェーズで実装する範囲

1. merge 機能の新規モジュールを追加する
2. HomeView の merge カードを有効化する
3. MainWindow の stacked widget に merge_view を追加する
4. AppCoordinator に merge presenter を登録し、show_merge 相当の遷移を追加する
5. MergeSession を作成し、以下の状態を保持できるようにする
6. 入力 PDF パス一覧
7. 現在の並び順
8. 選択中アイテム
9. 保存先ファイルパス
10. 実行中フラグの受け皿
11. キャンセル要求フラグの受け皿
12. MergeView を作成し、以下の UI を用意する
13. PDF リスト
14. PDF を追加ボタン
15. 削除ボタン
16. 上へボタン
17. 下へボタン
18. 保存先を選択ボタン
19. 結合実行ボタン
20. 必要最小限の進捗表示領域
21. PDF ファイルのみ受け入れるドラッグ&ドロップを実装する
22. リスト内ドラッグ&ドロップによる並び替えを実装する
23. 上へ / 下へボタンによる並び替えを実装する
24. 選択アイテム削除を実装する
25. 重複ファイル追加を防止する
26. PDF 以外の入力は無視し、必要なら日本語メッセージで知らせる

### このフェーズでは仮実装でよいもの

- 結合実行処理の本体
- サムネイル生成処理の本体
- 完了 / エラー時の最終ダイアログ文言の詳細化
- 終了時キャンセルの実処理

### 設計ルール

- view は PyMuPDF を使わないこと
- presenter は入力検証と UI 更新の責務を持つこと
- session は一覧操作をテストしやすい純粋ロジックとして作ること
- 後続フェーズでサムネイルや実処理を差し込めるよう、リストアイテムはサムネイル表示領域を持てる設計にすること
- 後続フェーズで processor を導入しやすいよう、presenter に execute_merge、on_closing、is_busy、has_active_session の骨格を用意すること

### 想定ファイル

新規追加候補:

- model/merge/**init**.py
- model/merge/merge_session.py
- presenter/merge_presenter.py
- view/merge/**init**.py
- view/merge/merge_view.py

既存変更候補:

- presenter/app_coordinator.py
- view/main_window.py
- view/home_view.py
- model/**init**.py
- presenter/**init**.py

### このフェーズの完了条件

- ホーム画面から PDF 結合画面へ遷移できる
- PDF の追加、削除、順序変更、保存先指定ができる
- DnD は PDF のみ受け入れる
- 重複入力を防止できる
- UI とロジックが分離されている
- merge の基礎テストを追加している

### このフェーズで追加するテスト

- tests/model/merge/test_merge_session.py
- tests/presenter/test_merge_presenter.py
- tests/view/merge/test_merge_view.py

最低限検証する項目:

- 入力追加
- 重複除外
- 順序変更
- 削除
- 保存先設定
- DnD の受け入れ制御
- 実行前バリデーションの骨格
