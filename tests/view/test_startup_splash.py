"""起動スプラッシュのレイアウト計算テスト。"""

from __future__ import annotations

from view.startup_splash import _compute_splash_size, _select_icon_size


class TestStartupSplash:

    def test_compute_splash_size_for_full_hd(self):
        width, height = _compute_splash_size(1920, 1080)
        assert width >= 420
        assert height >= 260
        assert width > height

    def test_compute_splash_size_has_minimums(self):
        width, height = _compute_splash_size(800, 600)
        assert width == 420
        assert height == 260

    def test_compute_splash_size_has_caps(self):
        width, height = _compute_splash_size(5000, 3000)
        assert width == 720
        assert height == 420

    def test_select_icon_size_prefers_256(self):
        assert _select_icon_size([(16, 16), (32, 32), (256, 256)]) == 256

    def test_select_icon_size_uses_next_larger_when_256_missing(self):
        assert _select_icon_size([(16, 16), (48, 48), (512, 512)]) == 512

    def test_select_icon_size_falls_back_to_largest_smaller_size(self):
        assert _select_icon_size([(16, 16), (32, 32), (128, 128)]) == 128