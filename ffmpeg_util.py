"""Shared ffmpeg/ffprobe plumbing used by every op in ops/.

Kept UI-agnostic on purpose: no Tkinter, no file dialogs. Ops call these
helpers and return plain {ok, message, path} dicts; the Tkinter app in
audio_sample_tool.py is the only place that talks to the user.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any


class FfmpegError(RuntimeError):
    """A failure with a message that is safe to show directly to the user."""


DEFAULT_TIMEOUT = 900  # seconds. Two-pass loudnorm and rubberband pitch/time-stretch on a
                        # long file can each burn several minutes; 120s was too tight.


# ── locating the binaries ───────────────────────────────────────────────────

def resolve_ffmpeg(settings: dict[str, Any]) -> str:
    configured = str(settings.get("ffmpeg_path") or "").strip()
    if configured:
        path = Path(configured)
        if path.is_dir():
            candidate = path / "ffmpeg.exe"
            if candidate.is_file():
                return str(candidate)
        if not path.is_file():
            raise FfmpegError('ffmpeg_path "%s" is not a file. Fix it in Settings.' % configured)
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FfmpegError("ffmpeg not found. Set ffmpeg_path in Settings or add ffmpeg to PATH.")


def resolve_ffprobe(settings: dict[str, Any]) -> str:
    configured = str(settings.get("ffmpeg_path") or "").strip()
    if configured:
        candidate = Path(configured).with_name(Path(configured).name.replace("ffmpeg", "ffprobe"))
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FfmpegError("ffprobe not found. Set ffmpeg_path in Settings or add ffmpeg to PATH.")


# ── running commands ─────────────────────────────────────────────────────────

def run_ffmpeg(ffmpeg_path: str, args: list[str], timeout: int = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([ffmpeg_path, "-y", *args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FfmpegError("ffmpeg timed out after %ds. The file may be very long, or something is stuck." % timeout)
    except OSError as exc:
        raise FfmpegError("Could not run ffmpeg at %s: %s" % (ffmpeg_path, exc))


def run_ffprobe(ffprobe_path: str, args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([ffprobe_path, *args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FfmpegError("ffprobe timed out after %ds." % timeout)
    except OSError as exc:
        raise FfmpegError("Could not run ffprobe at %s: %s" % (ffprobe_path, exc))


def ffmpeg_error(result: subprocess.CompletedProcess) -> str:
    text = (result.stderr or b"").decode("utf-8", "replace").strip()
    return text[-500:] if text else "ffmpeg exited with code %d and no error output." % result.returncode


# ── probing source format so ops can preserve it ────────────────────────────

def probe(path: Path, ffprobe_path: str) -> dict[str, Any]:
    result = run_ffprobe(
        ffprobe_path,
        ["-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
    )
    if result.returncode != 0:
        raise FfmpegError("Could not read %s: %s" % (path.name, ffmpeg_error(result)))
    try:
        data = json.loads(result.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise FfmpegError("Could not parse ffprobe output for %s: %s" % (path.name, exc)) from exc

    audio_stream = next((s for s in data.get("streams") or [] if s.get("codec_type") == "audio"), None)
    if audio_stream is None:
        raise FfmpegError("%s has no audio stream." % path.name)

    fmt = data.get("format") or {}
    duration = fmt.get("duration") or audio_stream.get("duration")
    sample_rate = audio_stream.get("sample_rate")
    channels = audio_stream.get("channels")
    bits = audio_stream.get("bits_per_raw_sample") or audio_stream.get("bits_per_sample")
    return {
        "sample_rate": int(sample_rate) if sample_rate else None,
        "channels": int(channels) if channels else None,
        "sample_fmt": audio_stream.get("sample_fmt"),
        "bits_per_raw_sample": int(bits) if bits else None,
        "codec_name": audio_stream.get("codec_name"),
        "duration": float(duration) if duration else None,
    }


def preserving_codec_args(source_probe: dict[str, Any]) -> list[str]:
    """-c:a args that keep the source's bit depth instead of ffmpeg's WAV default.

    Deliberately does not touch -ar/-ac — sample rate and channel count pass
    through unchanged unless an op explicitly resamples/remixes.
    """
    sample_fmt = str(source_probe.get("sample_fmt") or "").lower()
    bits = source_probe.get("bits_per_raw_sample")

    if sample_fmt in ("s16", "s16p"):
        return ["-c:a", "pcm_s16le"]
    if sample_fmt in ("s32", "s32p"):
        if bits and int(bits) <= 24:
            return ["-c:a", "pcm_s24le"]
        return ["-c:a", "pcm_s32le"]
    if sample_fmt in ("flt", "fltp", "dbl", "dblp"):
        return ["-c:a", "pcm_f32le"]
    # Unknown / compressed source (mp3, etc.) — 24-bit is a safe, lossless-enough default.
    return ["-c:a", "pcm_s24le"]


# ── time field parsing ───────────────────────────────────────────────────────

def parse_time(text: str) -> float:
    """Accepts "SS(.ms)", "MM:SS(.ms)", or "HH:MM:SS(.ms)". Raises ValueError otherwise."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Time is required.")
    parts = raw.split(":")
    if len(parts) > 3:
        raise ValueError('Time "%s" is not valid. Use seconds, mm:ss, or hh:mm:ss.' % raw)
    try:
        parts_f = [float(p) for p in parts]
    except ValueError:
        raise ValueError('Time "%s" is not a number. Use seconds, mm:ss, or hh:mm:ss.' % raw)
    if any(p < 0 for p in parts_f):
        raise ValueError('Time "%s" cannot be negative.' % raw)
    if len(parts_f) >= 2 and any(p != int(p) for p in parts_f[:-1]):
        raise ValueError('Time "%s": only the final seconds segment may have a decimal.' % raw)
    seconds = 0.0
    for part in parts_f:
        seconds = seconds * 60 + part
    return seconds


def parse_optional_time(text: str) -> float | None:
    raw = (text or "").strip()
    return parse_time(raw) if raw else None


def parse_float_field(text: str, label: str, default: float | None = None) -> float:
    raw = (text or "").strip()
    if not raw:
        if default is not None:
            return default
        raise ValueError("%s is required." % label)
    try:
        return float(raw)
    except ValueError:
        raise ValueError('%s "%s" is not a number.' % (label, raw))


# ── small helpers every op reuses ───────────────────────────────────────────

def require_input(input_path: str | Path | None) -> Path:
    if not input_path:
        raise FfmpegError("No input file selected.")
    resolved = Path(input_path)
    if not resolved.is_file():
        raise FfmpegError("Input file not found: %s" % resolved)
    return resolved


def finish(ffmpeg_path: str, args: list[str], out_path: Path, ok_message: str) -> dict[str, Any]:
    """Run ffmpeg, and turn the result into the {ok, message, path} shape every op returns."""
    try:
        result = run_ffmpeg(ffmpeg_path, args)
    except FfmpegError as exc:
        out_path.unlink(missing_ok=True)  # don't leave the reserved-name stub behind
        return {"ok": False, "message": str(exc)}
    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        return {"ok": False, "message": "ffmpeg failed: %s" % ffmpeg_error(result)}
    return {"ok": True, "message": ok_message, "path": str(out_path)}


# ── output paths ─────────────────────────────────────────────────────────────

_NAME_LOCK = threading.Lock()
_SAFE_RE = re.compile(r"[^A-Za-z0-9]+")


def resolve_output_dir(settings: dict[str, Any]) -> Path:
    configured = str(settings.get("audio_sample_output_dir") or "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "output"


def next_output_path(out_dir: Path, op_label: str, source_path: Path | None, ext: str) -> Path:
    """Friendly numbered output name: <Op>-<SourceStem>-N.ext (or <Op>-Sample-N.ext)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_label = _SAFE_RE.sub("", op_label) or "Output"
    safe_stem = _SAFE_RE.sub("", source_path.stem) if source_path else ""
    stem = safe_stem or "Sample"
    prefix = "%s-%s-" % (safe_label, stem)
    pattern = re.compile(r"^%s(\d+)%s$" % (re.escape(prefix), re.escape(ext)))

    with _NAME_LOCK:
        highest = 0
        for existing in out_dir.glob("%s*%s" % (prefix, ext)):
            m = pattern.match(existing.name)
            if m:
                highest = max(highest, int(m.group(1)))
        path = out_dir / ("%s%d%s" % (prefix, highest + 1, ext))
        path.touch()  # reserve the name so two quick Runs never collide
        return path
