#!/usr/bin/env python3
"""Inventory Android reverse-analysis artifacts for static triage."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


PACKER_HINTS = (
    # China-market packers
    "jiagu", "bangcle", "secneo", "ijiami", "qihoo", "tencent_stub",
    "legu", "libshella", "libDexHelper", "libsecexe", "libprotectClass",
    "libBaiduProtect", "libmobisec", "libtup", "libexec", "libexecmain",
    "libjiagu", "libddog", "libfdog", "libchaosvmp", "libegis",
    "libnesec", "libAPKProtect", "libdemolish", "libx3g", "libmedl",
    # International packers
    "apkprotect", "dexhelper", "dexguard", "arxan", "verimatrix",
    "promon", "guardsquare", "liapp", "appsealing", "virbox", "nagain",
    # Generic indicators
    "shell", "protect", "stub", "packer", "wrapper",
)

FRAMEWORK_HINTS = {
    "unity-il2cpp": ("libil2cpp.so", "global-metadata.dat"),
    "flutter": ("libflutter.so", "flutter_assets/"),
    "react-native-hermes": ("libhermes.so", "index.android.bundle"),
    "cordova-webview": ("assets/www/", "cordova.js"),
    "xamarin": ("libmonodroid.so", "assemblies/"),
}

DYNAMIC_CODE_SUFFIXES = (".dex", ".jar", ".apk", ".zip", ".so")
ARCHIVE_SUFFIXES = {".apk", ".xapk", ".zip", ".aar", ".jar"}


@dataclass(frozen=True)
class Entry:
    source: str
    path: str
    size: int | None


@dataclass(frozen=True)
class InputFile:
    path: Path
    size: int
    sha256: str


def iter_entries(path: Path):
    if path.is_file() and path.suffix.lower() in ARCHIVE_SUFFIXES:
        yield from iter_archive_entries(path)
        return

    if path.is_file():
        yield Entry(str(path.parent), path.name, path.stat().st_size)
        return

    for item in path.rglob("*"):
        if not item.is_file():
            continue
        if item.suffix.lower() in ARCHIVE_SUFFIXES:
            yield from iter_archive_entries(item)
            continue
        try:
            rel = str(item.relative_to(path))
        except ValueError:
            rel = str(item)
        yield Entry(str(path), rel, item.stat().st_size)


def iter_archive_entries(path: Path):
    if path.suffix.lower() in ARCHIVE_SUFFIXES:
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if not info.is_dir():
                        yield Entry(str(path), info.filename, info.file_size)
        except zipfile.BadZipFile:
            yield Entry(str(path), path.name, path.stat().st_size)


def iter_input_files(path: Path):
    if path.is_file():
        yield path
        return
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in ARCHIVE_SUFFIXES:
            yield item


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches_any(value: str, needles: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(needle.lower() in lowered for needle in needles)


def classify(entries: list[Entry]) -> dict[str, list[Entry]]:
    buckets: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        lowered = entry.path.lower()
        name = Path(lowered).name
        if name.startswith("classes") and name.endswith(".dex"):
            buckets["Root DEX files"].append(entry)
        if lowered.endswith(DYNAMIC_CODE_SUFFIXES) and not name.startswith("classes"):
            buckets["Dynamic/native code artifacts"].append(entry)
        if lowered.startswith("lib/") and lowered.endswith(".so"):
            buckets["Native libraries by ABI"].append(entry)
        if lowered.startswith("assets/") or "/assets/" in lowered:
            buckets["Assets"].append(entry)
        if matches_any(lowered, PACKER_HINTS):
            buckets["Packer/protector hints"].append(entry)
        for framework, hints in FRAMEWORK_HINTS.items():
            if matches_any(lowered, hints):
                buckets[f"Framework hint: {framework}"].append(entry)
    return buckets


def print_table(title: str, rows: list[Entry], limit: int) -> None:
    print(f"\n## {title}\n")
    if not rows:
        print("_No matches._")
        return
    print("| Source | Path | Size |")
    print("|---|---|---:|")
    for row in rows[:limit]:
        size = "-" if row.size is None else str(row.size)
        safe_path = row.path.replace("|", "\\|")
        print(f"| `{row.source}` | `{safe_path}` | {size} |")
    if len(rows) > limit:
        print(f"\n_Truncated {len(rows) - limit} additional rows._")


def print_input_files(rows: list[InputFile], limit: int) -> None:
    print("\n## Input file hashes\n")
    if not rows:
        print("_No input archives found._")
        return
    print("| Path | Size | SHA-256 |")
    print("|---|---:|---|")
    for row in rows[:limit]:
        print(f"| `{row.path}` | {row.size} | `{row.sha256}` |")
    if len(rows) > limit:
        print(f"\n_Truncated {len(rows) - limit} additional rows._")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory APK/APKTool/JADX artifacts for static reverse-analysis triage.")
    parser.add_argument("paths", nargs="+", help="APK/XAPK/archive or extracted/decompiled directory")
    parser.add_argument("--limit", type=int, default=80, help="max rows per section")
    args = parser.parse_args(argv)

    all_entries: list[Entry] = []
    input_files: list[InputFile] = []
    for raw in args.paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"path not found: {path}")
        all_entries.extend(iter_entries(path))
        for input_file in iter_input_files(path):
            input_files.append(InputFile(input_file, input_file.stat().st_size, sha256_file(input_file)))

    buckets = classify(all_entries)
    ordered = [
        "Root DEX files",
        "Packer/protector hints",
        "Framework hint: unity-il2cpp",
        "Framework hint: flutter",
        "Framework hint: react-native-hermes",
        "Framework hint: cordova-webview",
        "Framework hint: xamarin",
        "Dynamic/native code artifacts",
        "Native libraries by ABI",
        "Assets",
    ]
    print("# Android Static Artifact Inventory")
    print_input_files(input_files, args.limit)
    for title in ordered:
        print_table(title, buckets.get(title, []), args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
