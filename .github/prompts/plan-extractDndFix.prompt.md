PDF抽出機能のDnD挙動を改修してください。対象は Source ペイン、Target ペイン、および両者の間のページDnDです。今回の目的は、DnDの受け口と送信元の実装を揃え、見かけ上 accept しているのに何も起きない状態をなくすことです。

現状の問題は次の3点です。

1. Sourceペインに外部からPDFをドラッグ&ドロップしても、実際には追加されない
2. Sourceペインから Target ペインへページをドラッグ&ドロップしても、Targetへページが追加されない
3. Targetペインに外部PDFをドラッグしたとき、受け付けそうに見えるが、ドロップしても何も起きない

改修方針は以下としてください。

1. Sourceペインへの外部PDFドロップ
Sourceペイン上での外部PDFドロップは、実際にユーザーがドロップする領域で正しく受理されるようにしてください。見えている Source 側のウィジェットがDnDイベントを受け、既存の Source追加処理へ中継する構造にしてください。ファイルの妥当性判定や Session 更新は Presenter 側に寄せ、View 側はイベント受理とシグナル発火に専念させてください。

2. Source→Target のページDnD
Sourceページ側にドラッグ開始実装を追加してください。現在選択されている Source ページ群を、既存の EXTRACT_PAGES_MIME を使って Target に渡せるようにしてください。単一ページだけでなく、複数選択時は選択中ページを順序付きでまとめてドラッグ対象にしてください。Target側の既存受信経路は活かしつつ、実際に Source から MIME が送られるようにしてください。

3. Targetへの外部PDFドロップは受け付けないようにしてください。見かけ上も受け付け不可が分かるようにしてください。見かけ上 accept しているだけで drop 後に無反応になる状態は解消してください。

4. Target の dropEvent 整理
Target側のドロップ処理は、少なくとも次の3種類を明確に分けて扱ってください。
内部並び替え
Source→Target のページ追加
外部PDF→Target のドロップ（受け付けない）
これらが混線しないように、条件分岐とシグナル責務を整理してください。

5. 実行中状態の整合
抽出処理の実行中は、既存仕様どおり Target の変更系DnDを無効のまま維持してください。必要であれば Source 側のドラッグ開始も抑止してください。実行中にDnDで状態変更できてしまわないようにしてください。

6. テスト
既存テストは dropEvent を直接呼ぶものが中心で、実際のDnD経路の不足を取りこぼしています。以下の観点を追加してください。
Sourceペインへの外部PDFドロップで Source追加シグナルまたは Presenter 経路が発火すること
Sourceで1ページ選択して Target にドラッグしたとき Target に追加されること
Sourceで複数ページ選択して Target にドラッグしたとき、同順で Target に追加されること
Targetに外部PDFをドラッグしたとき、見かけ上も受け付け不可であり、drop しても処理が走らないこと
Target内の内部並び替えDnDが従来どおり壊れていないこと
実行中は変更系DnDが無効であること

変更対象の中心は以下です。
- view/extract/extract_view.py
- presenter/extract_presenter.py
- tests/view/extract/test_extract_view.py
- tests/presenter/test_extract_presenter.py

参考にする既存パターンは以下です。
- view/merge/merge_view.py
- view/compress/compress_view.py

実装時の注意点は次のとおりです。
- ViewはDnDイベント受理とシグナル発火までに留める
- ファイル判定、Source追加、Target追加、Session更新は Presenter または Model に寄せる
- Source→Target のページ転送は EXTRACT_PAGES_MIME に統一する
- Target外部ドロップは accept せず、拒否状態が見た目でも分かるようにする
- 既存の Target内部並び替えは壊さない
- 最小変更で整合性を取り、不要な設計変更は避ける

完了条件は次のとおりです。
1. Sourceペインに外部PDFをドロップすると Source に追加される
2. Sourceから Target へページDnDすると Target に追加される
3. Targetに外部PDFをドラッグしたとき、見かけ上も受け付けず、drop しても処理されない
4. Target内部並び替えDnDが従来どおり機能する
5. 関連テストが追加され、通過する
