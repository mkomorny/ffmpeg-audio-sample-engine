"""Trim, Fades & Levels — trim/cut, auto-trim silence, fade in/out, gain, normalize."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ffmpeg_util as fu

CATEGORY = "Trim, Fades & Levels"


def _run_trim(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        start = fu.parse_time(fields.get("start") or "0")
        end = fu.parse_optional_time(fields.get("end") or "")
        if end is not None and end <= start:
            raise ValueError("End time must be after start time.")
        source_probe = fu.probe(src, ffprobe_path)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Trim", src, ".wav")

    args = ["-ss", str(start), "-i", str(src)]
    if end is not None:
        args += ["-t", str(end - start)]
    args += [*fu.preserving_codec_args(source_probe), str(out_path)]
    message = "Trimmed to %.3fs." % (end - start) if end is not None else "Trimmed from %.3fs to end of file." % start
    return fu.finish(ffmpeg_path, args, out_path, message)


def _run_autotrim(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        threshold = fu.parse_float_field(fields.get("threshold_db") or "-40", "Threshold", -40.0)
        min_silence = fu.parse_time(fields.get("min_silence") or "0.3")
        sides = str(fields.get("sides") or "Both").strip().lower()
        source_probe = fu.probe(src, ffprobe_path)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    start_stage = "silenceremove=start_periods=1:start_threshold=%gdB:start_silence=%g:detection=peak" % (
        threshold, min_silence,
    )
    if sides == "start only":
        chain = start_stage
    elif sides == "end only":
        chain = "areverse,%s,areverse" % start_stage
    else:
        chain = "%s,areverse,%s,areverse" % (start_stage, start_stage)

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "AutoTrim", src, ".wav")
    args = ["-i", str(src), "-af", chain, *fu.preserving_codec_args(source_probe), str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Silence trimmed (%s)." % sides)


def _run_fades(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        fade_in = fu.parse_time(fields.get("fade_in") or "0")
        fade_out = fu.parse_time(fields.get("fade_out") or "0")
        curve = str(fields.get("curve") or "tri").strip() or "tri"
        source_probe = fu.probe(src, ffprobe_path)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    duration = source_probe.get("duration")
    if fade_out > 0 and not duration:
        return {"ok": False, "message": "Could not read source duration; cannot place a fade-out."}
    if fade_out > 0 and fade_in + fade_out > duration:
        return {"ok": False, "message": "Fade in + fade out is longer than the file (%.3fs)." % duration}

    stages = []
    if fade_in > 0:
        stages.append("afade=t=in:st=0:d=%g:curve=%s" % (fade_in, curve))
    if fade_out > 0:
        stages.append("afade=t=out:st=%g:d=%g:curve=%s" % (duration - fade_out, fade_out, curve))
    if not stages:
        return {"ok": False, "message": "Set a fade-in and/or fade-out duration greater than 0."}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Fade", src, ".wav")
    args = ["-i", str(src), "-af", ",".join(stages), *fu.preserving_codec_args(source_probe), str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Faded.")


def _run_gain(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        db = fu.parse_float_field(fields.get("db") or "0", "Gain")
        source_probe = fu.probe(src, ffprobe_path)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Gain", src, ".wav")
    args = ["-i", str(src), "-af", "volume=%gdB" % db, *fu.preserving_codec_args(source_probe), str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Gain applied: %+gdB." % db)


def _measure_peak(ffmpeg_path: str, src: Path) -> float:
    result = fu.run_ffmpeg(ffmpeg_path, ["-i", str(src), "-af", "volumedetect", "-f", "null", "-"])
    stderr = (result.stderr or b"").decode("utf-8", "replace")
    for line in stderr.splitlines():
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].strip().split(" ")[0])
            except (IndexError, ValueError):
                pass
    raise fu.FfmpegError("Could not measure peak volume.")


def _run_normalize(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        mode = str(fields.get("mode") or "LUFS").strip().lower()
        source_probe = fu.probe(src, ffprobe_path)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    codec_args = fu.preserving_codec_args(source_probe)
    # loudnorm (and, harmlessly, volumedetect's measurement pass) can hand back audio
    # resampled for internal true-peak analysis — pin -ar back to the source rate so the
    # output file doesn't silently end up at e.g. 192000 Hz.
    rate_args = ["-ar", str(source_probe["sample_rate"])] if source_probe.get("sample_rate") else []

    if mode == "peak":
        try:
            target = fu.parse_float_field(fields.get("target") or "-1", "Target", -1.0)
            max_volume = _measure_peak(ffmpeg_path, src)
        except (fu.FfmpegError, ValueError) as exc:
            return {"ok": False, "message": str(exc)}
        gain = target - max_volume
        out_dir = fu.resolve_output_dir(settings)
        out_path = fu.next_output_path(out_dir, "Normalize", src, ".wav")
        args = ["-i", str(src), "-af", "volume=%gdB" % gain, *codec_args, *rate_args, str(out_path)]
        return fu.finish(ffmpeg_path, args, out_path, "Peak-normalized to %gdB (%+gdB gain applied)." % (target, gain))

    # LUFS — two-pass loudnorm.
    try:
        target_i = fu.parse_float_field(fields.get("target") or "-14", "Target LUFS", -14.0)
        target_tp = fu.parse_float_field(fields.get("true_peak") or "-1.5", "True peak", -1.5)
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}

    measure_filter = "loudnorm=I=%g:TP=%g:LRA=11:print_format=json" % (target_i, target_tp)
    try:
        measure = fu.run_ffmpeg(ffmpeg_path, ["-i", str(src), "-af", measure_filter, "-f", "null", "-"])
    except fu.FfmpegError as exc:
        return {"ok": False, "message": "Loudness measurement failed: %s" % exc}
    stderr = (measure.stderr or b"").decode("utf-8", "replace")
    brace_start = stderr.rfind("{")
    brace_end = stderr.find("}", brace_start) if brace_start != -1 else -1
    if measure.returncode != 0 or brace_start == -1 or brace_end == -1:
        return {"ok": False, "message": "Loudness measurement failed: %s" % fu.ffmpeg_error(measure)}
    import json
    try:
        stats = json.loads(stderr[brace_start:brace_end + 1])
    except json.JSONDecodeError:
        return {"ok": False, "message": "Could not parse loudness measurement."}

    apply_filter = (
        "loudnorm=I=%g:TP=%g:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:"
        "measured_thresh=%s:offset=%s:linear=true:print_format=summary"
    ) % (
        target_i, target_tp,
        stats.get("input_i"), stats.get("input_tp"), stats.get("input_lra"),
        stats.get("input_thresh"), stats.get("target_offset"),
    )
    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Normalize", src, ".wav")
    args = ["-i", str(src), "-af", apply_filter, *codec_args, *rate_args, str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Loudness-normalized to %g LUFS." % target_i)


OPS = [
    {
        "id": "trim",
        "name": "Trim / Cut",
        "description": "Cut the sample to a start/end time range.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "start", "label": "Start", "type": "text", "default": "0", "hint": "Seconds or mm:ss.ms"},
            {"id": "end", "label": "End", "type": "text", "default": "", "hint": "Blank = end of file"},
        ],
        "run": _run_trim,
    },
    {
        "id": "autotrim",
        "name": "Auto-Trim Silence",
        "description": "Strip leading and/or trailing silence.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "threshold_db", "label": "Silence threshold", "type": "text", "default": "-40", "hint": "dB, e.g. -40"},
            {"id": "min_silence", "label": "Minimum silence length", "type": "text", "default": "0.3", "hint": "Seconds or mm:ss.ms"},
            {"id": "sides", "label": "Trim", "type": "select", "options": ["Both", "Start only", "End only"], "default": "Both"},
        ],
        "run": _run_autotrim,
    },
    {
        "id": "fades",
        "name": "Fade In / Out",
        "description": "Fade the start and/or end of the sample.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "fade_in", "label": "Fade in", "type": "text", "default": "0", "hint": "Seconds or mm:ss.ms, 0 = none"},
            {"id": "fade_out", "label": "Fade out", "type": "text", "default": "0", "hint": "Seconds or mm:ss.ms, 0 = none"},
            {
                "id": "curve", "label": "Curve", "type": "select",
                "options": ["tri", "log", "exp", "qsin", "hsin", "esin", "par", "cub"],
                "default": "tri", "hint": "tri = linear",
            },
        ],
        "run": _run_fades,
    },
    {
        "id": "gain",
        "name": "Gain",
        "description": "Change volume by a fixed dB amount.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "db", "label": "Gain (dB)", "type": "text", "default": "0", "hint": "Positive = louder, negative = quieter"},
        ],
        "run": _run_gain,
    },
    {
        "id": "normalize",
        "name": "Normalize",
        "description": "Bring the sample to a target loudness (Peak or two-pass LUFS).",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "mode", "label": "Mode", "type": "select", "options": ["LUFS", "Peak"], "default": "LUFS"},
            {"id": "target", "label": "Target", "type": "text", "default": "-14", "hint": "LUFS mode: integrated LUFS (e.g. -14). Peak mode: dBFS ceiling (e.g. -1)."},
            {"id": "true_peak", "label": "True peak ceiling (LUFS mode)", "type": "text", "default": "-1.5", "hint": "dBTP, ignored in Peak mode"},
        ],
        "run": _run_normalize,
    },
]
