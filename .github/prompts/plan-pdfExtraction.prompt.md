# Plan: PDF抽出機能の実装

「PDF並び替え」(reorder) を「PDF抽出」(extract) に完全差し替え。左右分割ペイン UI で、Source（複数PDFのページサムネイル一覧）から Target（抽出先・並べ替え可）へページを DnD/ボタンで移動し、単一PDFとして出力する。ページレベル Lazy Loading サムネイルと 50%–200% 独立ズーム（Source/Target 別々）を実装。

---

## 確定した要件

| 項目                 | 決定                                                |
| -------------------- | --------------------------------------------------- |
| 内部ID               | `extract`（reorder を完全置換）                     |
| Source表示           | ファイル別セクション＋ページサムネイルグリッド      |
| Sourceセクション移動 | Ctrl+PageUp/Down                                    |
| PDF追加              | ボタン + 外部DnD                                    |
| PDF削除              | PDF単位（セクション単位）                           |
| ページ選択           | 複数選択対応（Ctrl+Click, Shift+Click）             |
| Target並び替え       | DnD + ↑↓ボタン                                      |
| Target削除           | 選択削除 + 全クリア                                 |
| 同一ページ重複       | 許可                                                |
| 出力形式             | 単一PDF                                             |
| サムネイル基準       | 128px = 100% (pillowでリサイズしてメモリに取り込み) |
| ズーム               | 50%–200%（25%刻み）、Source/Targetを別々に制御      |
| Lazy Loading         | ページ単位で遅延読み込み                            |

---

## Phase 1: 基盤 — ID差し替え・ルーティング・空のMVPスケルトン

1. **FEATURES タプルの ID 変更** — `view/home_view.py` の `("reorder", ...)` → `("extract", ...)`
2. **AppCoordinator 配線** — `presenter/app_coordinator.py`: `FEATURE_LABELS` 差し替え、`_on_feature_selected()` に `"extract"` 分岐、`ExtractPresenter` 生成・保持、戻り/終了ガード追加
3. **MainWindow スタック追加** — `view/main_window.py`: `ExtractView` を `QStackedWidget` 登録、`show_extract()` 追加、ショートカット管理更新
4. **空の Model スケルトン** — `model/extract/` に `__init__.py`, `extract_session.py`, `extract_processor.py`, `page_thumbnail_loader.py`
5. **空の Presenter スケルトン** — `presenter/extract_presenter.py`（最小限 `is_busy()`, `has_active_session()` のみ）
6. **空の View スケルトン** — `view/extract/` に `__init__.py`, `extract_view.py`（プレースホルダー）
7. **`__init__.py` エクスポート更新** — `model/__init__.py`, `presenter/__init__.py`

**検証**: アプリ起動 → 「PDF抽出」カードクリック → プレースホルダー表示 → ホーム戻り → 既存4機能正常

---

## Phase 2: Model — ExtractSession + PageThumbnailLoader

8. **`ExtractSession`** — データモデル: `SourceDocument`(path, page_count, id), `SourcePageRef`(doc_id, page_index), `TargetPageEntry`(id, source_ref)。Source操作（追加/削除/選択）、Target操作（追加/削除/移動/並替/クリア）、ズーム(`source_zoom_percent` / `target_zoom_percent` の2値、各50–200, 25刻み)、実行制御。パス正規化は `MergeSession` パターン踏襲
9. **`PageThumbnailLoader`** — `ThumbnailLoader` をページ単位に拡張。キャッシュキー `(path, page_index)`、LRU 256エントリ、ワーカースレッド、result_queue、128px基準PNG出力。`request_thumbnails(list[tuple[str, int]])` / `get_cached()` / `is_loading`

**検証**: `pytest tests/model/extract/test_extract_session.py tests/model/extract/test_page_thumbnail_loader.py`

---

## Phase 3: Model — ExtractProcessor

10. **`ExtractProcessor`** — `MergeProcessor` と同パターン（デーモンスレッド + result_queue + cancel_event）。pikepdf で各ソースPDF→ターゲット順にページ追加→アトミック書き込み。進捗/完了/失敗/キャンセル メッセージ

**検証**: `pytest tests/model/extract/test_extract_processor.py`

---

## Phase 4: View — ExtractView（二分割ペイン）

11. **レイアウト構造**:

    ```
    ExtractView (QVBoxLayout)
    ├── Header (← ホーム + "PDF 抽出")
    └── QSplitter (horizontal, 5:5)
        ├── Source Panel
        │   ├── btn_add_pdf + btn_remove_pdf
        │   ├── zoom_controls (btn_zoom_in + btn_zoom_out + btn_zoom_reset)
        │   └── QScrollArea → ファイル別セクション → PageThumbnailWidget グリッド
        └── Target Panel
            ├── btn_extract (→) + btn_remove + btn_clear + btn_move_up/down
            ├── target_list (QListWidget, DnD対応)
            ├── zoom_controls (btn_zoom_in + btn_zoom_out + btn_zoom_reset)
            └── Output (出力先 + btn_execute)
    ```

12. **`PageThumbnailWidget`** — サムネイル画像(128px×zoom%) + ページ番号。選択ハイライト(青枠)、Ctrl+Click/Shift+Click、ダブルクリック即追加
13. **`TargetPageList`** (QListWidget) — `MergeInputList` パターン踏襲。InternalMove DnD + Source→Target受け入れ（カスタムMIME `application/x-pdf-extract-pages`）
14. **`ExtractUiState`** — source_sections, target_items, zoom, ボタンフラグ, progress, is_running

15. **キーバインド**:

| キー               | 操作                                    |
| ------------------ | --------------------------------------- |
| Ctrl+PageUp / Down | Source: 前/次のファイルセクションへ移動 |
| Enter / →          | 選択ページを Target へ追加              |
| Delete             | Target: 選択削除 / Source: PDF削除      |
| Ctrl+A             | Sourceセクション全選択 / Target全選択   |
| Ctrl+Shift+A       | Source全ページ選択                      |
| ↑ / ↓              | Target: 選択を上/下に移動               |
| + / −              | ズームイン / アウト                     |
| Ctrl+0             | ズーム100%リセット                      |

**検証**: 手動 — 2ペイン表示、ズーム動作、プレースホルダーサムネイル

---

## Phase 5: Presenter — ExtractPresenter

16. **`ExtractPresenter`** — Session/Processor/PageThumbnailLoader を統合。PDF追加(ダイアログ+DnD)、Source選択、Target操作、ズーム、出力ダイアログ、実行+ポーリング(100ms)、Lazy Loading制御（スクロール位置→可視ページのみリクエスト）。`_build_ui_state()` → `view.update_ui()` パターン

**検証**: `pytest tests/presenter/test_extract_presenter.py` + 手動統合テスト

---

## Phase 6: テスト

17. テストファイル群を `tests/model/extract/`, `tests/presenter/`, `tests/view/extract/` に作成。既存テストパターン（mock view + UIState検証）に準拠

**検証**: `pytest tests/` 全テストグリーン + 統合テスト（複数PDF 50+ページ→抽出→並替→出力）

---

## Relevant Files

**変更**: `view/home_view.py`, `presenter/app_coordinator.py`, `view/main_window.py`, `model/__init__.py`, `presenter/__init__.py`

**参考テンプレート**: `model/merge/merge_session.py` (状態管理), `model/merge/merge_processor.py` (スレッド+Queue), `model/merge/thumbnail_loader.py` (LRUキャッシュ・Lazy Loading), `presenter/merge_presenter.py` (ポーリング), `view/merge/merge_view.py` (DnD), `view/split/split_view.py` (二分割レイアウト)

---

## Decisions

- 内部IDは `extract` に統一（ファイル名・クラス名すべて）
- Source PDF削除時、Targetの該当ページも連動削除
- サムネイルLRUキャッシュ: 256エントリ（ページ単位のため merge の64より大きく）
- 出力は pikepdf（既存依存、ページ操作に最適）
- ズームは Source/Target 独立制御（各パネルに zoom_controls を配置）

## Further Considerations

1. **QSplitter 初期比率**: 左右5:5推奨。ユーザーがドラッグで自由調整可能
2. **Source→Target DnD MIME形式**: カスタム MIME (`application/x-pdf-extract-pages`) で `SourcePageRef` をシリアライズし、内部DnDと外部ファイルDnDを区別
3. **大量ページ時**: 初期実装は QScrollArea + ウィジェット直接配置。1000ページ超でパフォーマンス問題なら QListView + カスタムデリゲートに移行検討
