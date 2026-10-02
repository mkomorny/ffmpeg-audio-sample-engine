# FFmpeg Audio Sample Engine - Setup & Usage Guide

## Prerequisites
- **Python**: 3.9+
- **FFmpeg**: Must be installed on your system.
  - Windows: `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org/)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

Verify installation:
```bash
ffmpeg -version
```

---

## 1. Running Sample Tool CLI

To test an audio transformation operation:
```bash
python audio_sample_tool.py --help
```

---

## 2. Programmatic Usage

Import operations directly into your Python scripts or pipeline:
```python
from ops.registry import get_operation

trim_op = get_operation("trim")
result = trim_op.run(
    input_path="input.wav",
    fields={"start_ms": 1000, "end_ms": 5000},
    settings={"output_dir": "./processed"}
)
print(result)
```
