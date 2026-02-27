import tkinter as tk
from tkinter import ttk, messagebox
import requests
import time
import threading
import sys
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import numpy as np
import imageio.v2 as imageio

# 監視対象API
API_URL = "http://localhost:8000/metrics"

# 設定
MAX_DURATION = 300        # 最大計測時間 (秒)
BIN_SIZE = 5              # 集計区間 (秒)
UPDATE_INTERVAL = 1       # メトリクス更新間隔 (秒)
Y_AXIS_MAX = 700          # Y軸最大値 (固定)
VIDEO_FPS = 29.97         # 動画のフレームレート
CAPTURE_INTERVAL_MS = int(1000 / VIDEO_FPS)  # 約33ms ごとにキャプチャ
VIDEO_FILENAME = "RA_plan01.mp4" # ビデオ保存ファイル名(変更可)

class AutoStartMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Realtime Timeout Monitor")
        self.root.geometry("900x600")

        # データ管理
        self.start_time = None
        self.last_total_timeouts = 0
        self.baseline_timeouts = 0  # 計測開始時のタイムアウト数
        
        self.num_bins = (MAX_DURATION // BIN_SIZE) + 1
        self.bins = [0] * self.num_bins
        self.x_pos = [i * BIN_SIZE for i in range(self.num_bins)]
        
        self.is_running = False

        # 動画用フレーム格納
        self.frames = []

        # --- GUI Layout ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Labels (Tk 側の表示用)
        info_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.time_label = ttk.Label(info_frame, text="Elapsed: 0s", font=("Arial", 12))
        self.time_label.pack(side=tk.LEFT, padx=10)

        self.total_label = ttk.Label(
            info_frame,
            text="Total Timeouts (300s): 0",
            font=("Arial", 14, "bold"),
            foreground="red"
        )
        self.total_label.pack(side=tk.LEFT, padx=20)

        self.status_label = ttk.Label(
            info_frame,
            text="Starting...",
            font=("Arial", 10),
            foreground="blue"
        )
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Graph Area
        graph_frame = ttk.LabelFrame(main_frame, text="Current Timeouts", padding="5")
        graph_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)

        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.bar_container = self.ax.bar(
            self.x_pos, self.bins, 
            width=BIN_SIZE * 0.8, align='edge', 
            color='#ff6b6b', edgecolor='#c0392b'
        )

        self.ax.set_xlim(0, MAX_DURATION)
        self.ax.set_ylim(0, Y_AXIS_MAX)
        self.ax.set_xlabel("Time (seconds)")
        self.ax.set_ylabel("Timeouts / 5s")
        self.ax.grid(True, axis='y', linestyle='--', alpha=0.5)

        self.fig_text = self.fig.text(
            0.5, 0.96,
            "Elapsed: 0s  |  Total Timeouts (300s): 0",
            ha='center', va='top', fontsize=10
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.start_monitoring)

    def get_metrics(self):
        try:
            r = requests.get(API_URL, timeout=1)
            if r.status_code == 200:
                data = r.json()
                val = data.get("timeouts", 0)
                return int(val)
        except:
            pass
        return None

    def start_monitoring(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()

    def monitor_loop(self):
        while self.is_running:
            initial = self.get_metrics()
            if initial is not None:
                self.start_time = time.time()
                self.last_total_timeouts = initial
                self.baseline_timeouts = initial
                
                self.root.after(
                    0,
                    lambda: self.status_label.config(text="Running", foreground="green")
                )
                self.root.after(0, self.start_capture_loop)
                break
            time.sleep(0.5)

        while self.is_running:
            now = time.time()
            elapsed = now - self.start_time if self.start_time is not None else 0.0

            current_total = self.get_metrics()
            
            if current_total is not None and self.start_time is not None:
                delta = max(0, current_total - self.last_total_timeouts)
                self.last_total_timeouts = current_total

                period_total = max(0, current_total - self.baseline_timeouts)

                bin_idx = int(elapsed // BIN_SIZE)
                if 0 <= bin_idx < len(self.bins):
                    self.bins[bin_idx] += delta

                self.root.after(0, self.update_gui, elapsed, period_total)
            
            time.sleep(UPDATE_INTERVAL)

    def start_capture_loop(self):
        if self.start_time is None:
            return
        self.capture_loop()

    def capture_loop(self):
        if not self.is_running or self.start_time is None:
            return

        elapsed = time.time() - self.start_time

        if elapsed >= MAX_DURATION:
            final_elapsed = MAX_DURATION
            final_total = max(0, self.last_total_timeouts - self.baseline_timeouts)
            self.update_gui(final_elapsed, final_total)

            self.is_running = False
            self.status_label.config(text="Finished", foreground="red")

            self.capture_frame()
            self.save_video()
            return

        self.capture_frame()
        self.root.after(CAPTURE_INTERVAL_MS, self.capture_loop)

    def update_gui(self, elapsed, period_total):
        self.time_label.config(text=f"Elapsed: {int(elapsed)}s")
        self.total_label.config(text=f"Total Timeouts (300s): {period_total}")

        self.fig_text.set_text(
            f"Elapsed: {int(elapsed)}s  |  Total Timeouts (300s): {period_total}"
        )

        for rect, h in zip(self.bar_container, self.bins):
            rect.set_height(h)
        
        self.canvas.draw_idle()
        self.canvas.flush_events()

    def capture_frame(self):
        self.fig.canvas.draw()
        w, h = self.fig.canvas.get_width_height()
        buf = np.frombuffer(self.fig.canvas.tostring_rgb(), dtype=np.uint8)
        buf = buf.reshape(h, w, 3)
        self.frames.append(buf.copy())

    def save_video(self):
        if not self.frames:
            return
        try:
            expected_frames = int(MAX_DURATION * VIDEO_FPS)

            if len(self.frames) < expected_frames:
                last = self.frames[-1]
                missing = expected_frames - len(self.frames)
                self.frames.extend([last] * missing)
            elif len(self.frames) > expected_frames:
                self.frames = self.frames[:expected_frames]

            with imageio.get_writer(VIDEO_FILENAME, fps=VIDEO_FPS) as writer:
                for frame in self.frames:
                    writer.append_data(frame)
        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror("Video Error", f"Failed to save video: {e}")
            )

    def on_close(self):
        self.is_running = False
        self.root.destroy()
        sys.exit()


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoStartMonitor(root)
    root.mainloop()
