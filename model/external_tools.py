from __future__ import annotations

"""外部ツール実行ファイルの解決を集約する。"""

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import winreg
except ImportError:
    winreg = None


PNGQUANT_PATH_CANDIDATES: tuple[str, ...] = ("pngquant",)
PNGQUANT_BUNDLED_RELATIVE_PATHS: tuple[Path, ...] = (
    Path("vendor/pngquant-windows/pngquant/pngquant.exe"),
)

GHOSTSCRIPT_PATH_CANDIDATES: tuple[str, ...] = (
    "gswin64c",
    "gswin32c",
    "gswin64",
    "gswin32",
    "gs",
)
GHOSTSCRIPT_BUNDLED_RELATIVE_PATHS: tuple[Path, ...] = (
    Path("vendor/Ghostscript-windows/bin/gswin64c.exe"),
    Path("vendor/Ghostscript-windows/bin/gswin32c.exe"),
    Path("vendor/Ghostscript-windows/bin/gswin64.exe"),
    Path("vendor/Ghostscript-windows/bin/gswin32.exe"),
)
GHOSTSCRIPT_REGISTRY_ROOTS: tuple[tuple[object, str], ...] = (
    (getattr(winreg, "HKEY_LOCAL_MACHINE", object()), r"SOFTWARE\GPL Ghostscript"),
    (getattr(winreg, "HKEY_CURRENT_USER", object()), r"SOFTWARE\GPL Ghostscript"),
    (getattr(winreg, "HKEY_LOCAL_MACHINE", object()), r"SOFTWARE\WOW6432Node\GPL Ghostscript"),
    (getattr(winreg, "HKEY_CURRENT_USER", object()), r"SOFTWARE\WOW6432Node\GPL Ghostscript"),
)
GHOSTSCRIPT_EXECUTABLE_NAMES: tuple[str, ...] = (
    "gswin64c.exe",
    "gswin32c.exe",
    "gswin64.exe",
    "gswin32.exe",
)


@dataclass(frozen=True, slots=True)
class ResolvedExecutable:
    tool_name: str
    path: Path
    source: str


def get_application_root() -> Path:
    """開発実行と PyInstaller 実行の両方で使えるアプリケーションルートを返す。"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _resolve_command_on_path(tool_name: str, command_names: Iterable[str]) -> ResolvedExecutable | None:
    for command_name in command_names:
        resolved_path = shutil.which(command_name)
        if resolved_path:
            return ResolvedExecutable(tool_name=tool_name, path=Path(resolved_path), source="path")
    return None


def _resolve_bundled_executable(tool_name: str, relative_paths: Iterable[Path]) -> ResolvedExecutable | None:
    app_root = get_application_root()
    for relative_path in relative_paths:
        candidate = app_root / relative_path
        if candidate.exists():
            return ResolvedExecutable(tool_name=tool_name, path=candidate, source="bundled")
    return None


def _parse_version_tuple(version_text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version_text)
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts)


def _derive_ghostscript_executable_from_dll(dll_path: str | Path) -> Path | None:
    bin_dir = Path(dll_path).expanduser().resolve().parent
    for executable_name in GHOSTSCRIPT_EXECUTABLE_NAMES:
        candidate = bin_dir / executable_name
        if candidate.exists():
            return candidate
    return None


def _resolve_ghostscript_from_registry() -> ResolvedExecutable | None:
    if os.name != "nt" or winreg is None:
        return None

    registry_hits: list[tuple[tuple[int, ...], ResolvedExecutable]] = []
    for root_key, registry_path in GHOSTSCRIPT_REGISTRY_ROOTS:
        try:
            with winreg.OpenKey(root_key, registry_path) as ghostscript_root:
                subkey_names: list[str] = []
                index = 0
                while True:
                    try:
                        subkey_names.append(winreg.EnumKey(ghostscript_root, index))
                    except OSError:
                        break
                    index += 1
        except OSError:
            continue

        for subkey_name in subkey_names:
            version_key_path = f"{registry_path}\\{subkey_name}"
            try:
                with winreg.OpenKey(root_key, version_key_path) as version_key:
                    gs_dll, _value_type = winreg.QueryValueEx(version_key, "GS_DLL")
            except OSError:
                continue

            executable_path = _derive_ghostscript_executable_from_dll(gs_dll)
            if executable_path is None:
                continue

            registry_hits.append((
                _parse_version_tuple(subkey_name),
                ResolvedExecutable(tool_name="ghostscript", path=executable_path, source="winreg"),
            ))

    if not registry_hits:
        return None
    return max(registry_hits, key=lambda item: item[0])[1]


def resolve_pngquant_executable() -> ResolvedExecutable | None:
    resolved = _resolve_command_on_path("pngquant", PNGQUANT_PATH_CANDIDATES)
    if resolved is not None:
        return resolved
    return _resolve_bundled_executable("pngquant", PNGQUANT_BUNDLED_RELATIVE_PATHS)


def resolve_ghostscript_executable() -> ResolvedExecutable | None:
    registry_resolved = _resolve_ghostscript_from_registry()
    if registry_resolved is not None:
        return registry_resolved

    path_resolved = _resolve_command_on_path("ghostscript", GHOSTSCRIPT_PATH_CANDIDATES)
    if path_resolved is not None:
        return path_resolved

    return _resolve_bundled_executable("ghostscript", GHOSTSCRIPT_BUNDLED_RELATIVE_PATHS)


def is_pngquant_available() -> bool:
    return resolve_pngquant_executable() is not None


def is_ghostscript_available() -> bool:
    return resolve_ghostscript_executable() is not None