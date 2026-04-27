---
name: 'PDFフラット化 Phase 1 詳細実装計画'
description: 'PyMuPDF の bake を使う PDF フラット化モデル層の Phase 1 実装計画'
agent: 'agent'
---

# PDFフラット化 Phase 1 詳細実装計画

## 目的

PyMuPDF の bake を使って、PDF 内の注釈とウィジェットをコンテンツへ焼き付けるモデル層を追加する。  
Phase 1 の対象は、純粋な状態モデル、バックグラウンド実行プロセッサ、事前検出 API、単体テストまでとする。  
Presenter、View、ホーム画面統合、上書き確認 UI は Phase 2 以降に分離する。

## Phase 1 の到達点

- PDF / フォルダ入力を受け取れる flatten モデル層を追加する
- フォルダ入力では再帰的に PDF を列挙できる
- 出力先は常に元 PDF と同じフォルダの \_flattened.pdf とする
- 実行前に既存出力の衝突一覧を取得できる
- バックグラウンド処理で bake -> temp 保存 -> 置換まで完結できる
- 失敗系を個別メッセージで返せる
- キャンセルは 1 ファイル単位の安全停止で扱える
- Session / Processor の自動テストが追加される

## 実装方針

既存の compress 系と同じく、責務を Session と Processor に分離する。

- Session は純粋な状態と命名規則だけを持つ
- Processor は入力探索、事前検出、PyMuPDF 実行、スレッド、キュー通知だけを持つ
- Presenter が将来使うため、Phase 1 の時点で prepare_batch 相当の事前検出 API を持たせる
- 実行は逐次処理に限定し、並列化は Phase 1 では行わない

## 新規追加ファイル

- model/flatten/**init**.py
- model/flatten/flatten_session.py
- model/flatten/flatten_processor.py
- tests/model/flatten/test_flatten_session.py
- tests/model/flatten/test_flatten_processor.py

必要に応じて fixture 追加先:

- conftest.py

## 参考実装

- compression_session.py
- compression_processor.py
- merge_processor.py
- pdf_to_jpeg_processor.py
- pdf_processor.py
- test_compression_processor.py
- test_merge_processor.py

## 1. 公開データ契約を先に固定する

Phase 2 の Presenter が内部実装を知らなくて済むように、先に公開 API を固定する。

想定する公開型:

- FlattenSession
- FlattenProcessor
- FlattenCandidate
- FlattenJob
- FlattenConflict
- FlattenBatchPlan

役割は次の通り。

- FlattenCandidate: 再帰探索で見つかった 1 件の元 PDF
- FlattenJob: 実行対象 1 件と、その出力先パス
- FlattenConflict: 既存出力との衝突情報
- FlattenBatchPlan: 実行前に確定した jobs、conflicts、preflight_issues の集合

この構成にすると、Phase 2 の Presenter は「入力変更時または実行直前に prepare_batch を呼ぶ」「確認後に start_flatten を呼ぶ」だけで済む。

## 2. FlattenSession を実装する

model/flatten/flatten_session.py は純粋な状態コンテナにする。

### 持つ状態

- input_paths: list[str]
- total_items
- processed_items
- success_count
- failure_count
- skip_count

### 公開メソッド

- add_input(path: str)
- add_inputs(paths: list[str])
- remove_input(path: str) -> bool
- clear_inputs()
- begin_batch(total_items: int)
- record_success()
- record_failure()
- record_skip()
- progress_snapshot() -> dict[str, int]

### 出力パス関連メソッド

- build_output_path(source_path: str) -> str
- build_temp_output_path(output_path: str, token: str) -> str
- validate_windows_path_limit(path: str) -> None

### 命名規則

出力名は常に次で固定する。

- source.pdf -> source_flattened.pdf
- report.v2.pdf -> report.v2_flattened.pdf

連番による自動回避はしない。  
既存ファイルとの衝突は conflict として切り出し、Phase 2 の上書き確認へ渡す。

### temp ファイル命名

temp は同じフォルダに作成する。

形式:

- .{output_stem}.flattening-{token}.pdf

例:

- sample_flattened.pdf
- .sample_flattened.flattening-0123abcd....pdf

path 長判定は final path と temp path の両方で行う。  
事前検出では token 長が実運用と一致するよう、固定長ダミー文字列を使う。

## 3. データ構造を定義する

model/flatten/flatten_session.py か、必要なら分離した型定義で dataclass を置く。

### FlattenCandidate

最低限持つ項目:

- source_path
- source_label

source_label は将来 UI や結果メッセージにそのまま流せる文字列にする。

### FlattenJob

最低限持つ項目:

- candidate
- output_path
- allow_overwrite

allow_overwrite を持たせる理由は、Phase 2 でユーザーが承認した conflict だけ実行に回せるようにするため。

### FlattenConflict

最低限持つ項目:

- source_path
- output_path

### FlattenBatchPlan

最低限持つ項目:

- jobs
- conflicts
- preflight_issues

preflight_issues は、事前に確定できる skipped / failure を保持する。  
例:

- 入力パスが存在しない
- PDF 以外のファイル
- output path が長すぎる
- temp path が長すぎる

## 4. prepare_batch を実装する

model/flatten/flatten_processor.py に同期 API を置く。

想定シグネチャ:

- prepare_batch(session: FlattenSession) -> FlattenBatchPlan

### この API の責務

- 入力パスを走査する
- フォルダを再帰展開する
- PDF とフォルダだけを受け付ける
- 出力パスを計算する
- 既存出力との衝突を抽出する
- path-too-long を preflight failure にする
- 実行対象 job を確定する

### 探索ルール

- path が存在しない -> skipped
- path がフォルダ -> sorted(path.rglob("\*")) で再帰
- path がファイルかつ suffix が .pdf -> candidate 化
- path がファイルかつ .pdf 以外 -> skipped

Phase 1 では ZIP 対応は含めない。  
また、壊れた PDF や暗号化 PDF の判定は fitz.open が必要なので、prepare_batch ではなく実行時に扱う。

### conflict 判定

Session の build_output_path で出力先を決め、すでに存在していれば conflict に振り分ける。  
自動リネームは行わない。

## 5. FlattenProcessor の非同期実行を実装する

model/flatten/flatten_processor.py にバックグラウンド worker を実装する。

想定する公開 API:

- start_flatten(session: FlattenSession, plan: FlattenBatchPlan)
- request_cancel()
- poll_results()

内部状態:

- is_running
- result_queue
- \_cancel_event

### 実行シーケンス

1. queue を drain
2. cancel event を clear
3. worker thread を開始
4. preflight_issues を順に replay
5. jobs を逐次処理
6. finished / failure / cancelled を返す

### 逐次処理にする理由

- キャンセル境界を 1 ファイル完了単位に固定しやすい
- temp 保存と os.replace の競合を最小化できる
- Phase 1 の実装とテストが単純になる
- UI 要件上、まずは安全性の方が重要

## 6. 1 ジョブの flatten 手順を分解する

Processor 内にヘルパーを切る。

想定ヘルパー:

- \_flatten_worker(...)
- \_flatten_job(job: FlattenJob) -> dict[str, object]
- \_open_source_pdf(path: Path) -> fitz.Document
- \_raise_if_cancelled()
- \_cleanup_temp_output(temp_output: Path)

### \_flatten_job の処理順

1. source_path を open
2. open 失敗時は不正 PDF 扱い
3. needs_pass または is_encrypted を確認
4. page_count <= 0 を確認
5. bake 実行
6. temp へ save
7. cancel 確認
8. os.replace で本番出力へ置換
9. success event を返す

### 例外分類

- fitz.FileDataError -> 不正なPDF
- RuntimeError -> PDFを開けませんでした
- needs_pass / is_encrypted -> 暗号化されたPDFのため処理できません
- PermissionError -> ファイルが他のアプリで開かれています
- OSError -> 保存失敗
- その他 -> flatten 実行失敗

## 7. キャンセル仕様を固定する

キャンセルは merge_processor.py と同じ協調キャンセルに寄せる。

### 仕様

- request_cancel は event を立てるだけ
- 強制停止はしない
- 現在処理中の 1 ファイルが安全に終わった境界で止める
- 未処理ジョブは failure へ変換しない
- temp は必ず cleanup する
- cancelled イベントは 1 回だけ返す

### チェックポイント

- 各ジョブ開始前
- bake 後
- save 後
- os.replace 前

## 8. キューイベントの形を固定する

Presenter が既存パターンを流用しやすいよう、イベント形状を既存機能に寄せる。

### progress

返すキー:

- total_items
- processed_items
- success_count
- failure_count
- skip_count
- progress_percent

### success

返すキー:

- type
- item
- output_path

### failure

返すキー:

- type
- item
- message

### skipped

返すキー:

- type
- item
- reason

### finished

返すキー:

- type
- total_items
- processed_items
- success_count
- failure_count
- skip_count
- progress_percent

### cancelled

返すキー:

- type
- total_items
- processed_items
- success_count
- failure_count
- skip_count
- progress_percent
- message

## 9. テスト計画

### Session テスト

test_flatten_session.py で確認する項目:

- input の追加、削除、クリア
- build_output_path が \_flattened.pdf を返す
- build_temp_output_path の形式
- progress_snapshot の集計
- path 長 260 文字制限の判定
- begin_batch がカウンタを初期化する

### Processor テスト

test_flatten_processor.py で確認する項目:

- prepare_batch がフォルダを再帰探索する
- missing path を skipped にする
- non-PDF を skipped にする
- 既存 output を conflict に分離する
- output/temp の path-too-long を preflight failure にする
- 正常 PDF を flatten して output を作る
- 壊れた PDF を failure にする
- 暗号化 PDF を failure にする
- PermissionError を専用文言で返す
- cancel 後に partial output を残さない
- reentry を無視する
- progress が件数に応じて流れる
- temp file が失敗時に cleanup される

### fixture 追加

conftest.py に追加候補:

- annotated_pdf
- form_pdf
- encrypted_pdf

Phase 1 の自動テストでは、注釈の視覚結果そのものよりも以下を優先して確認する。

- bake 後の PDF が保存できる
- 再オープンできる
- page_count が維持される

## 10. 完了条件

Phase 1 完了の定義は次の通り。

- flatten 用 Session と Processor が追加されている
- prepare_batch で conflict と preflight issue を取得できる
- bake 実行から temp 保存、置換まで動作する
- 暗号化 PDF を常に failure にできる
- final path と temp path の両方で 260 文字制限を検出できる
- cancel と temp cleanup がテストで保証される
- flatten 用の新規テストが通る

## 確定した意思決定

- 既存出力 conflict は Phase 1 で事前検出 API を持たせる
- 暗号化 PDF は needs_pass または is_encrypted のどちらかが立てば常に failure にする
- Windows パス長制限は classic MAX_PATH 前提で 260 文字以上なら failure にする
- 出力命名は常に \_flattened.pdf 固定とする
- 自動連番による衝突回避は行わない
- 実行は逐次処理とする
- キャンセル境界は 1 ファイル完了後の安全停止とする

## 検証コマンド

1. `pytest tests/model/flatten/test_flatten_session.py tests/model/flatten/test_flatten_processor.py`
2. `pytest test_compression_processor.py test_merge_processor.py tests/model/pdf_to_jpeg/test_pdf_to_jpeg_processor.py`

必要なら次に、これをそのまま issue 分解しやすい粒度の「実装タスクリスト形式」に変換します。
