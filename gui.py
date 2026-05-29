"""Main tkinter GUI for the coordinate format converter."""

import tkinter as tk
from tkinter import ttk
from parser import parse
from converter import format_dd, format_dms, format_ddm
from minimap import MiniMap


class CoordConverterApp:
    """Main application window for coordinate format conversion."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("经纬度坐标格式转换器")
        self.root.geometry("620x700")
        self.root.resizable(True, True)
        self.root.minsize(620, 600)

        # Debounce timer
        self._debounce_id: str | None = None

        # Variables
        self.input_var = tk.StringVar()
        self.dd_var = tk.StringVar()
        self.dms_var = tk.StringVar()
        self.ddm_var = tk.StringVar()
        self.status_var = tk.StringVar(value="输入经纬度坐标，支持 DD / DMS / DDM 格式")

        self._build_ui()

    def _build_ui(self):
        """Build the complete widget tree."""
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="经纬度坐标格式转换器",
                          font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        # ── Input Section ──
        input_frame = ttk.LabelFrame(main_frame, text="输入", padding=8)
        input_frame.pack(fill=tk.X, pady=(0, 8))

        input_row = ttk.Frame(input_frame)
        input_row.pack(fill=tk.X)

        self.input_entry = ttk.Entry(input_row, textvariable=self.input_var, font=("Consolas", 11))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.input_entry.bind("<KeyRelease>", self._on_input_changed)
        self.input_entry.bind("<<Paste>>", lambda e: self.root.after(10, self._on_input_changed, None))
        self.input_entry.focus_set()

        clear_btn = ttk.Button(input_row, text="✕", width=3, command=self._clear)
        clear_btn.pack(side=tk.RIGHT)

        self.status_label = ttk.Label(input_frame, textvariable=self.status_var,
                                      foreground="gray", font=("Segoe UI", 9))
        self.status_label.pack(anchor="w", pady=(4, 0))

        # Example hint
        hint = ttk.Label(input_frame,
                         text="示例: 40°26'46\"N 79°56'56\"W  |  40 26 46 N 79 56 56 W  |  40.44611, -79.94889",
                         foreground="#999999", font=("Segoe UI", 8))
        hint.pack(anchor="w", pady=(2, 0))

        # ── Output Sections ──
        self._create_output_section(main_frame, "十进制度 (DD) — 最简GPS格式", self.dd_var, self._copy_dd)
        self._create_output_section(main_frame, "度分秒 (DMS)", self.dms_var, self._copy_dms)
        self._create_output_section(main_frame, "度十进制分 (DDM)", self.ddm_var, self._copy_ddm)

        # ── Minimap ──
        map_frame = ttk.LabelFrame(main_frame, text="地图预览", padding=4)
        map_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.minimap = MiniMap(map_frame, width=580, height=250)
        self.minimap.pack(fill=tk.BOTH, expand=True)

    def _create_output_section(self, parent, label_text: str, var: tk.StringVar, copy_cmd):
        """Create a reusable output row: label + readonly entry + copy button."""
        frame = ttk.LabelFrame(parent, text=label_text, padding=6)
        frame.pack(fill=tk.X, pady=(0, 6))

        row = ttk.Frame(frame)
        row.pack(fill=tk.X)

        entry = ttk.Entry(row, textvariable=var, font=("Consolas", 11), state="readonly")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._button_frame_ref = row  # store reference for button callbacks

        btn = ttk.Button(row, text="复制", width=8, command=copy_cmd)
        btn.pack(side=tk.RIGHT)

        # Store reference for copy feedback
        var._copy_btn = btn
        entry._copy_btn = btn

    # ── Input Handling ──

    def _on_input_changed(self, event=None):
        """Debounced handler: reset timer on each keystroke."""
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(250, self._do_convert)

    def _do_convert(self):
        """Parse input and update all output fields."""
        self._debounce_id = None
        text = self.input_var.get()

        if not text.strip():
            self._reset_outputs()
            self.status_var.set("输入经纬度坐标，支持 DD / DMS / DDM 格式")
            self.status_label.configure(foreground="gray")
            self.input_entry.configure(foreground="black")
            self.minimap.clear_points()
            return

        result = parse(text)

        if not result.success:
            self._reset_outputs()
            self.status_var.set(result.error_message)
            self.status_label.configure(foreground="#CC0000")
            self.input_entry.configure(foreground="#CC0000")
            self.minimap.clear_points()
            return

        # Success
        fmt_names = {"DD": "十进制度", "DMS": "度分秒", "DDM": "度十进制分"}
        fmt_cn = fmt_names.get(result.format_detected, result.format_detected)
        self.status_var.set(f"已识别: {fmt_cn} — 共 {len(result.pairs)} 对坐标")
        self.status_label.configure(foreground="#008800")
        self.input_entry.configure(foreground="black")

        # Format all pairs
        dd_lines = []
        dms_lines = []
        ddm_lines = []
        for lat, lon in result.pairs:
            dd_lines.append(format_dd(lat, lon))
            dms_lines.append(format_dms(lat, lon))
            ddm_lines.append(format_ddm(lat, lon))

        self.dd_var.set("\n".join(dd_lines))
        self.dms_var.set("\n".join(dms_lines))
        self.ddm_var.set("\n".join(ddm_lines))

        # Update minimap
        self.minimap.plot_batch(result.pairs)

    def _reset_outputs(self):
        """Clear all output fields."""
        self.dd_var.set("")
        self.dms_var.set("")
        self.ddm_var.set("")

    def _clear(self):
        """Clear input and outputs."""
        self.input_var.set("")
        self._reset_outputs()
        self.status_var.set("输入经纬度坐标，支持 DD / DMS / DDM 格式")
        self.status_label.configure(foreground="gray")
        self.input_entry.configure(foreground="black")
        self.minimap.clear_points()
        self.input_entry.focus_set()

    # ── Copy Commands ──

    def _copy_dd(self):
        self._copy_to_clipboard(self.dd_var.get(), self.dd_var._copy_btn)

    def _copy_dms(self):
        self._copy_to_clipboard(self.dms_var.get(), self.dms_var._copy_btn)

    def _copy_ddm(self):
        self._copy_to_clipboard(self.ddm_var.get(), self.ddm_var._copy_btn)

    def _copy_to_clipboard(self, text: str, button: ttk.Button):
        """Copy text to clipboard with brief visual feedback on the button."""
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        original = button.cget("text")
        button.configure(text="已复制!")
        self.root.after(1500, lambda: button.configure(text=original))
