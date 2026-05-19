#!/usr/bin/env python3
"""Export Android app packages and run repeatable static reverse-analysis tools."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


KNOWN_PACKAGES: dict[str, str] = {}

PACKAGE_RE = re.compile(r"^[a-zA-Z][\w]*(\.[a-zA-Z_][\w]*)+$")


@dataclass(frozen=True)
class AppSpec:
    alias: str
    package: str | None = None
    apk_path: Path | None = None


@dataclass(frozen=True)
class AppResult:
    alias: str
    package: str
    apk_dir: Path
    jadx_dir: Path
    apktool_dir: Path | None
    apktool_status: str | None
    vineflower_dir: Path | None
    vineflower_status: str | None
    apkid_status: str | None
    apkleaks_report: Path | None
    apkleaks_status: str | None
    apk_count: int
    jadx_exit: int
    manifest_package: str | None
    status: str


def run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command, optionally with a timeout in seconds.

    If timeout is set and the process exceeds it, the process is terminated
    and a CompletedProcess with returncode=-9 is returned.
    """
    print("+ " + " ".join(cmd), flush=True)
    if timeout is None:
        return subprocess.run(cmd, text=True, capture_output=True)
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Process exceeded {timeout}s limit, terminating.", flush=True)
        return subprocess.CompletedProcess(cmd, returncode=-9, stdout="", stderr=f"timeout after {timeout}s")


def adb_cmd(args: list[str], serial: str | None = None) -> list[str]:
    if serial:
        return ["adb", "-s", serial, *args]
    return ["adb", *args]


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise SystemExit(f"Missing required tool: {name}")


def require_any_tool(names: list[str]) -> str:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise SystemExit(f"Missing required tool: one of {', '.join(names)}")


def safe_alias(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    return cleaned or "app"


def parse_spec(raw: str) -> AppSpec:
    if "=" in raw:
        alias_raw, value_raw = raw.split("=", 1)
        alias = safe_alias(alias_raw)
        value = value_raw.strip()
        path = Path(value).expanduser()
        if path.exists():
            return AppSpec(alias=alias, apk_path=path)
        return AppSpec(alias=alias, package=value)

    path = Path(raw).expanduser()
    if path.exists():
        return AppSpec(alias=safe_alias(path.stem.replace("_apks", "")), apk_path=path)

    lowered = raw.lower()
    if lowered in KNOWN_PACKAGES:
        return AppSpec(alias=safe_alias(lowered), package=KNOWN_PACKAGES[lowered])

    if PACKAGE_RE.match(raw):
        return AppSpec(alias=safe_alias(raw.split(".")[-1]), package=raw)

    return AppSpec(alias=safe_alias(raw), package=None)


def parse_adb_devices(output: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("*") or line.startswith("List of devices"):
            continue
        columns = line.split()
        if len(columns) >= 2:
            devices[columns[0]] = columns[1]
    return devices


def ensure_adb_device(serial: str | None) -> None:
    devices_proc = run(["adb", "devices"])
    if devices_proc.returncode != 0:
        raise SystemExit(devices_proc.stderr.strip() or "failed to run adb devices")

    devices = parse_adb_devices(devices_proc.stdout)
    if serial:
        if devices.get(serial) == "device":
            return
        state_proc = run(adb_cmd(["get-state"], serial))
        if state_proc.returncode == 0 and state_proc.stdout.strip() == "device":
            return
        observed = devices.get(serial, "not listed")
        raise SystemExit(
            f"ADB serial '{serial}' is not authorized/ready (state: {observed}). "
            "Check `adb devices`, then retry or manually pull with "
            "`adb -s <serial> shell pm path <package>` and `adb -s <serial> pull <remote> <dir>`."
        )

    ready = [device for device, state in devices.items() if state == "device"]
    if len(ready) == 1:
        return
    if len(ready) > 1:
        raise SystemExit(
            "Multiple authorized adb devices found. Rerun with `--serial <device>` "
            f"or set ANDROID_SERIAL. Devices: {', '.join(ready)}"
        )
    raise SystemExit(
        "No authorized adb device found. Check `adb devices`; if a device is listed, "
        "rerun with `--serial <device>` or set ANDROID_SERIAL. Manual fallback: "
        "`adb shell pm path <package>` then `adb pull <remote-apk> <output-dir>`."
    )


def resolve_package(spec: AppSpec, serial: str | None) -> str:
    if spec.package:
        return spec.package

    proc = run(adb_cmd(["shell", "pm", "list", "packages", "-3"], serial))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"failed to list packages for {spec.alias}")

    needle = spec.alias.lower()
    matches = []
    for line in proc.stdout.splitlines():
        pkg = line.removeprefix("package:").strip()
        if needle in pkg.lower():
            matches.append(pkg)

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"could not resolve app name '{spec.alias}' to a package")
    raise RuntimeError(f"ambiguous app name '{spec.alias}': {', '.join(matches[:20])}")


def output_dirs(base_out: Path, alias: str, flat: bool) -> tuple[Path, Path]:
    if flat:
        return base_out / f"{alias}_apks", base_out / f"{alias}_jadx"
    return base_out / alias / "apks", base_out / alias / "jadx"


def prepare_dir(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not force:
            raise RuntimeError(f"refusing to overwrite non-empty directory without --force: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def pull_apks(package: str, apk_dir: Path, force: bool, serial: str | None) -> list[Path]:
    prepare_dir(apk_dir, force)
    proc = run(adb_cmd(["shell", "pm", "path", package], serial))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"pm path failed for {package}")

    remote_paths = [
        line.removeprefix("package:").strip()
        for line in proc.stdout.splitlines()
        if line.strip().startswith("package:")
    ]
    if not remote_paths:
        raise RuntimeError(f"no APK paths found for {package}")

    local_paths = []
    for remote in remote_paths:
        local = apk_dir / Path(remote).name
        pull = run(adb_cmd(["pull", remote, str(local)], serial))
        if pull.returncode != 0:
            raise RuntimeError(pull.stderr.strip() or f"adb pull failed for {remote}")
        local_paths.append(local)
    return local_paths


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (dest_dir / member.filename).resolve()
            if target != dest_resolved and not str(target).startswith(str(dest_resolved) + str(Path("/"))):
                raise RuntimeError(f"refusing unsafe zip path: {member.filename}")
            archive.extract(member, dest_dir)


def collect_local_inputs(path: Path, work_dir: Path, force: bool) -> list[Path]:
    suffix = path.suffix.lower()
    if path.is_file() and suffix in {".apk", ".jar", ".aar"}:
        return [path]
    if path.is_file() and suffix == ".xapk":
        prepare_dir(work_dir, force)
        safe_extract_zip(path, work_dir)
        apks = sorted(work_dir.rglob("*.apk"))
        if apks:
            return apks
        raise RuntimeError(f"no APK files found inside XAPK: {path}")
    if path.is_dir():
        apks = sorted(path.glob("*.apk"))
        if apks:
            return apks
    raise RuntimeError(f"no supported APK/XAPK/JAR/AAR input found in {path}")


def run_jadx(apks: list[Path], jadx_dir: Path, force: bool, mode: str, deobf: bool, timeout: int | None = None) -> int:
    prepare_dir(jadx_dir, force)
    cmd = ["jadx", "-d", str(jadx_dir), "--show-bad-code"]
    if mode != "auto":
        cmd.extend(["--decompilation-mode", mode])
    if deobf:
        cmd.append("--deobf")
    cmd.extend(map(str, apks))
    proc = run(cmd, timeout=timeout)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    # Timeout: check if output is still usable
    if proc.returncode == -9:
        if (jadx_dir / "sources").is_dir() and any((jadx_dir / "sources").iterdir()):
            print("  [INFO] JADX timed out but sources/ exists; treating as partial success.", flush=True)
            return 3  # Treat as partial success
        return -9
    return proc.returncode


def run_apktool(inputs: list[Path], apktool_dir: Path, force: bool, framework_dir: Path | None) -> str:
    prepare_dir(apktool_dir, force)
    frame_dir = framework_dir or apktool_dir / "framework"
    frame_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    decoded = 0
    for input_path in inputs:
        if input_path.suffix.lower() != ".apk":
            continue
        out_dir = apktool_dir / safe_alias(input_path.stem)
        proc = run(["apktool", "d", "-f", "-p", str(frame_dir), str(input_path), "-o", str(out_dir)])
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if proc.returncode == 0 and out_dir.exists():
            decoded += 1
        else:
            failures.append(f"{input_path.name}: apktool exit {proc.returncode}")

    if failures and decoded:
        return "partial: " + "; ".join(failures[:5])
    if failures:
        return "failed: " + "; ".join(failures[:5])
    if decoded:
        return "ok"
    return "skipped: no APK inputs"


def run_vineflower(inputs: list[Path], vineflower_dir: Path, force: bool) -> str:
    prepare_dir(vineflower_dir, force)
    dex2jar = require_any_tool(["d2j-dex2jar.sh", "d2j-dex2jar", "dex2jar"])
    vineflower = require_any_tool(["vineflower"])

    jar_dir = vineflower_dir / "jars"
    source_root = vineflower_dir / "sources"
    extract_root = vineflower_dir / "extracted"
    jar_dir.mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    jars: list[Path] = []
    failures: list[str] = []
    for input_path in inputs:
        suffix = input_path.suffix.lower()
        if suffix == ".jar":
            jars.append(input_path)
            continue
        if suffix == ".aar":
            aar_dir = extract_root / safe_alias(input_path.stem)
            aar_dir.mkdir(parents=True, exist_ok=True)
            safe_extract_zip(input_path, aar_dir)
            classes_jar = aar_dir / "classes.jar"
            if classes_jar.exists():
                jars.append(classes_jar)
            else:
                failures.append(f"{input_path.name}: no classes.jar in AAR")
            continue

        jar_path = jar_dir / f"{safe_alias(input_path.stem)}.jar"
        dex = run([dex2jar, "-f", "-o", str(jar_path), str(input_path)])
        if dex.stdout:
            print(dex.stdout, end="")
        if dex.stderr:
            print(dex.stderr, end="", file=sys.stderr)
        if dex.returncode == 0 and jar_path.exists():
            jars.append(jar_path)
        else:
            failures.append(f"{input_path.name}: dex2jar exit {dex.returncode}")

    for jar in jars:
        out_dir = source_root / safe_alias(jar.stem)
        out_dir.mkdir(parents=True, exist_ok=True)
        vf = run([vineflower, str(jar), str(out_dir)])
        if vf.stdout:
            print(vf.stdout, end="")
        if vf.stderr:
            print(vf.stderr, end="", file=sys.stderr)
        if vf.returncode != 0:
            failures.append(f"{jar.name}: vineflower exit {vf.returncode}")

    if failures and jars:
        return "partial: " + "; ".join(failures[:5])
    if failures:
        return "failed: " + "; ".join(failures[:5])
    return "ok"


def manifest_package(jadx_dir: Path) -> str | None:
    manifest = jadx_dir / "resources" / "AndroidManifest.xml"
    if not manifest.exists():
        return None
    text = manifest.read_text(errors="ignore")
    match = re.search(r'\bpackage="([^"]+)"', text)
    return match.group(1) if match else None


def run_apkid(inputs: list[Path]) -> str:
    apkid = shutil.which("apkid")
    if not apkid:
        return "skipped: apkid not installed"
    targets = [str(p) for p in inputs if p.suffix.lower() == ".apk"]
    if not targets:
        return "skipped: no APK inputs"
    proc = run(["apkid"] + targets)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode == 0:
        return "ok"
    return f"partial: exit {proc.returncode}"


def run_apkleaks(inputs: list[Path], output_dir: Path, timeout: int | None = None) -> tuple[Path | None, str]:
    apkleaks = shutil.which("apkleaks")
    if not apkleaks:
        return None, "skipped: apkleaks not installed"
    targets = [p for p in inputs if p.suffix.lower() == ".apk"]
    if not targets:
        return None, "skipped: no APK inputs"
    report = output_dir / "apkleaks-report.txt"
    proc = run(["apkleaks", "-f", str(targets[0]), "-o", str(report)], timeout=timeout)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode == -9:
        if report.exists() and report.stat().st_size > 0:
            return report, "partial: timed out but report exists"
        return None, f"failed: timed out after {timeout}s"
    if proc.returncode == 0 and report.exists():
        return report, "ok"
    return None, f"failed: exit {proc.returncode}"


def process_app(
    spec: AppSpec,
    base_out: Path,
    flat: bool,
    force: bool,
    serial: str | None,
    with_vineflower: bool,
    with_apktool: bool,
    apktool_framework_dir: Path | None,
    with_apkid: bool,
    with_apkleaks: bool,
    jadx_mode: str,
    jadx_deobf: bool,
    parallel: bool = False,
    jadx_timeout: int | None = None,
    apkleaks_timeout: int | None = None,
) -> AppResult:
    apk_dir, jadx_dir = output_dirs(base_out, spec.alias, flat)

    if spec.apk_path:
        work_dir = base_out / spec.alias / "extracted"
        apks = collect_local_inputs(spec.apk_path, work_dir, force)
        package = spec.alias
        apk_dir = spec.apk_path if spec.apk_path.is_dir() else spec.apk_path.parent
    else:
        package = resolve_package(spec, serial)
        apks = pull_apks(package, apk_dir, force, serial)

    # --- Parallel execution: JADX runs concurrently with apktool/APKiD/apkleaks ---
    apktool_dir = None
    apktool_status = None
    vineflower_dir = None
    vineflower_status = None
    apkid_status = None
    apkleaks_report = None
    apkleaks_status = None

    if parallel and (with_apktool or with_apkid or with_apkleaks):
        futures: dict[str, concurrent.futures.Future] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit JADX
            futures["jadx"] = executor.submit(
                run_jadx, apks, jadx_dir, force, jadx_mode, jadx_deobf, jadx_timeout
            )
            # Submit apktool (does not depend on JADX)
            if with_apktool:
                apktool_dir = base_out / f"{spec.alias}_apktool" if flat else base_out / spec.alias / "apktool"
                futures["apktool"] = executor.submit(
                    run_apktool, apks, apktool_dir, force, apktool_framework_dir
                )
            # Submit APKiD (does not depend on JADX)
            if with_apkid:
                futures["apkid"] = executor.submit(run_apkid, apks)
            # Submit apkleaks (does not depend on JADX)
            if with_apkleaks:
                report_dir = base_out / spec.alias if not flat else base_out
                report_dir.mkdir(parents=True, exist_ok=True)
                futures["apkleaks"] = executor.submit(
                    run_apkleaks, apks, report_dir, apkleaks_timeout
                )

        # Collect results
        jadx_exit = futures["jadx"].result()
        if "apktool" in futures:
            apktool_status = futures["apktool"].result()
        if "apkid" in futures:
            apkid_status = futures["apkid"].result()
        if "apkleaks" in futures:
            apkleaks_report, apkleaks_status = futures["apkleaks"].result()
    else:
        # Sequential execution (original behavior)
        jadx_exit = run_jadx(apks, jadx_dir, force, jadx_mode, jadx_deobf, jadx_timeout)
        if with_apktool:
            apktool_dir = base_out / f"{spec.alias}_apktool" if flat else base_out / spec.alias / "apktool"
            apktool_status = run_apktool(apks, apktool_dir, force, apktool_framework_dir)
        if with_apkid:
            apkid_status = run_apkid(apks)
        if with_apkleaks:
            report_dir = base_out / spec.alias if not flat else base_out
            report_dir.mkdir(parents=True, exist_ok=True)
            apkleaks_report, apkleaks_status = run_apkleaks(apks, report_dir, apkleaks_timeout)

    # Vineflower depends on JADX completing (uses same DEX inputs but runs after)
    if with_vineflower:
        vineflower_dir = base_out / f"{spec.alias}_vineflower" if flat else base_out / spec.alias / "vineflower"
        vineflower_status = run_vineflower(apks, vineflower_dir, force)

    # Fallback: if apkleaks failed/timed out but JADX output exists, use find_static_anchors
    if with_apkleaks and apkleaks_status and "failed" in apkleaks_status:
        jadx_sources = jadx_dir / "sources"
        if jadx_sources.is_dir() and any(jadx_sources.iterdir()):
            script_dir = Path(__file__).resolve().parent
            fallback_script = script_dir / "find_static_anchors.py"
            if fallback_script.exists():
                print("  [FALLBACK] apkleaks failed; running find_static_anchors.py on JADX output...", flush=True)
                fb_proc = run([sys.executable, str(fallback_script), str(jadx_sources), "--urls", "--auth"])
                if fb_proc.stdout:
                    report_dir = base_out / spec.alias if not flat else base_out
                    report_dir.mkdir(parents=True, exist_ok=True)
                    fallback_report = report_dir / "static-anchors-fallback.txt"
                    fallback_report.write_text(fb_proc.stdout)
                    apkleaks_report = fallback_report
                    apkleaks_status += "; fallback find_static_anchors.py ok"

    manifest_pkg = manifest_package(jadx_dir)
    if manifest_pkg:
        package = manifest_pkg

    resource_optional = bool(
        spec.apk_path
        and spec.apk_path.is_file()
        and spec.apk_path.suffix.lower() in {".jar", ".aar"}
    )
    has_core = (jadx_dir / "sources").is_dir() and (
        resource_optional or (jadx_dir / "resources").is_dir()
    )
    if jadx_exit == 0 and has_core:
        status = "ok"
    elif jadx_exit == 3 and has_core:
        status = "partial-jadx-errors"
    else:
        status = f"failed-exit-{jadx_exit}"

    return AppResult(
        alias=spec.alias,
        package=package,
        apk_dir=apk_dir,
        jadx_dir=jadx_dir,
        apktool_dir=apktool_dir,
        apktool_status=apktool_status,
        vineflower_dir=vineflower_dir,
        vineflower_status=vineflower_status,
        apkid_status=apkid_status,
        apkleaks_report=apkleaks_report,
        apkleaks_status=apkleaks_status,
        apk_count=len(apks),
        jadx_exit=jadx_exit,
        manifest_package=manifest_pkg,
        status=status,
    )


def print_summary(results: list[AppResult], failures: list[tuple[str, str]]) -> None:
    print()
    show_apktool = any(result.apktool_dir for result in results)
    show_vineflower = any(result.vineflower_dir for result in results)
    headers = ["App", "Package", "APKs", "APK dir", "JADX dir"]
    if show_apktool:
        headers.append("Apktool dir")
    if show_vineflower:
        headers.append("Vineflower dir")
    headers.append("Status")
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---:" if header == "APKs" else "---" for header in headers) + "|")
    for result in results:
        status = f"{result.status} (jadx {result.jadx_exit})"
        if result.apktool_status:
            status = f"{status}; apktool {result.apktool_status}"
        if result.vineflower_status:
            status = f"{status}; vineflower {result.vineflower_status}"
        if result.apkid_status:
            status = f"{status}; apkid {result.apkid_status}"
        if result.apkleaks_status:
            status = f"{status}; apkleaks {result.apkleaks_status}"
        row = [
            result.alias,
            f"`{result.package}`",
            str(result.apk_count),
            f"`{result.apk_dir}`",
            f"`{result.jadx_dir}`",
        ]
        if show_apktool:
            row.append(f"`{result.apktool_dir}`" if result.apktool_dir else "-")
        if show_vineflower:
            row.append(f"`{result.vineflower_dir}`" if result.vineflower_dir else "-")
        row.append(status)
        print("| " + " | ".join(row) + " |")
    for alias, error in failures:
        row = [alias, "-", "0", "-", "-"]
        if show_apktool:
            row.append("-")
        if show_vineflower:
            row.append("-")
        row.append(f"failed: {error}")
        print("| " + " | ".join(row) + " |")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Export Android app packages and run static reverse-analysis tools."
    )
    parser.add_argument("apps", nargs="+", help="app alias, package ID, alias=package, alias=/path/to/apks, or local APK/XAPK/JAR/AAR path")
    parser.add_argument("--out", default=None, help="output root; default is <system-temp-dir>/android-static-app-reverse-<timestamp>")
    parser.add_argument("--flat", action="store_true", help="write <out>/<alias>_apks and <out>/<alias>_jadx")
    parser.add_argument("--force", action="store_true", help="replace non-empty output dirs")
    parser.add_argument("--with-apktool", action="store_true", help="also decode APK resources, manifest, and smali with apktool")
    parser.add_argument("--apktool-framework-dir", default=None, help="writable apktool framework directory; default is <apktool-output>/framework")
    parser.add_argument("--with-vineflower", action="store_true", help="also run dex2jar + Vineflower into a sibling output dir")
    parser.add_argument("--with-apkid", action="store_true", help="run APKiD for packer/compiler/obfuscator fingerprinting")
    parser.add_argument("--with-apkleaks", action="store_true", help="run apkleaks for secret/URL leak detection")
    parser.add_argument("--jadx-mode", choices=["auto", "restructure", "simple", "fallback"], default="auto", help="JADX decompilation mode; fallback is useful when higher-level Java output is suspect")
    parser.add_argument("--jadx-deobf", action="store_true", help="enable JADX deobfuscation; report that names may be rewritten")
    parser.add_argument("--parallel", action="store_true", help="run JADX, apktool, APKiD, and apkleaks in parallel (default: sequential)")
    parser.add_argument("--timeout", type=int, default=None, help="default timeout in seconds for JADX and apkleaks (overridden by specific --jadx-timeout/--apkleaks-timeout)")
    parser.add_argument("--jadx-timeout", type=int, default=None, help="timeout in seconds for JADX decompilation; recommended 600 for large APKs")
    parser.add_argument("--apkleaks-timeout", type=int, default=None, help="timeout in seconds for apkleaks; recommended 300 for large APKs")
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL"), help="ADB device serial; defaults to ANDROID_SERIAL when set")
    args = parser.parse_args(argv)

    # Resolve timeouts: specific overrides general
    jadx_timeout = args.jadx_timeout or args.timeout
    apkleaks_timeout = args.apkleaks_timeout or args.timeout

    require_tool("jadx")
    if args.with_apktool:
        require_tool("apktool")
    if args.with_vineflower:
        require_any_tool(["d2j-dex2jar.sh", "d2j-dex2jar", "dex2jar"])
        require_any_tool(["vineflower"])
    parsed = [parse_spec(app) for app in args.apps]
    if any(not spec.apk_path for spec in parsed):
        require_tool("adb")
        ensure_adb_device(args.serial)

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base_out = Path(args.out or Path(tempfile.gettempdir()) / f"android-static-app-reverse-{timestamp}").expanduser().resolve()
    base_out.mkdir(parents=True, exist_ok=True)
    apktool_framework_dir = Path(args.apktool_framework_dir).expanduser().resolve() if args.apktool_framework_dir else None

    results: list[AppResult] = []
    failures: list[tuple[str, str]] = []
    for spec in parsed:
        print(f"\n== {spec.alias} ==")
        try:
            results.append(
                process_app(
                    spec,
                    base_out,
                    args.flat,
                    args.force,
                    args.serial,
                    args.with_vineflower,
                    args.with_apktool,
                    apktool_framework_dir,
                    args.with_apkid,
                    args.with_apkleaks,
                    args.jadx_mode,
                    args.jadx_deobf,
                    parallel=args.parallel,
                    jadx_timeout=jadx_timeout,
                    apkleaks_timeout=apkleaks_timeout,
                )
            )
        except Exception as exc:
            failures.append((spec.alias, str(exc)))
            print(f"ERROR: {spec.alias}: {exc}", file=sys.stderr)

    print_summary(results, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
