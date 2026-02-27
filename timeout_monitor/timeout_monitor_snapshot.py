import tkinter as tk
from tkinter import ttk, messagebox
import requests
import time
import threading
import sys
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# 監視対象API
API_URL = "http://localhost:8000/metrics"

# 設定
MAX_DURATION = 300  # 最大計測時間 (秒)
BIN_SIZE = 5        # 集計区間 (秒)
UPDATE_INTERVAL = 1 # 更新間隔 (秒)
Y_AXIS_MAX = 700    # Y軸最大値 (固定)
SCREENSHOT_FILENAME = "RA_noplan.png" # スクリーンショット保存ファイル名(変更可)

class AutoStartMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Realtime Timeout Monitor")
        self.root.geometry("900x600")

        # データ管理
        self.start_time = None
        self.last_total_timeouts = 0
        self.baseline_timeouts = 0
        
        self.num_bins = (MAX_DURATION // BIN_SIZE) + 1
        self.bins = [0] * self.num_bins
        self.x_pos = [i * BIN_SIZE for i in range(self.num_bins)]
        
        self.is_running = False

        # --- GUI Layout ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Labels
        info_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.time_label = ttk.Label(info_frame, text="Elapsed: 0s", font=("Arial", 12))
        self.time_label.pack(side=tk.LEFT, padx=10)

        self.total_label = ttk.Label(info_frame, text="Total Timeouts (300s): 0", font=("Arial", 14, "bold"), foreground="red")
        self.total_label.pack(side=tk.LEFT, padx=20)

        self.status_label = ttk.Label(info_frame, text="Starting...", font=("Arial", 10), foreground="blue")
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

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Save Button
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        self.save_btn = ttk.Button(btn_frame, text="Save Graph", command=self.save_graph)
        self.save_btn.pack(side=tk.RIGHT, padx=5)

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
        # 1. 初期化待ち
        while self.is_running:
            initial = self.get_metrics()
            if initial is not None:
                self.start_time = time.time()
                self.last_total_timeouts = initial
                self.baseline_timeouts = initial
                
                self.root.after(0, lambda: self.status_label.config(text="Running", foreground="green"))
                break
            time.sleep(0.5)

        # 2. 計測ループ
        while self.is_running:
            now = time.time()
            elapsed = now - self.start_time
            
            if elapsed > MAX_DURATION:
                self.is_running = False
                self.root.after(0, lambda: self.status_label.config(text="Finished", foreground="red"))
                break

            current_total = self.get_metrics()
            
            if current_total is not None:
                delta = max(0, current_total - self.last_total_timeouts)
                self.last_total_timeouts = current_total

                period_total = max(0, current_total - self.baseline_timeouts)

                bin_idx = int(elapsed // BIN_SIZE)
                if bin_idx < len(self.bins):
                    self.bins[bin_idx] += delta

                self.root.after(0, self.update_gui, elapsed, period_total)
            
            time.sleep(UPDATE_INTERVAL)

    def update_gui(self, elapsed, period_total):
        self.time_label.config(text=f"Elapsed: {int(elapsed)}s")
        self.total_label.config(text=f"Total Timeouts (300s): {period_total}")

        for rect, h in zip(self.bar_container, self.bins):
            rect.set_height(h)
        
        self.canvas.draw_idle()

    def save_graph(self):
        self.fig.savefig(SCREENSHOT_FILENAME)
        messagebox.showinfo("Saved", f"Saved to {SCREENSHOT_FILENAME}")

    def on_close(self):
        self.is_running = False
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoStartMonitor(root)
    root.mainloop()