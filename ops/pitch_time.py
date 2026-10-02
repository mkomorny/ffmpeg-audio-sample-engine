"""Reverse, Pitch & Time — reverse playback, and independent pitch/tempo via rubberband."""

from __future__ import annotations

from typing import Any

import ffmpeg_util as fu

CATEGORY = "Reverse, Pitch & Time"


def _run_reverse(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        source_probe = fu.probe(src, ffprobe_path)
    except fu.FfmpegError as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Reverse", src, ".wav")
    args = ["-i", str(src), "-af", "areverse", *fu.preserving_codec_args(source_probe), str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Reversed.")


def _run_pitch_time(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        semitones = fu.parse_float_field(fields.get("semitones") or "0", "Semitones", 0.0)
        tempo_pct = fu.parse_float_field(fields.get("tempo_pct") or "100", "Tempo %", 100.0)
        if tempo_pct <= 0:
            raise ValueError("Tempo %% must be greater than 0.")
        source_probe = fu.probe(src, ffprobe_path)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    if semitones == 0 and tempo_pct == 100:
        return {"ok": False, "message": "Set a pitch shift and/or tempo change first."}

    pitch_factor = 2 ** (semitones / 12.0)
    tempo_factor = tempo_pct / 100.0

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "PitchTime", src, ".wav")
    rb_filter = "rubberband=pitch=%g:tempo=%g" % (pitch_factor, tempo_factor)
    args = ["-i", str(src), "-af", rb_filter, *fu.preserving_codec_args(source_probe), str(out_path)]
    return fu.finish(
        ffmpeg_path, args, out_path,
        "Pitch %+g semitones, tempo %g%%." % (semitones, tempo_pct),
    )


OPS = [
    {
        "id": "reverse",
        "name": "Reverse",
        "description": "Play the sample backwards.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [],
        "run": _run_reverse,
    },
    {
        "id": "pitch-time",
        "name": "Pitch & Time Stretch",
        "description": "Shift pitch and/or change tempo independently (Rubber Band).",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "semitones", "label": "Pitch shift (semitones)", "type": "text", "default": "0", "hint": "e.g. 12 = up an octave, -12 = down an octave"},
            {"id": "tempo_pct", "label": "Tempo (%)", "type": "text", "default": "100", "hint": "100 = unchanged, 50 = half speed, 200 = double speed"},
        ],
        "run": _run_pitch_time,
    },
]
