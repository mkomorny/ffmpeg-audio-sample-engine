# FFmpeg Audio Sample Engine

A decoupled, functional audio DSP transformation library and sample processing engine built in Python around the FFmpeg command-line suite. Exposes 17 granular audio operations across trimming, automated silence elimination, peak/LUFS normalization, stereo widening, pitch/tempo shifting, and multi-format conversion.

## Architecture

Every operation is implemented as a pure, stateless handler adhering to the standard schema:
```python
def run(input_path: str, fields: dict, settings: dict) -> dict:
    ...
    return {"ok": True, "message": "...", "path": output_path}
```
This architecture decouples the DSP operations from any specific UI, allowing them to be invoked from the command line, web services, batch job runners, or desktop GUIs without modification.

## Features & Operations

- **Trim & Levels**: Exact millisecond sample cutting, automated start/end silence stripping, linear/exponential fades, and peak/RMS normalization.
- **Pitch & Time**: Independent pitch shifting (semitone/cent) and tempo stretching using `atempo` and `rubberband` filter graphs.
- **Stereo & Channels**: Mono-to-stereo synthesis, Mid/Side matrix encoding/decoding, channel phase inversion, and stereo image widening.
- **Conversion & Formatting**: Lossless (WAV, FLAC, AIFF) and delivery (MP3, OGG, AAC) transcoding with bit-depth and sample-rate dithering.

## Dependencies

- **Python**: Version 3.9 or higher (standard library only: `subprocess`, `pathlib`, `json`, `argparse`, `shutil`).
- **FFmpeg**: System FFmpeg executable installed and available on system PATH.

## Instructions

See [INSTRUCTIONS.md](./INSTRUCTIONS.md) for CLI commands and programmatic usage.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0) - see the [LICENSE](./LICENSE) file for details.
