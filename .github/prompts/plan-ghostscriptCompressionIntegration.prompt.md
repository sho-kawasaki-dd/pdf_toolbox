## Plan: Ghostscript Compression Integration

Ghostscript を PDF 圧縮の第2エンジンとして追加し、Ghostscript は Windows 向け実行ファイルへ同梱する標準構成で配布する。実行時の Ghostscript 解決順は Windows レジストリ (`winreg`) -> system PATH -> bundled vendor binary とし、システムに新しい Ghostscript が導入されている場合はそれを優先し、見つからなければ同梱版へフォールバックする。pngquant は system PATH -> bundled vendor binary -> Pillow fallback の順で解決する。圧縮画面はエンジン別タブへ再構成し、Ghostscript タブでは 5 種の画質プリセット + カスタム DPI、後段 pikepdf 実行有無、既存の可逆最適化チェック群を扱う。フラット化画面では最小 UI のまま、フラット化後に Ghostscript (+ 任意で pikepdf default options) を流せる後処理パイプラインを追加する。Windows 配布前提で進め、Ghostscript が見つからない場合はタブを無効化し説明文を表示する。実行ファイル化は one-folder 構成を維持し、TEMP フォルダー展開が必要な one-file 構成は採用しない。最新版の Ghostscript を使いたい利用者には、システムへ最新版をインストールするとそれが優先利用される運用を明記する。

**Steps**
1. Phase 1: Binary resolution and shared compression infrastructure
2. Implement a shared executable-resolution module for external tools so Ghostscript and pngquant can be resolved by platform-appropriate policies without duplicating logic across compression and flatten features.
3. Add Ghostscript Windows discovery with `winreg` support. The resolution order is `winreg -> PATH -> bundled vendor binary`, so a system-installed Ghostscript can override the bundled default. This step blocks all Ghostscript execution work.
4. Add pngquant resolution using `PATH -> bundled vendor binary -> Pillow fallback`, preserving the current image-level failure downgrade semantics.
5. Extend packaging/runtime assumptions for bundled binaries. Keep PyInstaller in one-folder mode, include vendor assets in the build output, and add targeted tests for registry-based resolution, PATH resolution, bundled fallback resolution, and packaged resource-root lookup. This depends on steps 2 and 3.
6. Split the current single compression backend into explicit backend entry points: keep the existing PyMuPDF/pikepdf flow as the native engine, add a new Ghostscript engine adapter, and add a top-level dispatch layer that chooses engine by session state. This depends on steps 2 through 5 and can proceed in parallel with step 7 once the shared settings contract is stable.
7. Expand compression settings/session models to represent engine selection, Ghostscript preset/custom DPI state, Ghostscript availability, optional post-Ghostscript pikepdf execution, and the existing pikepdf lossless options. This depends on step 6’s public interface only loosely and can be developed in parallel after steps 2 through 5 if the enum/string names are fixed.
8. Phase 2: Compression UI and presenter integration
9. Rework the compression view from a single settings pane into engine-specific tabs. Keep the current controls in a native/standard tab, and add a Ghostscript tab with preset selection, custom DPI enabled only for the custom preset, a toggle for post-Ghostscript pikepdf execution, and the existing lossless optimization checkboxes. If Ghostscript is unavailable, keep the tab visible but disabled with an explanatory status message. This depends on step 7.
10. Update the compression presenter to populate the new UI state, react to tab/setting changes, guard invalid combinations, and pass the correct engine configuration into the compression processor. Update completion summaries only if Ghostscript introduces materially different metrics wording. This depends on steps 6, 7, and 9.
11. Update the compression processor to pass engine-specific settings through batch execution for file and ZIP inputs, and to preserve the current behavior for native compression metrics/fallbacks. Add Ghostscript-specific result normalization where needed. This depends on steps 6, 7, and 10.
12. Phase 3: Ghostscript backend behavior
13. Implement Ghostscript PDF compression command construction around the selected preset/custom DPI and temporary output handling. Define a narrow contract: Ghostscript tab always performs Ghostscript compression, and optional post-processing with pikepdf produces the “lossy + lossless” path; the old generic mode combo does not apply inside this tab. This depends on steps 3, 6, and 7.
14. Treat the following Ghostscript baseline flags as non-UI invariants in the command builder: -dColorConversionStrategy=/LeaveColorUnchanged, -dEmbedAllFonts=true, and -dSubsetFonts=true. Do not force a fixed -dCompatibilityLevel; instead, treat compatibility as a floor and avoid configurations that would drop below 1.4 when transparency or soft masks are involved. Apply 1.4 as a lower limit only when necessary. This rule protects soft masks and enforces font subsetting for the large-font regression case. This depends on step 13.
15. Reuse the existing pikepdf lossless optimization function/path after Ghostscript when the new toggle is enabled. Compression-screen Ghostscript settings should expose the current detailed pikepdf checkboxes; flatten-screen post-compression should only expose ON/OFF and use existing default lossless options internally. This depends on steps 13 and 14.
16. Phase 4: Flatten post-processing pipeline
17. Extend the flatten session/presenter/view with a minimal post-compression option set: enable Ghostscript compression after flatten, choose Ghostscript preset, and choose whether to run post-Ghostscript pikepdf with default options. This depends on steps 7 and 9 for shared naming and UI consistency.
18. Insert the post-processing hook in the flatten processor after flattening succeeds. The pipeline should be `Flatten (PyMuPDF) -> Save Temp A -> Compress (Ghostscript) -> Publish final output`, with optional post-Ghostscript pikepdf after Ghostscript succeeds. Reuse the Ghostscript compression service from the compression feature rather than duplicating command construction. Ensure temp-file cleanup and cancellation behavior remain correct if post-processing fails or is interrupted. This depends on steps 13, 14, 15, and 17.
19. Change flatten result semantics from atomic all-or-nothing publication to partial-success publication. If flatten succeeds but Ghostscript compression fails, publish the flattened artifact from Temp A as the final output instead of discarding it. Treat flattening as the primary user goal and compression as an additional optimization stage. This depends on step 18.
20. Add explicit pipeline-warning UI and result messaging for partial success, such as `フラット化完了（圧縮はスキップされました）`, so users understand that flatten succeeded but optimization did not. This depends on steps 18 and 19.
21. Phase 5: Tests, docs, and regression coverage
22. Add or extend model tests for Ghostscript registry resolution precedence, Ghostscript PATH resolution, Ghostscript bundled fallback, pngquant bundled fallback, Ghostscript availability detection, Ghostscript command construction, mandatory Ghostscript baseline flags, post-Ghostscript pikepdf chaining, and compression-session validation. These can be split across multiple files in parallel after steps 3, 4, 7, 13, and 14.
23. Add or extend presenter and view tests for compression tab switching, Ghostscript tab disabled state, custom DPI enablement, flatten post-compression toggle visibility/state, partial-success UI messaging, and propagation of settings into processor calls. This depends on steps 9, 10, 17, and 20.
24. Add or extend flatten processor tests for post-flatten Ghostscript success, Ghostscript failure with flattened-output fallback, cancellation behavior, temp cleanup, and final-output publication semantics. This depends on steps 18, 19, and 20.
25. Update README and user/developer docs to describe Ghostscript resolution order, bundled-vs-system precedence, one-folder packaging rationale, how to opt into newer system Ghostscript versions, Ghostscript engine behavior, UI differences between standard and Ghostscript tabs, and flatten post-compression behavior. This depends on the final UX wording from steps 9, 17, and 20.

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
- c:/Users/tohbo/python_programs/pdf_toolbox/pdf_toolbox.spec — update one-folder packaged contents to include vendor binaries without moving to one-file mode.
- c:/Users/tohbo/python_programs/pdf_toolbox/pdf_toolbox.iss — installer packaging remains based on dist contents and should inherit the bundled Ghostscript payload.
- c:/Users/tohbo/python_programs/pdf_toolbox/build-exe.ps1 — build entry point that should continue to produce one-folder output.
- c:/Users/tohbo/python_programs/pdf_toolbox/scripts/build-exe.ps1 — wrapper build script used by contributors.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/compress/test_native_compressor.py — extend for pngquant resolution and Ghostscript backend behavior.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/compress/test_compression_session.py — extend for engine/Ghostscript settings validation.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/compress/test_compression_processor.py — extend for engine dispatch and ZIP-path behavior.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/model/flatten/test_flatten_processor.py — extend for post-flatten compression pipeline behavior and fallback publication semantics.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/presenter/test_compress_presenter.py — extend for tab state and Ghostscript setting propagation.
- c:/Users/tohbo/python_programs/pdf_toolbox/tests/presenter/test_flatten_presenter.py — extend for post-compression toggle/preset propagation and warning-state messaging.

**Verification**
1. Unit-test Ghostscript executable resolution precedence on Windows using monkeypatch for `winreg`, PATH hits, and bundled fallback behavior.
2. Unit-test pngquant resolution precedence for PATH hit, bundled fallback hit, and Pillow fallback behavior.
3. Unit-test Ghostscript command generation for each preset and custom DPI, including disabled custom DPI outside the custom preset.
4. Unit-test that the mandatory Ghostscript baseline flags are always present: -dColorConversionStrategy=/LeaveColorUnchanged, -dEmbedAllFonts=true, and -dSubsetFonts=true, and that -dCompatibilityLevel is not forced to a fixed value but is treated as a compatibility floor that never drops below 1.4 when transparency or soft masks are involved.
5. Unit-test compression-session and presenter state transitions for engine tabs, Ghostscript availability-disabled state, and pikepdf toggle/detail options.
6. Run targeted compression processor tests for native engine regressions and new Ghostscript dispatch on both normal PDF inputs and ZIP-contained PDFs.
7. Run targeted flatten processor tests for post-flatten compression success, Ghostscript failure with flattened-output fallback, cancellation, temp cleanup, and final-output publication semantics.
8. Run focused presenter and view tests for compression and flatten UI updates, including partial-success warning UI.
9. Run a packaged-build smoke check to verify vendor binaries are present in the one-folder build output and resolved correctly under the packaged resource root without requiring TEMP extraction.
10. Perform manual Windows validation with representative PDFs: PNG-heavy PDFs, annotation/form flatten cases with external-font references, a machine where Ghostscript is absent to confirm the disabled-tab behavior, and a machine with a newer system Ghostscript to confirm override precedence over the bundled version.

**Decisions**
- Scope includes Windows-first bundled binary support; non-Windows is not a packaging target in this change.
- Ghostscript is distributed in the packaged application by default instead of being treated as an external dependency.
- Ghostscript resolution order on Windows is `winreg -> PATH -> bundled vendor binary`.
- The bundled Ghostscript version is the stable default, but users who want a newer version can install it system-wide and the app will prefer it.
- Packaging remains one-folder; one-file packaging is not adopted because TEMP extraction is undesirable for this app.
- Compression UI becomes engine-based tabs, not a single conditional pane.
- Ghostscript tab uses standard 5 presets plus a custom preset, and custom DPI is editable only in the custom preset.
- Ghostscript tab does not reuse the old generic mode combo; Ghostscript always runs, and post-Ghostscript pikepdf determines whether the path is effectively lossy-only or lossy-plus-lossless.
- Compression-screen Ghostscript settings expose the detailed pikepdf lossless checkboxes.
- Flatten screen remains minimal: post-flatten Ghostscript toggle, preset selector, and pikepdf ON/OFF only.
- When Ghostscript is unavailable, its tab remains visible but disabled with explanation.
- pngquant resolution order is system PATH -> bundled vendor binary -> Pillow fallback.
- Flatten success is treated as the primary outcome; if post-flatten compression fails, the flattened artifact is still published and the user is notified that compression was skipped.

**Further Considerations**
1. Keep Ghostscript discovery in a dedicated shared module rather than embedding it inside the current native compression implementation, because both compression and flatten depend on it.
2. If Ghostscript metrics differ materially from the current native metrics model, decide whether to normalize to a common summary shape or show engine-specific wording in completion dialogs.
3. Document clearly which bundled Ghostscript version ships with each release so users can decide whether they need to install a newer system version.