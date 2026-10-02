"""Effects — Echo, Chorus, Tremolo, Vibrato, EQ/Tone Shape, Bitcrusher/Lo-Fi.

All 100% wet: these are utility processors applied to the whole sample, not a
dry/wet mix and not a substitute for a proper plugin in Live.
"""

from __future__ import annotations

from typing import Any

import ffmpeg_util as fu

CATEGORY = "Effects (100% wet)"


def _apply(input_path: str, fields: dict[str, Any], settings: dict[str, Any], op_label: str, build_filter):
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        source_probe = fu.probe(src, ffprobe_path)
        af, ok_message = build_filter(fields)
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, op_label, src, ".wav")
    args = ["-i", str(src), "-af", af, *fu.preserving_codec_args(source_probe), str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, ok_message)


def _build_echo(fields: dict[str, Any]) -> tuple[str, str]:
    delay_ms = fu.parse_float_field(fields.get("delay_ms") or "500", "Delay", 500.0)
    decay = fu.parse_float_field(fields.get("decay") or "0.5", "Decay", 0.5)
    if not (0 < decay < 1):
        raise ValueError("Decay must be between 0 and 1.")
    return "aecho=0.6:0.3:%g:%g" % (delay_ms, decay), "Echo applied (%gms, decay %g)." % (delay_ms, decay)


def _build_chorus(fields: dict[str, Any]) -> tuple[str, str]:
    depth = fu.parse_float_field(fields.get("depth") or "1", "Depth", 1.0)
    rate = fu.parse_float_field(fields.get("rate") or "1", "Rate", 1.0)
    decays = "|".join("%.3f" % (v * depth) for v in (0.4, 0.32, 0.3))
    speeds = "|".join("%.3f" % (v * rate) for v in (0.25, 0.4, 0.3))
    return (
        "chorus=0.6:0.9:50|60|40:%s:%s:2|2.3|1.3" % (decays, speeds),
        "Chorus applied (depth %g, rate %g)." % (depth, rate),
    )


def _build_tremolo(fields: dict[str, Any]) -> tuple[str, str]:
    freq = fu.parse_float_field(fields.get("frequency") or "5", "Frequency", 5.0)
    depth = fu.parse_float_field(fields.get("depth") or "0.5", "Depth", 0.5)
    if not (0 <= depth <= 1):
        raise ValueError("Depth must be between 0 and 1.")
    return "tremolo=f=%g:d=%g" % (freq, depth), "Tremolo applied (%gHz, depth %g)." % (freq, depth)


def _build_vibrato(fields: dict[str, Any]) -> tuple[str, str]:
    freq = fu.parse_float_field(fields.get("frequency") or "5", "Frequency", 5.0)
    depth = fu.parse_float_field(fields.get("depth") or "0.5", "Depth", 0.5)
    if not (0 <= depth <= 1):
        raise ValueError("Depth must be between 0 and 1.")
    return "vibrato=f=%g:d=%g" % (freq, depth), "Vibrato applied (%gHz, depth %g)." % (freq, depth)


def _build_eq(fields: dict[str, Any]) -> tuple[str, str]:
    stages = []
    labels = []

    highpass_raw = str(fields.get("highpass_hz") or "").strip()
    if highpass_raw:
        hp = fu.parse_float_field(highpass_raw, "Highpass")
        stages.append("highpass=f=%g" % hp)
        labels.append("highpass %gHz" % hp)

    lowpass_raw = str(fields.get("lowpass_hz") or "").strip()
    if lowpass_raw:
        lp = fu.parse_float_field(lowpass_raw, "Lowpass")
        stages.append("lowpass=f=%g" % lp)
        labels.append("lowpass %gHz" % lp)

    bass_db = fu.parse_float_field(fields.get("bass_db") or "0", "Bass", 0.0)
    if bass_db != 0:
        stages.append("bass=g=%g" % bass_db)
        labels.append("bass %+gdB" % bass_db)

    treble_db = fu.parse_float_field(fields.get("treble_db") or "0", "Treble", 0.0)
    if treble_db != 0:
        stages.append("treble=g=%g" % treble_db)
        labels.append("treble %+gdB" % treble_db)

    if not stages:
        raise ValueError("Set at least one of highpass, lowpass, bass, or treble.")
    return ",".join(stages), "EQ applied: %s." % ", ".join(labels)


def _build_bitcrush(fields: dict[str, Any]) -> tuple[str, str]:
    bits = fu.parse_float_field(fields.get("bits") or "8", "Bits", 8.0)
    mix = fu.parse_float_field(fields.get("mix") or "0.5", "Mix", 0.5)
    sample_reduction = fu.parse_float_field(fields.get("sample_reduction") or "1", "Sample reduction", 1.0)
    if not (1 <= bits <= 64):
        raise ValueError("Bits must be between 1 and 64.")
    if not (0 <= mix <= 1):
        raise ValueError("Mix must be between 0 and 1.")
    if not (1 <= sample_reduction <= 250):
        raise ValueError("Sample reduction must be between 1 and 250.")
    return (
        "acrusher=bits=%g:mix=%g:samples=%g" % (bits, mix, sample_reduction),
        "Bitcrushed (%g-bit, mix %g)." % (bits, mix),
    )


OPS = [
    {
        "id": "echo",
        "name": "Echo / Delay",
        "description": "Add a single echo tap.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "delay_ms", "label": "Delay (ms)", "type": "text", "default": "500"},
            {"id": "decay", "label": "Decay (0-1)", "type": "text", "default": "0.5"},
        ],
        "run": lambda ip, f, s: _apply(ip, f, s, "Echo", _build_echo),
    },
    {
        "id": "chorus",
        "name": "Chorus",
        "description": "3-voice chorus.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "depth", "label": "Depth", "type": "text", "default": "1", "hint": "Multiplier, 1 = ffmpeg default"},
            {"id": "rate", "label": "Rate", "type": "text", "default": "1", "hint": "Multiplier, 1 = ffmpeg default"},
        ],
        "run": lambda ip, f, s: _apply(ip, f, s, "Chorus", _build_chorus),
    },
    {
        "id": "tremolo",
        "name": "Tremolo",
        "description": "Amplitude modulation.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "frequency", "label": "Frequency (Hz)", "type": "text", "default": "5"},
            {"id": "depth", "label": "Depth (0-1)", "type": "text", "default": "0.5"},
        ],
        "run": lambda ip, f, s: _apply(ip, f, s, "Tremolo", _build_tremolo),
    },
    {
        "id": "vibrato",
        "name": "Vibrato",
        "description": "Pitch modulation.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "frequency", "label": "Frequency (Hz)", "type": "text", "default": "5"},
            {"id": "depth", "label": "Depth (0-1)", "type": "text", "default": "0.5"},
        ],
        "run": lambda ip, f, s: _apply(ip, f, s, "Vibrato", _build_vibrato),
    },
    {
        "id": "eq",
        "name": "EQ / Tone Shape",
        "description": "Highpass, lowpass, bass, and treble shaping.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "highpass_hz", "label": "Highpass cutoff (Hz)", "type": "text", "default": "", "hint": "Blank = off"},
            {"id": "lowpass_hz", "label": "Lowpass cutoff (Hz)", "type": "text", "default": "", "hint": "Blank = off"},
            {"id": "bass_db", "label": "Bass gain (dB)", "type": "text", "default": "0"},
            {"id": "treble_db", "label": "Treble gain (dB)", "type": "text", "default": "0"},
        ],
        "run": lambda ip, f, s: _apply(ip, f, s, "EQ", _build_eq),
    },
    {
        "id": "bitcrush",
        "name": "Bitcrusher / Lo-Fi",
        "description": "Reduce bit resolution and sample rate for a lo-fi/crushed texture.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "bits", "label": "Bits", "type": "text", "default": "8", "hint": "1-64, lower = crunchier"},
            {"id": "mix", "label": "Mix", "type": "text", "default": "0.5", "hint": "0-1"},
            {"id": "sample_reduction", "label": "Sample reduction", "type": "text", "default": "1", "hint": "1-250, higher = more aliasing"},
        ],
        "run": lambda ip, f, s: _apply(ip, f, s, "Bitcrush", _build_bitcrush),
    },
]
