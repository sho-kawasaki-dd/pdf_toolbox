from __future__ import annotations

from pathlib import Path

from model import external_tools


class _FakeRegistryHandle:
    def __init__(self, subkeys: list[str] | None = None, values: dict[str, str] | None = None) -> None:
        self.subkeys = list(subkeys or [])
        self.values = dict(values or {})

    def __enter__(self) -> _FakeRegistryHandle:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeWinreg:
    HKEY_LOCAL_MACHINE = object()
    HKEY_CURRENT_USER = object()

    def __init__(self, entries: dict[tuple[object, str], _FakeRegistryHandle]) -> None:
        self._entries = entries

    def OpenKey(self, root: object, path: str) -> _FakeRegistryHandle:
        key = (root, path)
        if key not in self._entries:
            raise OSError(path)
        return self._entries[key]

    def EnumKey(self, handle: _FakeRegistryHandle, index: int) -> str:
        if index >= len(handle.subkeys):
            raise OSError(index)
        return handle.subkeys[index]

    def QueryValueEx(self, handle: _FakeRegistryHandle, value_name: str) -> tuple[str, int]:
        if value_name not in handle.values:
            raise OSError(value_name)
        return handle.values[value_name], 1


def test_get_application_root_prefers_meipass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(external_tools.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert external_tools.get_application_root() == tmp_path


def test_resolve_ghostscript_prefers_registry_over_path_and_bundled(monkeypatch, tmp_path: Path) -> None:
    registry_bin = tmp_path / "registry" / "bin"
    registry_bin.mkdir(parents=True)
    (registry_bin / "gsdll64.dll").write_bytes(b"dll")
    registry_executable = registry_bin / "gswin64c.exe"
    registry_executable.write_bytes(b"exe")

    fake_winreg = _FakeWinreg({
        (_FakeWinreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript"): _FakeRegistryHandle(subkeys=["10.05.1"]),
        (_FakeWinreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript\10.05.1"): _FakeRegistryHandle(
            values={"GS_DLL": str(registry_bin / "gsdll64.dll")}
        ),
    })

    monkeypatch.setattr(external_tools, "winreg", fake_winreg)
    monkeypatch.setattr(external_tools, "GHOSTSCRIPT_REGISTRY_ROOTS", ((fake_winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript"),))
    monkeypatch.setattr(external_tools.shutil, "which", lambda _name: str(tmp_path / "path" / "gswin64c.exe"))
    monkeypatch.setattr(external_tools, "get_application_root", lambda: tmp_path / "bundled")

    resolved = external_tools.resolve_ghostscript_executable()

    assert resolved is not None
    assert resolved.path == registry_executable
    assert resolved.source == "winreg"


def test_resolve_ghostscript_uses_path_when_registry_misses(monkeypatch, tmp_path: Path) -> None:
    path_executable = tmp_path / "path" / "gswin64c.exe"
    path_executable.parent.mkdir(parents=True)
    path_executable.write_bytes(b"exe")

    monkeypatch.setattr(external_tools, "winreg", _FakeWinreg({}))
    monkeypatch.setattr(external_tools, "GHOSTSCRIPT_REGISTRY_ROOTS", ((_FakeWinreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript"),))
    monkeypatch.setattr(
        external_tools.shutil,
        "which",
        lambda name: str(path_executable) if name == "gswin64c" else None,
    )
    monkeypatch.setattr(external_tools, "get_application_root", lambda: tmp_path / "bundled")

    resolved = external_tools.resolve_ghostscript_executable()

    assert resolved is not None
    assert resolved.path == path_executable
    assert resolved.source == "path"


def test_resolve_ghostscript_falls_back_to_bundled_binary(monkeypatch, tmp_path: Path) -> None:
    bundled_root = tmp_path / "app"
    bundled_executable = bundled_root / "vendor" / "Ghostscript-windows" / "bin" / "gswin64c.exe"
    bundled_executable.parent.mkdir(parents=True)
    bundled_executable.write_bytes(b"exe")

    monkeypatch.setattr(external_tools, "winreg", _FakeWinreg({}))
    monkeypatch.setattr(external_tools, "GHOSTSCRIPT_REGISTRY_ROOTS", ((_FakeWinreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript"),))
    monkeypatch.setattr(external_tools.shutil, "which", lambda _name: None)
    monkeypatch.setattr(external_tools, "get_application_root", lambda: bundled_root)

    resolved = external_tools.resolve_ghostscript_executable()

    assert resolved is not None
    assert resolved.path == bundled_executable
    assert resolved.source == "bundled"


def test_resolve_pngquant_prefers_path_over_bundled(monkeypatch, tmp_path: Path) -> None:
    path_executable = tmp_path / "tools" / "pngquant.exe"
    path_executable.parent.mkdir(parents=True)
    path_executable.write_bytes(b"exe")

    monkeypatch.setattr(
        external_tools.shutil,
        "which",
        lambda name: str(path_executable) if name == "pngquant" else None,
    )
    monkeypatch.setattr(external_tools, "get_application_root", lambda: tmp_path / "app")

    resolved = external_tools.resolve_pngquant_executable()

    assert resolved is not None
    assert resolved.path == path_executable
    assert resolved.source == "path"


def test_resolve_pngquant_falls_back_to_bundled_binary(monkeypatch, tmp_path: Path) -> None:
    bundled_root = tmp_path / "app"
    bundled_executable = bundled_root / "vendor" / "pngquant-windows" / "pngquant" / "pngquant.exe"
    bundled_executable.parent.mkdir(parents=True)
    bundled_executable.write_bytes(b"exe")

    monkeypatch.setattr(external_tools.shutil, "which", lambda _name: None)
    monkeypatch.setattr(external_tools, "get_application_root", lambda: bundled_root)

    resolved = external_tools.resolve_pngquant_executable()

    assert resolved is not None
    assert resolved.path == bundled_executable
    assert resolved.source == "bundled"