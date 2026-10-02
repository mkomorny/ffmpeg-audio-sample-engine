"""Dev-only generator — NOT shipped, NOT imported by the app.

Walks ops/registry.py and emits the tool.json manifest for the "audio-sample"
Live Actions host tool: one namespaced field per (op, field) pair, gated by a
`showIf` on the `operation` select so only the chosen op's fields render.

The namespacing scheme here (field_prefix) MUST stay byte-identical to the one
in Live Actions Helper's app/audio_sample/__init__.py adapter, which strips it
back off. If you change one, change the other.

Usage:
    python make_tool_json.py > tool.json
    python make_tool_json.py "C:\\Users\\miran\\My Apps\\Live Actions Helper\\tools\\audio-sample\\tool.json"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ops import registry  # noqa: E402

# Shortened for the Operation dropdown — full category names are used everywhere
# else (the standalone app's tree, docs), but "Effects (100% wet)" and
# "Generators (no input file)" are too long as a combobox prefix.
SHORT_CATEGORY: dict[str, str] = {
    "Trim, Fades & Levels": "Trim, Fades & Levels",
    "Convert": "Convert",
    "Reverse, Pitch & Time": "Reverse, Pitch & Time",
    "Effects (100% wet)": "Effects",
    "Generators (no input file)": "Generators",
}

GENERATOR_IDS = {op["id"] for op in registry.ALL_OPS if not op.get("needs_input", True)}


def field_prefix(op_id: str) -> str:
    return op_id.replace("-", "_") + "__"


def display_name(op: dict[str, Any]) -> str:
    short = SHORT_CATEGORY.get(op["category"], op["category"])
    return "%s — %s" % (short, op["name"])


def build_manifest() -> dict[str, Any]:
    display_names = [display_name(op) for op in registry.ALL_OPS]
    generator_names = [display_name(op) for op in registry.ALL_OPS if op["id"] in GENERATOR_IDS]

    fields: list[dict[str, Any]] = [
        {
            "id": "operation",
            "label": "Operation",
            "type": "select",
            "options": display_names,
            "default": display_names[0],
            "hint": "Pick what to do to the sample, then fill in its settings below.",
        },
        {
            "id": "input_file",
            "label": "Input audio file",
            "type": "file",
            "default": "",
            "filetypes": [
                ["Audio files", "*.wav *.aiff *.aif *.mp3 *.flac *.ogg"],
                ["All files", "*.*"],
            ],
            "hint": "Browse to the sample you want to process.",
            "showIf": {"field": "operation", "notIn": generator_names},
        },
    ]

    for op in registry.ALL_OPS:
        prefix = field_prefix(op["id"])
        name = display_name(op)
        for spec in op["fields"]:
            entry: dict[str, Any] = {
                "id": prefix + spec["id"],
                "label": spec["label"],
                "type": spec["type"],
                "default": spec.get("default", ""),
                "showIf": {"field": "operation", "in": [name]},
            }
            if spec.get("hint"):
                entry["hint"] = spec["hint"]
            if spec.get("options"):
                entry["options"] = spec["options"]
            fields.append(entry)

    fields.append(
        {
            "id": "destination",
            "label": "Destination",
            "type": "select",
            "options": ["Leave in output folder", "Save to PC", "Add to Live Set"],
            "default": "Leave in output folder",
            "hint": (
                "Leave in output folder just writes the file. Save to PC asks where to put it. "
                "Add to Live Set places it on the first ticked audio track."
            ),
        }
    )

    return {
        "id": "audio-sample",
        "name": "Audio Sample",
        "description": (
            "ffmpeg-backed sample prep — trim, fade, normalize, convert, pitch/time, effects, "
            "and generators. Runs on the desktop host, not in Live."
        ),
        "accent": "#38BDF8",
        "version": "1.0",
        "enabled": True,
        "runtime": "host",
        "fields": fields,
    }


def main() -> None:
    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2)
    if len(sys.argv) > 1:
        out_path = Path(sys.argv[1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
        print("Wrote %d fields to %s" % (len(manifest["fields"]), out_path))
    else:
        print(payload)


if __name__ == "__main__":
    main()
