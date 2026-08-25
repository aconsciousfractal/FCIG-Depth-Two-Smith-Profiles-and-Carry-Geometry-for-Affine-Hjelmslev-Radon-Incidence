#!/usr/bin/env python3
"""Fail-closed verifier for the environment-independent source manifest."""

from __future__ import annotations

import ctypes
import hashlib
import os
import stat
from pathlib import Path, PurePosixPath


def _lexical_absolute(path: Path) -> Path:
    """Make a path absolute without resolving links or reparse points."""

    return Path(os.path.abspath(os.fspath(path)))


ROOT = _lexical_absolute(Path(__file__)).parents[1]
MANIFEST_NAME = "MANIFEST_SHA256.txt"
RELEASE_NAME = "RELEASE_SHA256.txt"
PDF_PATH = (
    "paper/Depth-Two-Smith-Profiles-and-Carry-Geometry-for-"
    "Affine-Hjelmslev-Radon-Incidence.pdf"
)
EXCLUDED = {MANIFEST_NAME, RELEASE_NAME, PDF_PATH}
EXPECTED_DIRECTORIES = {
    ".github",
    ".github/workflows",
    "companion",
    "docs",
    "paper",
    "scripts",
    "tests",
}
IGNORED_ROOT_ENTRIES = {".git"}
FILE_ATTRIBUTE_REPARSE_POINT = getattr(
    stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400
)


def native_path(path: Path) -> Path:
    """Return a lexical extended Win32 path and preserve UNC semantics."""

    if os.name != "nt":
        return _lexical_absolute(path)
    absolute = str(_lexical_absolute(path))
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _sha256(path: Path) -> str:
    with native_path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().upper()


def _stream_names(path: Path) -> list[str]:
    """Enumerate nondefault NTFS streams, failing closed on API errors."""

    if os.name != "nt":
        return []

    class Win32FindStreamData(ctypes.Structure):
        _fields_ = [
            ("stream_size", ctypes.c_longlong),
            ("stream_name", ctypes.c_wchar * 296),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first = kernel32.FindFirstStreamW
    find_first.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.POINTER(Win32FindStreamData),
        ctypes.c_ulong,
    ]
    find_first.restype = ctypes.c_void_p
    find_next = kernel32.FindNextStreamW
    find_next.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Win32FindStreamData),
    ]
    find_next.restype = ctypes.c_int
    find_close = kernel32.FindClose
    find_close.argtypes = [ctypes.c_void_p]
    find_close.restype = ctypes.c_int

    data = Win32FindStreamData()
    handle = find_first(str(native_path(path)), 0, ctypes.byref(data), 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        if error in {2, 38}:  # no stream / end of enumeration
            return []
        raise OSError(error, f"cannot enumerate streams for {path}")

    names: list[str] = []
    try:
        names.append(data.stream_name)
        while find_next(handle, ctypes.byref(data)):
            names.append(data.stream_name)
        error = ctypes.get_last_error()
        if error != 38:
            raise OSError(error, f"cannot complete stream scan for {path}")
    finally:
        find_close(handle)
    return sorted(name for name in names if name != "::$DATA")


def _safe_manifest_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.as_posix() == value
    )


def inspect_tree(root: Path = ROOT) -> dict[str, set[str]]:
    """Census every file and directory without following reparse points."""

    lexical_root = _lexical_absolute(root)
    scan_root = native_path(lexical_root)
    try:
        root_stat = os.lstat(scan_root)
    except FileNotFoundError as error:
        raise AssertionError("repository root is missing") from error
    if getattr(root_stat, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
        raise AssertionError("repository root cannot be a reparse point")
    if not scan_root.is_dir():
        raise AssertionError("repository root is not a directory")
    root_streams = _stream_names(lexical_root)
    if root_streams:
        raise AssertionError(f"alternate stream on repository root: {root_streams}")

    files: set[str] = set()
    directories: set[str] = set()
    stack = [scan_root]
    while stack:
        current = stack.pop()
        with os.scandir(current) as iterator:
            entries = sorted(iterator, key=lambda item: item.name)
        for entry in entries:
            # The release census authenticates the versioned package, not the
            # clone's administrative database.  Restrict the exclusion to the
            # repository root: a nested .git entry remains undeclared drift.
            if current == scan_root and entry.name in IGNORED_ROOT_ENTRIES:
                continue
            path = Path(entry.path)
            relative = path.relative_to(scan_root).as_posix()
            entry_stat = entry.stat(follow_symlinks=False)
            attributes = getattr(entry_stat, "st_file_attributes", 0)
            if entry.is_symlink() or attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise AssertionError(f"reparse point is not allowed: {relative}")
            streams = _stream_names(
                lexical_root / Path(*PurePosixPath(relative).parts)
            )
            if streams:
                raise AssertionError(
                    f"alternate stream is not allowed: {relative}: {streams}"
                )
            if entry.is_dir(follow_symlinks=False):
                directories.add(relative)
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.add(relative)
            else:
                raise AssertionError(f"special filesystem object: {relative}")

    if directories != EXPECTED_DIRECTORIES:
        raise AssertionError(
            "repository directory drift: "
            f"missing={sorted(EXPECTED_DIRECTORIES - directories)}, "
            f"extra={sorted(directories - EXPECTED_DIRECTORIES)}"
        )
    return {"files": files, "directories": directories}


def _parse_manifest(root: Path = ROOT) -> list[tuple[str, str]]:
    manifest = root / MANIFEST_NAME
    if not native_path(manifest).is_file():
        raise AssertionError("source manifest is missing")
    rows: list[tuple[str, str]] = []
    for line_number, raw in enumerate(
        native_path(manifest).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        fields = raw.split(maxsplit=1)
        if len(fields) != 2:
            raise AssertionError(f"malformed manifest line {line_number}")
        digest, relative = fields
        if len(digest) != 64 or any(ch not in "0123456789ABCDEF" for ch in digest):
            raise AssertionError(f"invalid SHA-256 on line {line_number}")
        if not _safe_manifest_path(relative):
            raise AssertionError(f"noncanonical path on line {line_number}")
        rows.append((digest, relative))
    if not rows:
        raise AssertionError("source manifest is empty")
    if [path for _, path in rows] != sorted(path for _, path in rows):
        raise AssertionError("source manifest paths are not sorted")
    if len({path for _, path in rows}) != len(rows):
        raise AssertionError("duplicate source manifest path")
    return rows


def check_manifest(root: Path = ROOT) -> dict[str, object]:
    tree = inspect_tree(root)
    rows = _parse_manifest(root)
    declared = {path for _, path in rows}
    expected = tree["files"] - EXCLUDED
    if declared != expected:
        raise AssertionError(
            f"manifest coverage drift: missing={sorted(expected - declared)}, "
            f"extra={sorted(declared - expected)}"
        )
    for expected_digest, relative in rows:
        observed = _sha256(root / Path(*PurePosixPath(relative).parts))
        if observed != expected_digest:
            raise AssertionError(f"source digest mismatch: {relative}")
    return {
        "status": "PASS",
        "source_files": len(rows),
        "repository_directories": len(tree["directories"]),
    }


def main() -> int:
    result = check_manifest()
    print(
        "MANIFEST PASS "
        f"files={result['source_files']} "
        f"directories={result['repository_directories']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
