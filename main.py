import threading
import multiprocessing
from datetime import datetime
import psutil
import customtkinter as ctk
from tkinter import filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from diagnostics import get_system_diagnostics
from benchmark import run_thermal_stress_test
from database import save_test_result, get_all_history

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class PCHealthApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PC Auditor")
        self.geometry("760x780")
        self.resizable(True, True)

        self.last_diag = None
        self.last_bench = None
        self.cpu_history = [0.0] * 30

        self._build_ui()
        threading.Thread(target=self._initial_scan, daemon=True).start()
        self._update_live_chart()

    def _build_ui(self):
        # Header
        header = ctk.CTkLabel(
            self,
            text="PC Auditor",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F60404",
        )
        header.pack(pady=(20, 5))

        subtitle = ctk.CTkLabel(
            self,
            text="CPU throttling detection and hardware configuration checks (XMP / Refresh Rate / Disk)",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        subtitle.pack(pady=(0, 12))

        # Specs frame
        self.specs_frame = ctk.CTkFrame(self)
        self.specs_frame.pack(fill="x", padx=25, pady=5)

        self.specs_label = ctk.CTkLabel(
            self.specs_frame,
            text="Loading system info...",
            justify="left",
            font=ctk.CTkFont(size=13),
        )
        self.specs_label.pack(padx=15, pady=12, anchor="w")

        # Live chart (Matplotlib)
        chart_frame = ctk.CTkFrame(self)
        chart_frame.pack(fill="x", padx=25, pady=8)

        self.fig = Figure(figsize=(10.0, 5.0), dpi=100, facecolor="#2b2b2b")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#1e1e1e")
        self.ax.set_ylim(0, 105)
        self.ax.set_ylabel("CPU %", color="gray", fontsize=9)
        self.ax.set_title("CPU usage", color="#cccccc", fontsize=20)
        self.ax.tick_params(colors="gray", labelsize=8)
        self.ax.grid(True, linestyle="--", alpha=0.2, color="gray")
        self.line, = self.ax.plot(self.cpu_history, color="#B70000", linewidth=2)
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=12)

        self.run_btn = ctk.CTkButton(
            btn_frame,
            text="Full test + CPU stress (12s)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color="#330066",
            hover_color="#4b0096",
            command=self.start_full_test,
        )
        self.run_btn.pack(side="left", padx=6)

        self.save_db_btn = ctk.CTkButton(
            btn_frame,
            text="Save to DB",
            height=40,
            fg_color="#0052B7",
            hover_color="#003d8a",
            state="disabled",
            command=self.save_to_database,
        )
        self.save_db_btn.pack(side="left", padx=6)

        self.history_btn = ctk.CTkButton(
            btn_frame,
            text="History (DB)",
            height=40,
            fg_color="#33333a",
            hover_color="#464650",
            command=self.open_history_window,
        )
        self.history_btn.pack(side="left", padx=6)

        self.export_btn = ctk.CTkButton(
            btn_frame,
            text="Save report (.txt)",
            height=40,
            fg_color="#7e1d1d",
            hover_color="#5c1414",
            state="disabled",
            command=self.export_report,
        )
        self.export_btn.pack(side="left", padx=6)

        # Progress bar
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self,
            width=700,
            height=12,
            corner_radius=6,
            fg_color="#1e1e1e",
            progress_color="#A50000",
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(5, 5))

        self.status_label = ctk.CTkLabel(
            self, text="Waiting to start...", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.status_label.pack(pady=(0, 8))

        # Result box
        self.result_box = ctk.CTkTextbox(self, width=710, height=200, font=ctk.CTkFont(size=13))
        self.result_box.pack(padx=25, pady=(5, 20))
        self.result_box.insert("0.0", "Waiting...")
        self.result_box.configure(state="disabled")

    def _update_live_chart(self):
        usage = psutil.cpu_percent(interval=None)
        self.cpu_history.pop(0)
        self.cpu_history.append(usage)

        self.line.set_ydata(self.cpu_history)
        self.canvas.draw_idle()
        self.after(500, self._update_live_chart)

    def _update_specs_text(self, diag: dict):
        text = (
            f"CPU: {diag['cpu_name']} (Load: {diag['cpu_usage']}%)  |  Power plan: {diag['power_plan']}\n"
            f"GPU: {diag['gpu_name']}\n"
            f"RAM: {diag['ram_total_gb']} GB @ {diag['ram_speed']} MHz (Used: {diag['ram_percent']}%)\n"
            f"Monitor: {diag['refresh_rate']} Hz   |   Free space C: {diag['disk_free_gb']} GB   |   S.M.A.R.T.: {diag['smart_summary']}"
        )
        self.specs_label.configure(text=text)

    def _initial_scan(self):
        try:
            diag = get_system_diagnostics()
            self.last_diag = diag
            self.after(0, lambda: self._update_specs_text(diag))
        except Exception as e:
            print("SCAN ERROR:", repr(e))
            self.after(0, lambda err=e: self.specs_label.configure(text=f"Hardware read error: {err}"))

    def _update_progress(self, value: float, text: str):
        self.after(0, lambda: self.progress_bar.set(value))
        self.after(0, lambda: self.status_label.configure(text=text))

    def start_full_test(self):
        self.run_btn.configure(state="disabled")
        self.export_btn.configure(state="disabled")
        self.save_db_btn.configure(state="disabled")
        self.progress_bar.set(0)
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        bench = run_thermal_stress_test(progress_callback=self._update_progress)
        diag = get_system_diagnostics(benchmark_result=bench)

        self.last_bench = bench
        self.last_diag = diag

        self.after(0, lambda: self._display_results(diag, bench))

    def _display_results(self, diag: dict, bench: dict):
        self._update_specs_text(diag)
        self.run_btn.configure(state="normal")
        self.export_btn.configure(state="normal")
        self.save_db_btn.configure(state="normal")

        lines = [
            f"==== CONFIGURATION & STABILITY SCORE: {diag['score']} / 100 PTS ===\n",
            f"• CPU Test ({bench['cores_tested']} threads):",
            f"   - Cold sample: {bench['cold_mops']}M ops/s",
            f"   - Post-load sample: {bench['hot_mops']}M ops/s",
            f"   - Performance drop: {bench['drop_percent']}%\n",
            f"• System uptime: {diag['uptime_hours']} hrs",
            f"• Most resource-heavy processes (RAM): {diag['top_processes']}\n",
            "=== DETECTED NOTES & WARNINGS ===",
        ]

        if not diag["warnings"]:
            lines.append(" No configuration issues found")
        else:
            for w in diag["warnings"]:
                lines.append(f"[WARN] {w}")

        self.result_box.configure(state="normal")
        self.result_box.delete("0.0", "end")
        self.result_box.insert("0.0", "\n".join(lines))
        self.result_box.configure(state="disabled")

    def save_to_database(self):
        if not self.last_diag or not self.last_bench:
            return
        save_test_result(self.last_diag, self.last_bench)
        self.save_db_btn.configure(state="disabled")
        messagebox.showinfo("SQLite", "Test result saved to audit_history.db")

    def open_history_window(self):
        rows = get_all_history()
        win = ctk.CTkToplevel(self)
        win.title("Test History (SQLite)")
        win.geometry("680x360")
        win.attributes("-topmost", True)

        box = ctk.CTkTextbox(win, width=640, height=320, font=ctk.CTkFont(family="Consolas", size=12))
        box.pack(padx=20, pady=20)

        if not rows:
            box.insert("0.0", "No saved tests in database..")
        else:
            header = f"{'DATE':<20} | {'COLD':<8} | {'HOT':<8} | {'DROP':<7} | {'SCORE'}\n"
            box.insert("end", header + "-" * 68 + "\n")
            for r in rows:
                line = f"{r[0]:<20} | {r[2]:<8} | {r[3]:<8} | {r[4]:>5}% | {r[5]}/100\n"
                box.insert("end", line)

        box.configure(state="disabled")

    def export_report(self):
        if not self.last_diag or not self.last_bench:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt")],
            initialfile=f"pc_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        )
        if not file_path:
            return

        content = self.specs_label.cget("text") + "\n\n" + self.result_box.get("0.0", "end")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        messagebox.showinfo("Saved", "Diagnostic report saved")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = PCHealthApp()
    app.mainloop()