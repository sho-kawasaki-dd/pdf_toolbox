## Plan: Merge/Extract Polling Race Fix

merge の初回 polling 起動を必ず 1 回保証し、その設計を extract にも横展開します。修正は presenter に限定し、model の worker や queue、UI 文言は変えず、即時完了ケースの回帰テストを追加して閉じます。計画は session memory に保存済みです。

**Steps**
1. merge の実行開始経路を修正する。対象は [presenter/merge_presenter.py](presenter/merge_presenter.py)。execute_merge から start_merge 直後に最初の poll を必ず予約できるようにし、通常時の再ポーリング条件とは分離する。
2. merge の polling helper を最小変更で拡張する。対象は [presenter/merge_presenter.py](presenter/merge_presenter.py)。_ensure_merge_polling に initial poll を強制できる引数を追加し、開始直後だけ使う。_poll_merge_results の finished、failure、cancelled 分岐は維持する。Step 1 に依存。
3. merge の回帰テストを追加する。対象は [tests/presenter/test_merge_presenter.py](tests/presenter/test_merge_presenter.py)。start_merge 内で即完了して is_merging が False に戻るケースでも、execute_merge 後の初回 poll で finished を拾って UI 解放と完了通知まで進むことを検証する。Step 1-2 に依存。
4. merge の helper 条件テストを足す。対象は [tests/presenter/test_merge_presenter.py](tests/presenter/test_merge_presenter.py)。initial poll 強制ありなら schedule され、強制なしなら idle 状態では schedule されないことを確認する。Step 2 に依存。
5. extract に同型修正を入れる。対象は [presenter/extract_presenter.py](presenter/extract_presenter.py)。execute_extract と _ensure_extract_polling に merge と同じ initial poll 強制の仕組みを入れる。_poll_extract_results の完了分岐は変更しない。Step 1-2 の方針確定後に着手。
6. extract の回帰テストを追加する。対象は [tests/presenter/test_extract_presenter.py](tests/presenter/test_extract_presenter.py)。start_extract 内で即完了して is_running が False に戻るケースでも、完了通知と session.finish_execution が通ることを検証する。Step 5 に依存。
7. extract の helper 条件テストを追加する。対象は [tests/presenter/test_extract_presenter.py](tests/presenter/test_extract_presenter.py)。initial poll 強制ありとなしで schedule 条件が分かれることを確認し、既存の execute 開始テストと整合を取る。Step 5 に依存。
8. 検証を行う。merge と extract の presenter テストを個別実行し、その後 presenter テスト一式を流して副作用を確認する。Step 3-7 に依存。
9. 今回の修正をリリースノートに記載する。内容は「PDF の結合と抽出で、処理完了の検知が失敗して UI が操作不能になるケースを修正しました。」程度で十分です。Step 8 に依存。リリースノートは [docs/release_notes.md](docs/release_notes.md) に記載します。version 1.0.2 のセクションに追記する形で、変更内容と影響範囲を簡潔にまとめます。

**Relevant files**
- [presenter/merge_presenter.py](presenter/merge_presenter.py)  execute_merge、_ensure_merge_polling、_poll_merge_results の主修正先
- [tests/presenter/test_merge_presenter.py](tests/presenter/test_merge_presenter.py)  merge の race 回帰テスト追加先
- [presenter/extract_presenter.py](presenter/extract_presenter.py)  execute_extract、_ensure_extract_polling、_poll_extract_results の横展開先
- [tests/presenter/test_extract_presenter.py](tests/presenter/test_extract_presenter.py)  extract の race 回帰テスト追加先
- [tests/view/test_main_window.py](tests/view/test_main_window.py)  schedule と cancel の既存テストパターン参照用
- [pyproject.toml](pyproject.toml)  pytest と pytest-qt 構成確認用

**Verification**
1. pytest tests/presenter/test_merge_presenter.py -v
2. pytest tests/presenter/test_extract_presenter.py -v
3. pytest tests/presenter/ -v
4. 可能なら実機で merge を短い PDF 1 から 2 件で実行し、完了後にツールバーと戻る操作が復帰することを確認する
5. 可能なら実機で extract の短時間ケースも確認し、現状の正常動作を維持していることを確認する

**Decisions**
- 修正対象は presenter に限定し、model 側の queue と worker は触らない
- merge と extract を今回のスコープに含め、compress と pdf_to_jpeg への横展開は今回は含めない
- UI 文言や progress 表示仕様は変えず、完了判定と UI 解放の確実性だけを直す
- extract は現状不具合が再現していなくても、merge と同型の race を持つため予防修正として同時対応する
