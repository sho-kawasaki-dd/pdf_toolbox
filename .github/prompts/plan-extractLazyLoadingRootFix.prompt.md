PDF抽出機能の根本改善を実装してください。対象は Source ペインと Target ペインのサムネイル表示です。現状は PDF追加時に全ページのサムネイルを一括要求しており、cache_limit=256 の LRU キャッシュと衝突して、500ページ級PDFで末尾側のサムネイルだけが残り、前半ページが表示されません。さらに、サムネイル結果が返るたびに Source セクションと Target リストを丸ごと再構築しているため、GUI が極端に重くなっています。

この修正は Phase ごとに分けて進めてください。各 Phase は、完了条件が明確で、次の Phase に進む前にテストまたは動作確認ができる粒度にしてください。さらに、各 Phase の中では issue 粒度まで分解し、各 issue ごとに変更対象、依存関係、確認項目が分かるようにしてください。

Phase 1: 現状整理と責務の分離
目的:
全件先読みと全UI再構築の責務を分離し、以降の改善を入れやすい構造にする。

Issue 1.1: 全件先読み経路の隔離
変更対象:
1. presenter/extract_presenter.py

タスク:
1. PDF追加時に全ページ request_thumbnails を発行している経路を特定してください。
2. その経路を、後続 Phase で可視範囲要求へ差し替えられる専用メソッドまたは専用責務に隔離してください。

依存関係:
1. なし

確認項目:
1. 全件要求の呼び出し箇所が一箇所または明確な責務単位にまとまっていること。

Issue 1.2: サムネイル要求トリガーの整理
変更対象:
1. presenter/extract_presenter.py
2. view/extract/extract_view.py

タスク:
1. Source と Target のサムネイル要求タイミングを Presenter 側で制御できるように、トリガー入口を整理してください。
2. 初回表示、スクロール、ズーム変更、Target追加後などのイベントから、Presenter が要求制御へ入れる構造を作ってください。

依存関係:
1. Issue 1.1

確認項目:
1. サムネイル要求の開始点が View 側ではなく Presenter 側に集約されていること。

Issue 1.3: 全再構築経路の分離
変更対象:
1. view/extract/extract_view.py

タスク:
1. update_ui が Source と Target を丸ごと再構築している箇所を分離してください。
2. 将来的に差分更新へ置き換えやすいよう、Source 更新処理と Target 更新処理を独立させてください。

依存関係:
1. なし

確認項目:
1. Source 全再構築と Target 全再構築の責務が独立していること。

Issue 1.4: Loader 契約の明確化
変更対象:
1. model/extract/page_thumbnail_loader.py

タスク:
1. cache と pending の役割を再確認してください。
2. 可視ページ再訪時に再要求できる前提を崩さないことを確認してください。
3. 必要なら再要求前提の振る舞いをコメント、命名、補助メソッドで明確にしてください。

依存関係:
1. なし

確認項目:
1. キャッシュ退避後でも再要求可能な前提がコード上で追えること。

完了条件:
1. PDF追加時の全件サムネイル要求を前提にしない構造になっていること。
2. Source と Target のサムネイル要求責務が Presenter に集約されていること。

Phase 2: 可視範囲ベースの Lazy Loading
目的:
表示中とその周辺だけを読み込む、本来の Lazy Loading を実装する。

Issue 2.1: Source 可視範囲取得 API の追加
変更対象:
1. view/extract/extract_view.py
2. presenter/extract_presenter.py

タスク:
1. Presenter が Source の可視ページまたは可視セクション範囲を取得できるようにしてください。
2. 必要なら View に可視範囲取得 API を追加してください。

依存関係:
1. Issue 1.2

確認項目:
1. Presenter が Source の現在表示範囲を取得できること。

Issue 2.2: Target 可視範囲取得 API の追加
変更対象:
1. view/extract/extract_view.py
2. presenter/extract_presenter.py

タスク:
1. Presenter が Target の可視行範囲を取得できるようにしてください。

依存関係:
1. Issue 1.2

確認項目:
1. Presenter が Target の現在表示範囲を取得できること。

Issue 2.3: Visible-only request の実装
変更対象:
1. presenter/extract_presenter.py

タスク:
1. Source と Target の両方で、現在可視の範囲と前後バッファだけを request_thumbnails するようにしてください。
2. visible かつ not cached かつ not pending のページだけを要求対象にしてください。

依存関係:
1. Issue 2.1
2. Issue 2.2
3. Issue 1.4

確認項目:
1. 500ページ級PDF追加直後に全ページ request が走らないこと。

Issue 2.4: 再評価トリガーの接続
変更対象:
1. presenter/extract_presenter.py
2. view/extract/extract_view.py

タスク:
1. スクロール、初回表示、ズーム変更、Target追加後など、表示内容が変わるタイミングで可視範囲を再評価してください。

依存関係:
1. Issue 2.3

確認項目:
1. 先頭、中盤、末尾への移動時に必要なページだけが順次要求されること。

完了条件:
1. 500ページ級PDFを追加しても、初回で全ページ request が走らないこと。
2. 先頭、中盤、末尾のどこに移動しても、可視化されたページだけが順次表示されること。

Phase 3: Loader とキャッシュの安定化
目的:
LRUキャッシュ退避があっても、表示欠落が残らないようにする。

Issue 3.1: レンダリングフロー維持の明示
変更対象:
1. model/extract/page_thumbnail_loader.py

タスク:
1. PyMuPDF -> Pillow 縮小フローを維持してください。
2. Pillow の resize ごとに PDF を再オープンしないことを確認してください。

依存関係:
1. Issue 1.4

確認項目:
1. レンダリングフローが従来どおりであること。

Issue 3.2: キャッシュ退避後の再要求保証
変更対象:
1. model/extract/page_thumbnail_loader.py
2. presenter/extract_presenter.py

タスク:
1. キャッシュから退避したページが再訪時に再取得されることを保証してください。
2. 再取得時に表示欠落が残らないようにしてください。

依存関係:
1. Issue 2.3

確認項目:
1. 先頭へ戻ったときに前半ページが再表示されること。

Issue 3.3: pending/cache 遷移の整合性確認
変更対象:
1. model/extract/page_thumbnail_loader.py

タスク:
1. pending と cache の遷移で、再要求漏れや二重要求が起きないことを確認してください。
2. 必要なら cache_limit を調整可能にしてください。ただし根本解決は可視範囲要求で行ってください。

依存関係:
1. Issue 3.2

確認項目:
1. pending の取り残しで表示が止まらないこと。
2. 同じページへの重複要求が過剰に発生しないこと。

完了条件:
1. キャッシュ退避後に同じページへ戻っても、サムネイルが再表示されること。
2. 二重要求や pending の取り残しで表示が止まらないこと。

Phase 4: View の差分更新
目的:
サムネイル結果が返るたびに全Widgetを作り直す構造をやめ、GUI負荷を大きく下げる。

Issue 4.1: Source 差分更新 API の導入
変更対象:
1. view/extract/extract_view.py

タスク:
1. update_ui で Source セクション全破棄をやめてください。
2. 既存 Source widget を再利用できる更新 API を導入してください。

依存関係:
1. Issue 1.3

確認項目:
1. Source 全体の再生成を前提にしない更新経路があること。

Issue 4.2: Source サムネイル差分反映
変更対象:
1. view/extract/extract_view.py
2. presenter/extract_presenter.py

タスク:
1. サムネイル到着ページだけ set_thumbnail で更新してください。
2. ポーリング結果から、変更があったページだけを更新対象にしてください。

依存関係:
1. Issue 4.1
2. Issue 2.3

確認項目:
1. サムネイル1件到着でSource全体が更新されないこと。

Issue 4.3: Target 差分更新 API の導入
変更対象:
1. view/extract/extract_view.py

タスク:
1. Target リストの全 clear と全 row 再生成をやめてください。
2. 既存 item と row を再利用する差分更新 API を導入してください。

依存関係:
1. Issue 1.3

確認項目:
1. Target の全行再生成を前提にしないこと。

Issue 4.4: 状態保持の保証
変更対象:
1. view/extract/extract_view.py
2. presenter/extract_presenter.py

タスク:
1. 選択状態、並べ替え状態、フォーカス状態が全再構築で消えないようにしてください。

依存関係:
1. Issue 4.2
2. Issue 4.3

確認項目:
1. 差分更新中も選択やフォーカスが保持されること。

完了条件:
1. サムネイル結果が返るたびに Source/Target 全体が再構築されないこと。
2. 大量ページ時でも、スクロールや選択が極端に重くならないこと。

Phase 5: レイアウトと大量ページ性能の改善
目的:
大量ページでの再配置コストを抑え、実用的な操作性にする。

Issue 5.1: Source レイアウト再構築頻度の削減
変更対象:
1. view/extract/extract_view.py

タスク:
1. _FlowLayout の addWidget ごとの全再構築を避けてください。
2. 必要なら初回構築時のバッチ配置または再配置タイミング制御を入れてください。

依存関係:
1. Issue 4.1

確認項目:
1. 大量ページ追加時のレイアウト再計算回数が抑えられていること。

Issue 5.2: Target 大量行性能の改善
変更対象:
1. view/extract/extract_view.py

タスク:
1. Target 側も数百行での描画更新コストが実用範囲に収まるようにしてください。

依存関係:
1. Issue 4.3

確認項目:
1. Target でスクロール、選択、並べ替えが極端に重くならないこと。

Issue 5.3: 将来の model/view 化に向けた境界整理
変更対象:
1. presenter/extract_presenter.py
2. view/extract/extract_view.py

タスク:
1. 今回のスコープ内で十分な性能が出ない場合に備え、将来的な model/view + delegate 化を見据えた境界を残してください。

依存関係:
1. Issue 5.1
2. Issue 5.2

確認項目:
1. View とデータ更新責務の境界が明確であること。

完了条件:
1. 500ページ級PDFで、Source と Target のスクロールが実用速度を維持すること。
2. ズーム変更時の再描画コストが過度に増えないこと。

Phase 6: テストと回帰防止
目的:
今回の不具合と性能回帰をテストで固定する。

Issue 6.1: Presenter の visible-only request テスト
変更対象:
1. tests/presenter/test_extract_presenter.py

タスク:
1. visible-only request のテストを追加または更新してください。
2. 初回表示で全ページ要求しないことを固定してください。

依存関係:
1. Issue 2.3
2. Issue 2.4

確認項目:
1. 可視範囲ベース要求がテストで固定されていること。

Issue 6.2: Loader の再要求テスト
変更対象:
1. tests/model/extract/test_page_thumbnail_loader.py

タスク:
1. cache eviction 後の再要求テストを追加または更新してください。
2. pending と cache の整合性テストを必要に応じて追加してください。

依存関係:
1. Issue 3.2
2. Issue 3.3

確認項目:
1. キャッシュ退避後の再表示がテストで固定されていること。

Issue 6.3: View の差分更新テスト
変更対象:
1. tests/view/extract/test_extract_view.py

タスク:
1. 差分更新、ズーム、表示維持のテストを追加または更新してください。
2. 全再構築に戻っていないことを確認できるテストを追加してください。

依存関係:
1. Issue 4.1
2. Issue 4.2
3. Issue 4.3
4. Issue 4.4

確認項目:
1. 差分更新の挙動がテストで固定されていること。

Issue 6.4: 既存操作の回帰確認
変更対象:
1. tests/presenter/test_extract_presenter.py
2. tests/view/extract/test_extract_view.py

タスク:
1. 既存の選択、複数選択、ダブルクリックで Target 追加、並べ替え、ズーム操作が壊れていないことを確認してください。

依存関係:
1. Issue 6.1
2. Issue 6.3

確認項目:
1. 主要操作の既存挙動が維持されていること。

完了条件:
1. 今回追加したテストが通ること。
2. 既存の主要テストが落ちないこと。

必須要件:
1. 500ページ級PDFで、先頭、中盤、末尾のどこへスクロールしても必要時にサムネイルが表示されること。
2. キャッシュから退避したページも、再度可視になれば再要求されて表示されること。
3. Target に数百ページあっても、スクロールや選択や並べ替えが極端に重くならないこと。
4. 既存の選択、複数選択、ダブルクリックで Target 追加、並べ替え、ズーム操作を壊さないこと。

変更対象の中心:
1. presenter/extract_presenter.py
2. view/extract/extract_view.py
3. model/extract/page_thumbnail_loader.py

進め方:
1. Phase は順番に進めてください。
2. 各 Phase の中では Issue 単位で完了させ、必要なら小さなコミット相当の変更として扱ってください。
3. 各 Issue 完了時に、変更対象、確認結果、次の依存 Issue を簡潔にまとめてください。

最後に、各 Phase で何を変えたか、どの設計変更で何が改善したか、残る制約は何かを簡潔にまとめてください。
