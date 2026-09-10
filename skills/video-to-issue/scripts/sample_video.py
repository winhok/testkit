#!/usr/bin/env python3
"""Extract bounded video evidence for issue drafting; extraction is not review."""
import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path


def sample(source, output, start=0, duration=10, interval=1):
    source, output = Path(source).resolve(), Path(output)
    if not source.is_file() or output.exists():
        raise ValueError("source must exist and output directory must be new")
    if not all(math.isfinite(v) for v in (start, duration, interval)) or start < 0 or duration <= 0 or interval <= 0:
        raise ValueError("invalid sampling interval")
    if duration > 300 or math.ceil(duration / interval) > 100:
        raise ValueError("sample at most 300 seconds and 100 frames per invocation")
    probe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not ffmpeg:
        raise ValueError("installed ffprobe and ffmpeg are required")
    meta = subprocess.run([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries", "format=duration:stream=codec_type,avg_frame_rate", "-of", "json", str(source)], capture_output=True, text=True, timeout=30, check=True)
    metadata = json.loads(meta.stdout)
    total = float(metadata["format"]["duration"])
    if not math.isfinite(total) or start >= total:
        raise ValueError("sample starts outside video")
    duration = min(duration, total - start)
    output.mkdir(parents=True)
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-ss", str(start), "-i", str(source), "-t", str(duration), "-vf", f"fps=1/{interval},scale=w='min(1280,iw)':h=-2", "-frames:v", "100", "-n", str(output / "frame-%04d.png")], capture_output=True, text=True, timeout=120, check=True)
    frames = sorted(output.glob("frame-*.png"))
    if not frames:
        raise ValueError("no frames extracted")
    manifest = {"schema_version": 1, "kind": "video-sample", "duration": total, "sample_start": start,
                "sample_duration": duration, "interval": interval, "frames": [p.name for p in frames],
                "reviewed": False, "limitations": ["Sampling positions are approximate; frame index is not an exact source PTS.", "Extraction does not establish that frames were visually reviewed; sparse sampling can miss transient symptoms."]}
    with (output / "sample.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--duration", type=float, default=10)
    p.add_argument("--interval", type=float, default=1)
    args = p.parse_args()
    try:
        print(json.dumps(sample(args.input, args.output_dir, args.start, args.duration, args.interval)))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Video sampling failed; any partial output is unreviewed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
