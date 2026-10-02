"""Convert — format, sample rate, and channel conversion in a single ffmpeg pass.

Bit depth is folded into the "Format" choice (e.g. "WAV 24-bit") rather than a
separate field, since bit depth only means something for PCM formats — a
standalone "bit depth" field would be meaningless for MP3/FLAC/OGG.
"""

from __future__ import annotations

from typing import Any

import ffmpeg_util as fu

CATEGORY = "Convert"

# label -> (extension, codec args or None to keep source format)
_FORMATS: dict[str, tuple[str, list[str] | None]] = {
    "Keep source format": (None, None),  # placeholder; resolved from source codec below
    "WAV 16-bit": (".wav", ["-c:a", "pcm_s16le"]),
    "WAV 24-bit": (".wav", ["-c:a", "pcm_s24le"]),
    "WAV 32-bit float": (".wav", ["-c:a", "pcm_f32le"]),
    "AIFF 16-bit": (".aiff", ["-c:a", "pcm_s16be"]),
    "AIFF 24-bit": (".aiff", ["-c:a", "pcm_s24be"]),
    "FLAC": (".flac", ["-c:a", "flac"]),
    "MP3": (".mp3", ["-c:a", "libmp3lame", "-q:a", "2"]),
    "OGG Vorbis": (".ogg", ["-c:a", "libvorbis", "-q:a", "5"]),
}

# codec_name (from ffprobe) -> (extension, re-encode args) for "Keep source format" when the
# source is compressed and a resample/channel change means a plain -c:a copy won't work.
_COMPRESSED_REENCODE: dict[str, tuple[str, list[str]]] = {
    "mp3": (".mp3", ["-c:a", "libmp3lame", "-q:a", "2"]),
    "vorbis": (".ogg", ["-c:a", "libvorbis", "-q:a", "5"]),
    "flac": (".flac", ["-c:a", "flac"]),
}


def _run_convert(input_path: str, fields: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    try:
        src = fu.require_input(input_path)
        ffmpeg_path = fu.resolve_ffmpeg(settings)
        ffprobe_path = fu.resolve_ffprobe(settings)
        source_probe = fu.probe(src, ffprobe_path)

        rate_raw = str(fields.get("sample_rate") or "").strip()
        rate_args: list[str] = []
        if rate_raw:
            rate = fu.parse_float_field(rate_raw, "Sample rate")
            rate_args = ["-ar", str(int(rate))]

        channels_choice = str(fields.get("channels") or "Keep source").strip().lower()
        channel_args: list[str] = []
        if channels_choice == "mono":
            channel_args = ["-ac", "1"]
        elif channels_choice == "stereo":
            channel_args = ["-ac", "2"]
        wants_transform = bool(rate_args) or bool(channel_args)

        fmt_label = str(fields.get("format") or "Keep source format").strip()
        if fmt_label not in _FORMATS:
            raise ValueError('Unknown format "%s".' % fmt_label)
        ext, codec_args = _FORMATS[fmt_label]

        if ext is None:  # "Keep source format"
            codec_name = str(source_probe.get("codec_name") or "").lower()
            if not codec_name or codec_name.startswith("pcm_"):
                # WAV/AIFF-style PCM source: a raw PCM codec fits fine in a WAV/AIFF container.
                ext = src.suffix or ".wav"
                codec_args = fu.preserving_codec_args(source_probe)
            elif codec_name in _COMPRESSED_REENCODE:
                # Compressed source (mp3/vorbis/flac): PCM can't go in this container. Stream-copy
                # when nothing else is changing; otherwise re-encode with a matching encoder.
                comp_ext, comp_codec_args = _COMPRESSED_REENCODE[codec_name]
                ext = src.suffix or comp_ext
                codec_args = comp_codec_args if wants_transform else ["-c:a", "copy"]
            else:
                raise ValueError(
                    'Cannot keep source format for codec "%s" — pick an explicit output format instead.'
                    % codec_name
                )
    except (fu.FfmpegError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    out_dir = fu.resolve_output_dir(settings)
    out_path = fu.next_output_path(out_dir, "Convert", src, ext)
    args = ["-i", str(src), *codec_args, *rate_args, *channel_args, str(out_path)]
    return fu.finish(ffmpeg_path, args, out_path, "Converted to %s." % fmt_label)


OPS = [
    {
        "id": "convert",
        "name": "Convert / Resample",
        "description": "Change format, sample rate, and/or channel count in one pass.",
        "category": CATEGORY,
        "needs_input": True,
        "fields": [
            {"id": "format", "label": "Format", "type": "select", "options": list(_FORMATS.keys()), "default": "Keep source format"},
            {"id": "sample_rate", "label": "Sample rate", "type": "text", "default": "", "hint": "e.g. 44100, 48000. Blank = keep source"},
            {"id": "channels", "label": "Channels", "type": "select", "options": ["Keep source", "Mono", "Stereo"], "default": "Keep source"},
        ],
        "run": _run_convert,
    },
]
