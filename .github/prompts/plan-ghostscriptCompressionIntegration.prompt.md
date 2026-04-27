## Plan: Ghostscript Compression Integration

Ghostscript を PDF 圧縮の第2エンジンとして追加し、pngquant/Ghostscript の実行ファイル解決を system PATH -> bundled vendor binary の優先順で統一する。圧縮画面はエンジン別タブへ再構成し、Ghostscript タブでは 5 種の画質プリセット + カスタム DPI、後段 pikepdf 実行有無、既存の可逆最適化チェック群を扱う。フラット化画面では最小 UI のまま、フラット化後に Ghostscript (+ 任意で pikepdf default options) を流せる後処理パイプラインを追加する。Windows 配布前提で進め、Ghostscript が見つからない場合はタブを無効化し説明文を表示する。

**Steps**
1. Phase 1: Binary resolution and shared compression infrastructure
2. Add a shared executable-resolution module for external tools so pngquant and Ghostscript both use the same policy: system PATH first, then bundled vendor path under the PyInstaller resource root. This step blocks all Ghostscript execution work.
3. Extend packaging/runtime assumptions for bundled binaries. Update the PyInstaller spec so vendor assets are included in the build output, and add targeted tests for resource-root and bundled-path resolution. This depends on step 2.
4. Split the current single compression backend into explicit backend entry points: keep the existing PyMuPDF/pikepdf flow as the native engine, add a new Ghostscript engine adapter, and add a top-level dispatch layer that chooses engine by session state. This depends on step 2 and can proceed in parallel with step 5 once the shared settings contract is stable.
5. Expand compression settings/session models to represent engine selection, Ghostscript preset/custom DPI state, Ghostscript availability, optional post-Ghostscript pikepdf execution, and the existing pikepdf lossless options. This depends on step 4’s public interface only loosely and can be developed in parallel after step 2 if the enum/string names are fixed.
6. Phase 2: Compression UI and presenter integration
7. Rework the compression view from a single settings pane into engine-specific tabs. Keep the current controls in a native/standard tab, and add a Ghostscript tab with preset selection, custom DPI enabled only for the custom preset, a toggle for post-Ghostscript pikepdf execution, and the existing lossless optimization checkboxes. If Ghostscript is unavailable, keep the tab visible but disabled with an explanatory status message. This depends on step 5.
8. Update the compression presenter to populate the new UI state, react to tab/setting changes, guard invalid combinations, and pass the correct engine configuration into the compression processor. Update completion summaries only if Ghostscript introduces materially different metrics wording. This depends on steps 4, 5, and 7.
9. Update the compression processor to pass engine-specific settings through batch execution for file and ZIP inputs, and to preserve the current behavior for native compression metrics/fallbacks. Add Ghostscript-specific result normalization where needed. This depends on steps 4, 5, and 8.
10. Phase 3: Ghostscript backend behavior
11. Implement Ghostscript PDF compression command construction around the selected preset/custom DPI and temporary output handling. Define a narrow contract: Ghostscript tab always performs Ghostscript compression, and optional post-processing with pikepdf produces the “lossy + lossless” path; the old generic mode combo does not apply inside this tab. This depends on steps 2, 4, and 5.
12. Reuse the existing pikepdf lossless optimization function/path after Ghostscript when the new toggle is enabled. Compression-screen Ghostscript settings should expose the current detailed pikepdf checkboxes; flatten-screen post-compression should only expose ON/OFF and use existing default lossless options internally. This depends on step 11.
13. Update pngquant detection to use the same system -> bundled -> Pillow fallback chain, keeping the current image-level failure downgrade semantics. This can run in parallel with steps 11 and 12 once step 2 is done.
14. Phase 4: Flatten post-processing pipeline
15. Extend the flatten session/presenter/view with a minimal post-compression option set: enable Ghostscript compression after flatten, choose Ghostscript preset, and choose whether to run post-Ghostscript pikepdf with default options. This depends on steps 5 and 7 for shared naming and UI consistency.
16. Insert the post-processing hook in the flatten processor after the flattened PDF has been safely written and before the job is reported as success. Reuse the Ghostscript compression service from the compression feature rather than duplicating command construction. Ensure temp-file cleanup and cancellation behavior remain correct if post-processing fails or is interrupted. This depends on steps 11, 12, and 15.
17. Decide and document flatten result semantics: flatten success followed by post-compression failure should likely report the job as failure while preserving the flattened output only if that is an intentional product decision; otherwise the pipeline should write atomically to a temp path and only publish the final output after all selected post-processing succeeds. Recommended implementation: keep atomic semantics and publish only the final chosen artifact. This step depends on step 16 and should be validated with the user if implementation-time edge cases arise.
18. Phase 5: Tests, docs, and regression coverage
19. Add/extend model tests for executable resolution precedence, pngquant bundled fallback, Ghostscript availability detection, Ghostscript command construction, post-Ghostscript pikepdf chaining, and compression-session validation. These can be split across multiple files in parallel after steps 2, 5, 11, and 13.
20. Add/extend presenter and view tests for compression tab switching, Ghostscript tab disabled state, custom DPI enablement, flatten post-compression toggle visibility/state, and propagation of settings into processor calls. This depends on steps 7, 8, and 15.
21. Add/extend flatten processor tests for post-flatten Ghostscript success/failure/cancel behavior and atomic output semantics. This depends on step 16.
22. Update README and user/developer docs to describe bundled tool resolution order, Ghostscript engine behavior, UI differences between standard and Ghostscript tabs, and flatten post-compression behavior. This depends on the final UX wording from steps 7 and 15.

**Relevant files**
- c:/Users/tohbo/python_programs/pdf_toolbox/model/compress/native_compressor.py — current native compression engine, pngquant integration, and the best extraction point for backend dispatch and shared pikepdf reuse.
- c:/Users/tohbo/python_programs/pdf_toolbox/model/compress/compression_processor.py — batch job execution and parameter pass-through for file/ZIP compression.
- c:/Users/tohbo/python_programs/pdf_toolbox/model/compress/compression_session.py — compression state model to extend with engine and Ghostscript settings.
- c:/Users/tohbo/python_programs/pdf_toolbox/model/compress/settings.py — current constants/defaults; add Ghostscript presets, engine identifiers, and resolution defaults here or in a new sibling module.
- c:/Users/tohbo/python_programs/pdf_toolbox/presenter/compress_presenter.py — compression UI-to-session orchestration.
- c:/Users/tohbo/python_programs/pdf_toolbox/view/compress/compress_view.py — current single-pane compression UI to be reworked into engine tabs.
- c:/Users/tohbo/python_programs/pdf_toolbox/model/flatten/flatten_processor.py — flatten execution path and the insertion point for post-flatten compression.
- c:/Users/tohbo/python_programs/pdf_toolbox/model/flatten/flatten_session.py — flatten state model; add minimal post-compression settings here.
- c:/Users/tohbo/python_programs/pdf_toolbox/presenter/flatten_presenter.py — flatten UI state and result handling.
- c:/Users/tohbo/python_programs/pdf_toolbox/view/flatten/flatten_view.py — minimal flatten UI to extend with the post-compression toggle/preset controls.
- c:/Users/tohbo/python_programs/pdf_toolbox/main.py — existing resource-root helper pattern for bundled assets.
- c:/Users/tohbo/python_programs/pdf_toolbox/pdf_toolbox.spec — currently bundles assets/fonts but not vendor binaries; must include vendor content for packaged builds.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/compress/test_native_compressor.py — extend for pngquant resolution and Ghostscript backend behavior.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/compress/test_compression_session.py — extend for engine/Ghostscript settings validation.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/compress/test_compression_processor.py — extend for engine dispatch and ZIP-path behavior.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/flatten/test_flatten_processor.py — extend for post-flatten compression pipeline behavior.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/presenter/test_compress_presenter.py — extend for tab state and Ghostscript setting propagation.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/presenter/test_flatten_presenter.py — extend for post-compression toggle/preset propagation.

**Verification**
1. Unit-test executable resolution precedence for pngquant and Ghostscript using monkeypatch: system PATH hit, bundled fallback hit, and full-miss fallback behavior.
2. Unit-test Ghostscript command generation for each preset and custom DPI, including disabled custom DPI outside the custom preset.
3. Unit-test compression-session/presenter state transitions for engine tabs, Ghostscript availability-disabled state, and pikepdf toggle/detail options.
4. Run targeted compression processor tests for native engine regressions and new Ghostscript dispatch on both normal PDF inputs and ZIP-contained PDFs.
5. Run targeted flatten processor tests for post-flatten compression success, Ghostscript failure, cancellation, temp cleanup, and atomic final-output publication.
6. Run focused presenter/view tests for compression and flatten UI updates.
7. Run a packaged-build smoke check to verify vendor binaries are present in the build output and resolved correctly under the PyInstaller resource root.
8. Perform manual Windows validation with representative PDFs: PNG-heavy PDFs, annotation/form flatten cases with external-font references, and a machine where Ghostscript is absent to confirm the disabled-tab behavior.

**Decisions**
- Scope includes Windows-first bundled binary support; non-Windows is not a packaging target in this change.
- Compression UI becomes engine-based tabs, not a single conditional pane.
- Ghostscript tab uses standard 5 presets plus a custom preset, and custom DPI is editable only in the custom preset.
- Ghostscript tab does not reuse the old generic mode combo; Ghostscript always runs, and post-Ghostscript pikepdf determines whether the path is effectively lossy-only or lossy-plus-lossless.
- Compression-screen Ghostscript settings expose the detailed pikepdf lossless checkboxes.
- Flatten screen remains minimal: post-flatten Ghostscript toggle, preset selector, and pikepdf ON/OFF only.
- When Ghostscript is unavailable, its tab remains visible but disabled with explanation.
- pngquant resolution order is system PATH -> bundled vendor binary -> Pillow fallback.

**Further Considerations**
1. Flatten post-compression failure semantics should be implemented atomically so a partially processed artifact is not silently published unless explicitly desired.
2. If Ghostscript metrics differ materially from the current native metrics model, decide whether to normalize to a common summary shape or show engine-specific wording in completion dialogs.
3. Consider moving external-tool discovery into a dedicated shared module now rather than embedding it in native_compressor.py, because both compression and flatten will depend on it.