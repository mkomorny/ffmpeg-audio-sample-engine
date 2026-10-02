"""Generators — Tone, Noise, Silence. No input file; output is 48kHz/24-bit/stereo."""

from __future__ import annotations

from typing import Any

import ffmpeg_util as fu

CATEGORY = "Generators (no input file)"

_SAMPLE_RATE = 48000
_CODEC_ARGS = ["-c:a", "pcm_s24le", "-ar", str(_SAMPLE_RATE), "-ac", "2"]


def _run_tone(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        frequency = fu.parse_float_field(fields.get("frequency") or "440", "Frequency", 440.0)
        duration = fu.parse_time(fields.get("duration") or "2")
        if frequency <= 0:
            raise ValueError("Frequency must be greater than 0.")
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Tone", None, ".wav")
    src = "sine=frequency=%g:duration=%g:sample_rate=%d" % (frequency, duration, _SAMPLE_RATE)
    args = ["-f", "lavfi", "-i", src, *_CODEC_ARGS, str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Generated %gHz tone, %gs." % (frequency, duration))


def _run_noise(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        color = str(fields.get("color") or "white").strip().lower()
        if color not in ("white", "pink", "brown"):
            raise ValueError('Color must be white, pink, or brown (got "%s").' % color)
        amplitude = fu.parse_float_field(fields.get("amplitude") or "0.5", "Amplitude", 0.5)
        duration = fu.parse_time(fields.get("duration") or "2")
        if not (0 < amplitude <= 1):
            raise ValueError("Amplitude must be between 0 and 1.")
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Noise", None, ".wav")
    src = "anoisesrc=color=%s:amplitude=%g:duration=%g:sample_rate=%d" % (color, amplitude, duration, _SAMPLE_RATE)
    args = ["-f", "lavfi", "-i", src, *_CODEC_ARGS, str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Generated %s noise, %gs." % (color, duration))


def _run_silence(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        duration = fu.parse_time(fields.get("duration") or "2")
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Silence", None, ".wav")
    src = "anullsrc=channel_layout=stereo:sample_rate=%d:duration=%g" % (_SAMPLE_RATE, duration)
    args = ["-f", "lavfi", "-i", src, *_CODEC_ARGS, str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Generated %gs of silence." % duration)


OPS = [
    {
        "id": "tone",
        "name": "Tone Generator",
        "description": "Generate a sine tone from scratch.",
        "category": CATEGORY,
        "needs_input": False,
        "fields": [
            {"id": "frequency", "label": "Frequency (Hz)", "type": "text", "default": "440"},
            {"id": "duration", "label": "Duration", "type": "text", "default": "2", "hint": "Seconds or mm:ss.ms"},
        ],
        "run": _run_tone,
    },
    {
        "id": "noise",
        "name": "Noise Generator",
        "description": "Generate white, pink, or brown noise from scratch.",
        "category": CATEGORY,
        "needs_input": False,
        "fields": [
            {"id": "color", "label": "Color", "type": "select", "options": ["white", "pink", "brown"], "default": "white"},
            {"id": "amplitude", "label": "Amplitude (0-1)", "type": "text", "default": "0.5"},
            {"id": "duration", "label": "Duration", "type": "text", "default": "2", "hint": "Seconds or mm:ss.ms"},
        ],
        "run": _run_noise,
    },
    {
        "id": "silence",
        "name": "Silence Generator",
        "description": "Generate a block of silence (spacer clips, etc.).",
        "category": CATEGORY,
        "needs_input": False,
        "fields": [
            {"id": "duration", "label": "Duration", "type": "text", "default": "2", "hint": "Seconds or mm:ss.ms"},
        ],
        "run": _run_silence,
    },
]
