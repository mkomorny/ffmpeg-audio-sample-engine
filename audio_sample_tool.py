"""Audio Sample Tool — standalone build of a future Live Actions host tool.

Pick an input file (or a Generator, which needs none), pick an operation from
the grouped list, adjust its settings, Run. See DESIGN.md for the full design
and the contract every op in ops/ follows.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import tkinter as tk
import winsound
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import theme as th
from ops import registry

ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "local_settings.json"


def load_settings() -> dict[str, Any]:
    if SETTINGS_PATH.is_file():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_settings(settings: dict[str, Any]) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio Sample Tool")
        self.geometry("1040x700")
        self.minsize(880, 580)
        self.configure(bg=th.BG)

        self.settings: dict[str, Any] = load_settings()
        self.input_path: Path | None = None
        self.selected_op: dict[str, Any] | None = None
        self.field_vars: dict[str, tk.StringVar] = {}
        self.last_result_path: str | None = None
        self._running = False

        self._build_ui()
        self._populate_tree()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_topbar()

        body = tk.Frame(self, bg=th.BG)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        body.columnconfigure(0, weight=0, minsize=280)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_tree(body)
        self._build_detail(body)

        self.result_frame = tk.Frame(self, bg=th.SURFACE, highlightbackground=th.BORDER, highlightthickness=1)
        self.status_label = tk.Label(self, text="", bg=th.BG, fg=th.TEXT_MUTED, font=th.FONT_SMALL, anchor="w")
        self.status_label.pack(fill="x", padx=16, pady=(0, 10))

    def _build_topbar(self) -> None:
        bar = tk.Frame(self, bg=th.SURFACE, highlightbackground=th.BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=16, pady=16)

        tk.Label(bar, text="Audio Sample Tool", bg=th.SURFACE, fg=th.TEXT, font=th.FONT_TITLE).pack(
            anchor="w", padx=16, pady=(12, 2)
        )
        tk.Label(
            bar, text="ffmpeg-backed sample prep — pick a file, pick an operation, Run.",
            bg=th.SURFACE, fg=th.TEXT_MUTED, font=th.FONT_SMALL,
        ).pack(anchor="w", padx=16, pady=(0, 10))

        row = tk.Frame(bar, bg=th.SURFACE)
        row.pack(fill="x", padx=16, pady=(0, 14))

        self.input_label = tk.Label(
            row, text="No file selected — pick one, or choose a Generator below.",
            bg=th.SURFACE_INPUT, fg=th.TEXT_MUTED, font=th.FONT_BODY, anchor="w", padx=10, pady=8,
            highlightthickness=1, highlightbackground=th.BORDER,
        )
        self.input_label.pack(side="left", fill="x", expand=True)

        self._button(row, "Browse…", self._browse_input, primary=False).pack(side="left", padx=(8, 0))
        self._button(row, "Settings", self._open_settings, primary=False).pack(side="left", padx=(8, 0))

    def _build_tree(self, parent: tk.Widget) -> None:
        frame = tk.Frame(parent, bg=th.BG_SIDEBAR, highlightbackground=th.BORDER, highlightthickness=1)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        tk.Label(frame, text="OPERATIONS", bg=th.BG_SIDEBAR, fg=th.TEXT_MUTED, font=th.FONT_SECTION).pack(
            anchor="w", padx=12, pady=(10, 4)
        )

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Ops.Treeview", background=th.BG_SIDEBAR, fieldbackground=th.BG_SIDEBAR,
            foreground=th.TEXT, borderwidth=0, rowheight=26, font=th.FONT_BODY,
        )
        style.map("Ops.Treeview", background=[("selected", th.SURFACE_RAISED)], foreground=[("selected", th.ACCENT)])

        self.tree = ttk.Treeview(frame, show="tree", style="Ops.Treeview", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _populate_tree(self) -> None:
        for category, ops in registry.grouped():
            cat_id = self.tree.insert("", "end", text=category.upper(), open=True, tags=("category",))
            for op in ops:
                self.tree.insert(cat_id, "end", iid=op["id"], text="   " + op["name"], tags=("op",))
        self.tree.tag_configure("category", foreground=th.TEXT_DIM)
        self.tree.tag_configure("op", foreground=th.TEXT)

    def _build_detail(self, parent: tk.Widget) -> None:
        self.detail = tk.Frame(parent, bg=th.SURFACE, highlightbackground=th.BORDER, highlightthickness=1)
        self.detail.grid(row=0, column=1, sticky="nsew")
        self._render_detail_placeholder()

    def _render_detail_placeholder(self) -> None:
        for child in self.detail.winfo_children():
            child.destroy()
        tk.Label(
            self.detail, text="Pick an operation from the list on the left.",
            bg=th.SURFACE, fg=th.TEXT_MUTED, font=th.FONT_BODY,
        ).pack(padx=20, pady=20, anchor="w")

    # ── small widget helpers ─────────────────────────────────────────────

    def _button(self, parent: tk.Widget, text: str, command, primary: bool = True) -> tk.Label:
        bg = th.ACCENT if primary else th.SURFACE_RAISED
        fg = th.ACCENT_TEXT if primary else th.TEXT
        btn = tk.Label(parent, text=text, bg=bg, fg=fg, font=th.FONT_BODY_BOLD, padx=14, pady=8, cursor="hand2")
        if not primary:
            btn.configure(highlightthickness=1, highlightbackground=th.BORDER)
        btn.bind("<Button-1>", lambda _e: command())
        return btn

    # ── operation list -> settings form ─────────────────────────────────

    def _on_tree_select(self, _event: Any = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        op = registry.OPS_BY_ID.get(selection[0])
        if op is None:
            return  # a category header was clicked, not an operation
        self.selected_op = op
        self._render_detail_form(op)

    def _render_detail_form(self, op: dict[str, Any]) -> None:
        for child in self.detail.winfo_children():
            child.destroy()
        self.field_vars = {}

        tk.Frame(self.detail, bg=th.ACCENT, height=4).pack(fill="x")

        pad = tk.Frame(self.detail, bg=th.SURFACE)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(pad, text=op["name"], bg=th.SURFACE, fg=th.TEXT, font=th.FONT_HEADING).pack(anchor="w")
        tk.Label(
            pad, text=op["description"], bg=th.SURFACE, fg=th.TEXT_MUTED, font=th.FONT_SMALL,
            wraplength=560, justify="left",
        ).pack(anchor="w", pady=(2, 4))

        needs_input = op.get("needs_input", True)
        tk.Label(
            pad,
            text="Uses the file selected above." if needs_input else "Generates a new file — no input needed.",
            bg=th.SURFACE, fg=th.TEXT_DIM, font=th.FONT_SMALL,
        ).pack(anchor="w", pady=(0, 12))

        for field in op["fields"]:
            self._render_field(pad, field)

        run_row = tk.Frame(pad, bg=th.SURFACE)
        run_row.pack(fill="x", pady=(16, 0))
        self._button(run_row, "Run", self._run_selected_op, primary=True).pack(side="left")

    def _render_field(self, parent: tk.Widget, field: dict[str, Any]) -> None:
        row = tk.Frame(parent, bg=th.SURFACE)
        row.pack(fill="x", pady=6)
        tk.Label(row, text=field["label"], bg=th.SURFACE, fg=th.TEXT, font=th.FONT_BODY, width=24, anchor="w").pack(
            side="left"
        )

        var = tk.StringVar(value=str(field.get("default", "")))
        self.field_vars[field["id"]] = var

        if field.get("type") == "select":
            ttk.Combobox(row, textvariable=var, values=field.get("options", []), state="readonly", width=22).pack(
                side="left"
            )
        else:
            tk.Entry(
                row, textvariable=var, bg=th.SURFACE_INPUT, fg=th.TEXT, insertbackground=th.TEXT,
                relief="flat", font=th.FONT_BODY, width=24,
                highlightthickness=1, highlightbackground=th.BORDER, highlightcolor=th.ACCENT,
            ).pack(side="left", ipady=4)

        hint = field.get("hint")
        if hint:
            tk.Label(row, text=hint, bg=th.SURFACE, fg=th.TEXT_DIM, font=th.FONT_SMALL, wraplength=260, justify="left").pack(
                side="left", padx=(10, 0)
            )

    # ── input file + settings ───────────────────────────────────────────

    def _browse_input(self) -> None:
        picked = filedialog.askopenfilename(
            title="Choose an audio sample",
            filetypes=[("Audio files", "*.wav *.aiff *.aif *.mp3 *.flac *.ogg"), ("All files", "*.*")],
        )
        if not picked:
            return
        self.input_path = Path(picked)
        self.input_label.configure(text=str(self.input_path), fg=th.TEXT)

    def _open_settings(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Settings")
        dialog.configure(bg=th.SURFACE)
        dialog.transient(self)
        dialog.resizable(False, False)

        ffmpeg_var = tk.StringVar(value=str(self.settings.get("ffmpeg_path") or ""))
        out_var = tk.StringVar(value=str(self.settings.get("audio_sample_output_dir") or ""))

        def add_row(label: str, var: tk.StringVar, hint: str) -> None:
            r = tk.Frame(dialog, bg=th.SURFACE)
            r.pack(fill="x", padx=16, pady=8)
            tk.Label(r, text=label, bg=th.SURFACE, fg=th.TEXT, font=th.FONT_BODY_BOLD, anchor="w").pack(anchor="w")
            tk.Entry(
                r, textvariable=var, bg=th.SURFACE_INPUT, fg=th.TEXT, insertbackground=th.TEXT,
                relief="flat", font=th.FONT_BODY, width=54,
                highlightthickness=1, highlightbackground=th.BORDER, highlightcolor=th.ACCENT,
            ).pack(anchor="w", pady=(4, 2), ipady=4)
            tk.Label(r, text=hint, bg=th.SURFACE, fg=th.TEXT_DIM, font=th.FONT_SMALL, anchor="w").pack(anchor="w")

        add_row("ffmpeg path", ffmpeg_var, "Blank = use ffmpeg from PATH.")
        add_row("Output folder", out_var, "Blank = .\\output next to this app.")

        def save_and_close() -> None:
            self.settings["ffmpeg_path"] = ffmpeg_var.get().strip()
            self.settings["audio_sample_output_dir"] = out_var.get().strip()
            save_settings(self.settings)
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg=th.SURFACE)
        btn_row.pack(fill="x", padx=16, pady=14)
        self._button(btn_row, "Save", save_and_close, primary=True).pack(side="left")
        self._button(btn_row, "Cancel", dialog.destroy, primary=False).pack(side="left", padx=8)

        dialog.update_idletasks()
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 80, self.winfo_rooty() + 80))
        dialog.grab_set()

    # ── running an op ────────────────────────────────────────────────────

    def _run_selected_op(self) -> None:
        op = self.selected_op
        if op is None or self._running:
            return
        if op.get("needs_input", True) and self.input_path is None:
            self._set_status("Pick an input file first.", th.WARN)
            return

        fields = {key: var.get() for key, var in self.field_vars.items()}
        input_path = str(self.input_path) if self.input_path else None

        self._running = True
        self._set_status("Running %s…" % op["name"], th.TEXT_MUTED)

        def worker() -> None:
            try:
                result = op["run"](input_path, fields, self.settings)
            except Exception as exc:  # an op must never take the app down
                result = {"ok": False, "message": "Unexpected error: %s" % exc}
            self.after(0, lambda: self._finish_run(op["name"], result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_run(self, name: str, result: dict[str, Any]) -> None:
        self._running = False
        ok = bool(result.get("ok"))
        message = str(result.get("message") or ("Done." if ok else "Failed."))
        self._set_status(("✓ %s — %s" if ok else "⚠ %s — %s") % (name, message), th.OK if ok else th.ERR)
        self._show_result(result.get("path") if ok else None)

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, fg=color)

    # ── result row: play / stop / save as / open folder ────────────────

    def _show_result(self, path: str | None) -> None:
        self.result_frame.pack_forget()
        for child in self.result_frame.winfo_children():
            child.destroy()
        self.last_result_path = path
        if not path:
            return

        self.result_frame.pack(fill="x", padx=16, pady=(0, 10), before=self.status_label)

        tk.Label(
            self.result_frame, text="📄  " + path, bg=th.SURFACE, fg=th.TEXT, font=th.FONT_MONO,
            anchor="w", wraplength=680, justify="left",
        ).pack(side="left", padx=12, pady=10, fill="x", expand=True)

        btn_row = tk.Frame(self.result_frame, bg=th.SURFACE)
        btn_row.pack(side="right", padx=12)

        can_preview = Path(path).suffix.lower() == ".wav"
        play_label = "▶ Play" if can_preview else "▶ Play (WAV only)"
        play_btn = self._button(btn_row, play_label, self._play_result, primary=False)
        play_btn.pack(side="left", padx=4)
        if not can_preview:
            play_btn.unbind("<Button-1>")
            play_btn.configure(fg=th.TEXT_DIM, cursor="arrow")

        self._button(btn_row, "■ Stop", self._stop_preview, primary=False).pack(side="left", padx=4)
        self._button(btn_row, "Save As…", self._save_result_as, primary=False).pack(side="left", padx=4)
        self._button(btn_row, "Open Folder", self._open_result_folder, primary=False).pack(side="left", padx=4)

    def _play_result(self) -> None:
        if not self.last_result_path:
            return
        try:
            winsound.PlaySound(self.last_result_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError as exc:
            self._set_status("Could not play file: %s" % exc, th.ERR)

    def _stop_preview(self) -> None:
        winsound.PlaySound(None, winsound.SND_PURGE)

    def _save_result_as(self) -> None:
        if not self.last_result_path:
            return
        src = Path(self.last_result_path)
        picked = filedialog.asksaveasfilename(
            title="Save Sample As", initialdir=str(src.parent), initialfile=src.name,
            defaultextension=src.suffix, filetypes=[("Audio file", "*" + src.suffix), ("All files", "*.*")],
        )
        if not picked:
            return
        dest = Path(picked)
        try:
            if dest.resolve() != src.resolve():
                shutil.copyfile(src, dest)
        except OSError as exc:
            messagebox.showerror("Save Sample", "Could not save to that location:\n%s" % exc)
            return
        self._set_status("Saved copy to %s" % dest, th.OK)

    def _open_result_folder(self) -> None:
        if not self.last_result_path:
            return
        os.startfile(str(Path(self.last_result_path).parent))  # Windows-only, matches this project's platform


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
