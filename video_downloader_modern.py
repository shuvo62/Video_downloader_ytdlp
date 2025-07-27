import itertools, threading, queue, sys, shutil, os, subprocess, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse
import json
from collections import deque

# ---------------------- Dependency Check ----------------------
def ensure_dependencies():
    if not shutil.which("yt-dlp"):
        try:
            subprocess.run(["winget", "install", "-e", "--id", "yt-dlp.yt-dlp", "-h"], check=True)
        except:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
            except:
                show_dep_error("yt-dlp")
    if not shutil.which("ffmpeg"):
        try:
            subprocess.run(["winget", "install", "-e", "--id", "Gyan.FFmpeg", "-h"], check=True)
        except:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "ffmpeg"])
            except:
                show_dep_error("ffmpeg")

def show_dep_error(pkg):
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("❌ Dependency Error", f"🚫 {pkg} could not be installed.\nPlease install it manually.")
    root.destroy(); sys.exit(1)

ensure_dependencies()

# ---------------------- Modern UI Setup ----------------------
SECONDARY_COLOR = "#ffffff"
ACCENT_COLOR = "#142e51"
LIGHT_COLOR = "#e6f1fa"
DARK_COLOR = "#0f1c32"
BG_GRADIENT = "#e3ecfa"
FONT = ("Segoe UI", 11)
HEADER_FONT = ("Segoe UI Semibold", 13)
LABEL_FONT = ("Segoe UI", 10)

def set_gradient(widget, width, height, color1, color2):
    """Set vertical gradient background (Canvas hack)."""
    canvas = tk.Canvas(widget, width=width, height=height, highlightthickness=0)
    for i in range(height):
        ratio = i / height
        r1, g1, b1 = widget.winfo_rgb(color1)
        r2, g2, b2 = widget.winfo_rgb(color2)
        r = int(r1 + ratio * (r2 - r1)) // 256
        g = int(g1 + ratio * (g2 - g1)) // 256
        b = int(b1 + ratio * (b2 - b1)) // 256
        color = f"#{r:02x}{g:02x}{b:02x}"
        canvas.create_line(0, i, width, i, fill=color)
    canvas.place(x=0, y=0)
    return canvas

# ---------------------- Scrollable Root Setup ----------------------
def make_scrollable_root(root, width=950, height=650):
    # Create a canvas and a vertical scrollbar for scrolling
    canvas = tk.Canvas(root, borderwidth=0, background=BG_GRADIENT, width=width, height=height)
    v_scroll = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=v_scroll.set)

    canvas.pack(side="left", fill="both", expand=True)
    v_scroll.pack(side="right", fill="y")

    # Frame inside the canvas for widgets
    scroll_frame = tk.Frame(canvas, background=BG_GRADIENT)
    scroll_frame_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

    # Function to update scrollregion
    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    scroll_frame.bind("<Configure>", on_frame_configure)

    # Mousewheel scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Resize the inner frame when the window size changes
    def on_canvas_configure(event):
        canvas.itemconfig(scroll_frame_id, width=event.width)
    canvas.bind("<Configure>", on_canvas_configure)

    return scroll_frame, canvas

root = tk.Tk()
root.withdraw()
download_folder = filedialog.askdirectory(title="📁 Select download folder")
if not download_folder:
    messagebox.showwarning("⚠️ Cancelled", "No folder selected. Exiting.")
    sys.exit()

root.deiconify()
root.title("🎬 Video Downloader")
root.geometry("950x650")
root.configure(bg=BG_GRADIENT)
root.protocol("WM_DELETE_WINDOW", root.quit)

# Make scrollable root
scroll_frame, canvas = make_scrollable_root(root)

# Use modern themed style
style = ttk.Style()
style.theme_use("clam")
style.configure("TButton",
    padding=7,
    relief="flat",
    background=DARK_COLOR,
    foreground=SECONDARY_COLOR,
    font=FONT,
    borderwidth=2,
    borderradius=5,
)

style.map("TButton",
    background=[("active", SECONDARY_COLOR), ("disabled", "#b7c5dc")],
    foreground=[("active", DARK_COLOR), ("disabled", "#a0a0a0")],
    relief=[("active", "solid"), ("!pressed", "flat")],
    bordercolor=[("active", DARK_COLOR), ("!active", DARK_COLOR)],
    borderwidth=[("active", 2), ("!active", 2)],
    borderradius=[("active", 5), ("!active", 5)]
)
style.configure("TLabel", background=BG_GRADIENT, foreground=ACCENT_COLOR, font=LABEL_FONT)
style.configure("TCombobox",
    padding=6,
    selectbackground=DARK_COLOR,
    selectforeground=SECONDARY_COLOR,
    fieldbackground=SECONDARY_COLOR,
    background=DARK_COLOR,
    font=FONT
)
style.configure("TLabelframe", background=BG_GRADIENT, foreground=DARK_COLOR)
style.configure("TLabelframe.Label", font=HEADER_FONT, background=BG_GRADIENT, foreground=ACCENT_COLOR)

SUPPORTED_SITES = {
    "YouTube": ["youtube.com", "youtu.be"], "Vimeo": ["vimeo.com"],
    "TikTok": ["tiktok.com"], "Instagram": ["instagram.com"],
    "Twitter/X": ["twitter.com", "x.com"], "Reddit": ["reddit.com"],
    "SoundCloud": ["soundcloud.com"], "Dailymotion": ["dailymotion.com"],
    "Facebook": ["facebook.com"], "Other": []
}

def detect_platform(url):
    hostname = urlparse(url).hostname or ""
    hostname = hostname.replace("www.", "")
    for platform, domains in SUPPORTED_SITES.items():
        if any(domain in hostname for domain in domains):
            return platform
    return "Other"

# ---------------------- UI Layout ----------------------
def add_shadow(widget, color="#b5d0f7"):
    widget.update_idletasks()
    x, y, w, h = widget.winfo_x(), widget.winfo_y(), widget.winfo_width(), widget.winfo_height()
    shadow = tk.Frame(widget.master, bg=color, width=w, height=6)
    shadow.place(x=x, y=y+h)
    return shadow

def create_header(parent):
    header_frame = tk.Frame(parent, bg=DARK_COLOR, height=64)
    header_frame.pack(fill="x")
    logo = tk.Label(header_frame, text="🎬", font=("Segoe UI Emoji", 26), bg=DARK_COLOR, fg=SECONDARY_COLOR)
    logo.pack(side="left", padx=16, pady=10)
    title = tk.Label(header_frame, text="Video Downloader", font=("Segoe UI Semibold", 18), bg=DARK_COLOR, fg=SECONDARY_COLOR)
    title.pack(side="left", padx=(0, 20), pady=10)
    return header_frame

create_header(scroll_frame)

url_frame = ttk.Labelframe(scroll_frame, text="📋 Paste video URLs (one per line)", padding=(16, 12))
url_frame.pack(padx=18, pady=12, fill="x")
textbox = tk.Text(url_frame, width=100, height=7, font=FONT, highlightbackground=DARK_COLOR, relief="flat", bg=LIGHT_COLOR, fg=ACCENT_COLOR, insertbackground=DARK_COLOR)
textbox.pack(padx=6, pady=6, fill="x")

btn_frame = tk.Frame(scroll_frame, bg=BG_GRADIENT)
btn_frame.pack(padx=10, pady=4)
ttk.Button(btn_frame, text="➕ Set Format Options", command=lambda: prepare_links(custom=True)).pack(side="left", padx=10)
ttk.Button(btn_frame, text="🚀 Start Download", command=lambda: start_download()).pack(side="left", padx=4)
ttk.Button(btn_frame, text="🔄 Reset", command=lambda: reset_ui()).pack(side="left", padx=10)

tk.Label(scroll_frame, text="🔁 Max Concurrent Downloads:", font=LABEL_FONT, bg=BG_GRADIENT, fg=ACCENT_COLOR).pack()
thread_count_var = tk.IntVar(value=2)
thread_count_menu = ttk.Combobox(scroll_frame, values=[1, 2, 3, 4, 5], state="readonly", textvariable=thread_count_var, width=5)
thread_count_menu.pack(pady=2)

preview_frame = ttk.Labelframe(scroll_frame, text="📄 Video Info & Format Selection", padding=(16, 12))
preview_frame.pack(padx=18, pady=12, fill="both")
entry_widgets = []
metadata_cache = {}
fetch_cancel_flag = False

progress_frame = ttk.Labelframe(scroll_frame, text="📥 Download Progress", padding=(16, 12))
progress_frame.pack(padx=18, pady=12, fill="both", expand=True)
progress_labels = []
queue_out = queue.Queue()
completed, failed = [], []

def format_duration(seconds):
    try:
        seconds = int(seconds)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
    except:
        return "--:--"

def cancel_metadata(spinner_label, cancel_btn):
    global fetch_cancel_flag
    fetch_cancel_flag = True
    spinner_label.config(text="❌ Metadata fetch cancelled.", fg="#d42a2a")
    cancel_btn.destroy()

def prepare_links(custom=False):
    global fetch_cancel_flag
    for widget in preview_frame.winfo_children():
        widget.destroy()
    entry_widgets.clear()
    fetch_cancel_flag = False

    links = textbox.get("1.0", tk.END).strip().splitlines()
    if not links:
        messagebox.showwarning("⚠️ No Input", "Paste at least one URL.")
        return

    spinner_label = tk.Label(preview_frame, text="⏳ Fetching metadata...", font=LABEL_FONT, bg=BG_GRADIENT, fg=DARK_COLOR)
    spinner_label.pack(anchor="w", pady=3)
    cancel_btn = ttk.Button(preview_frame, text="❌ Cancel", command=lambda: cancel_metadata(spinner_label, cancel_btn))
    cancel_btn.pack(anchor="e", pady=2)

    def fetch(url, idx):
        if fetch_cancel_flag: return
        try:
            if url in metadata_cache:
                meta = metadata_cache[url]
            else:
                res = subprocess.run(["yt-dlp", "--dump-json", "--skip-download", url],
                                     capture_output=True, text=True, timeout=30, check=True)
                meta = json.loads(res.stdout)
                metadata_cache[url] = meta
        except:
            meta = {"error": True}
        if fetch_cancel_flag: return

        if "error" in meta:
            text = "❌ Failed to fetch info"
        elif meta.get("_type") == "playlist":
            title = meta.get("title", "Playlist")
            count = len(meta.get("entries", []))
            duration = format_duration(sum(e.get("duration", 0) for e in meta["entries"] if isinstance(e, dict)))
            text = f"📃 {title} ({count} videos, {duration})"
        else:
            title = meta.get("title", "Unknown")
            duration = format_duration(meta.get("duration", 0))
            size = meta.get("filesize") or meta.get("filesize_approx")
            size_str = f"{round(int(size)/1024/1024, 1)} MB" if size else "~"
            text = f"🎞 {title} ({size_str}, {duration})"

        row = tk.Frame(preview_frame, bg=LIGHT_COLOR)
        row.pack(fill="x", padx=2, pady=3)
        lbl = tk.Label(row, text=text[:80] + ("..." if len(text) > 80 else ""), anchor="w", width=80, font=LABEL_FONT, bg=LIGHT_COLOR, fg=ACCENT_COLOR)
        lbl.pack(side="left", padx=6, pady=1)

        if custom:
            format_list = ["MP4 - 2160p", "MP4 - 1080p", "MP4 - 720p", "MP3 - best"]
        else:
            format_list = ["MP4", "MP3"]

        combo = ttk.Combobox(row, values=format_list, state="readonly", width=15, font=FONT)
        combo.set("MP4 - 1080p" if custom else "MP4")
        combo.pack(side="right", padx=4, pady=1)

        entry_widgets.append((url, combo, lbl))

        if idx == len(links) - 1:
            spinner_label.config(text="✅ Metadata loaded.", fg="#2ad47a")
            cancel_btn.destroy()

    for idx, url in enumerate(links):
        threading.Thread(target=fetch, args=(url.strip(), idx), daemon=True).start()

def reset_ui():
    textbox.delete("1.0", tk.END)
    for lbl in progress_labels:
        lbl.destroy()
    progress_labels.clear()
    entry_widgets.clear()
    metadata_cache.clear()
    completed.clear()
    failed.clear()
    for widget in preview_frame.winfo_children():
        widget.destroy()

def download_worker(idx, url, fmt):
    try:
        platform = detect_platform(url)
        is_playlist = "playlist" in url.lower()
        output = os.path.join(download_folder, "%(playlist_title)s" if is_playlist else "", "%(title)s.%(ext)s")
        output = output.replace("\\", "/")

        cmd = ["yt-dlp", "-o", output]

        if "MP3" in fmt:
            cmd += ["-f", "bestaudio", "--extract-audio", "--audio-format", "mp3"]
        else:
            cmd += ["--write-auto-subs", "--write-subs", "--sub-langs", "en", "--sub-format", "srt"]
            if "2160p" in fmt:
                cmd += ["-f", "bv[height<=2160]+ba/b", "--merge-output-format", "mp4", "--embed-subs"]
            elif "1080p" in fmt:
                cmd += ["-f", "bv[height<=1080]+ba/b", "--merge-output-format", "mp4", "--embed-subs"]
            elif "720p" in fmt:
                cmd += ["-f", "bv[height<=720]+ba/b", "--merge-output-format", "mp4", "--embed-subs"]
            else:
                cmd += ["-f", "bv[height<=1080]+ba/b", "--merge-output-format", "mp4", "--embed-subs"]

        queue_out.put(("status", idx, url, f"⬇️ Downloading from {platform}..."))
        proc = subprocess.Popen(cmd + [url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            queue_out.put(("progress", idx, url, line.strip()))
        if proc.wait() == 0:
            queue_out.put(("success", idx, url, "✔️ Done"))
        else:
            queue_out.put(("fail", idx, url, "❌ Download error"))
    except Exception as e:
        queue_out.put(("fail", idx, url, f"❌ {str(e)}"))

def process_queue():
    try:
        while True:
            msg_type, idx, url, msg = queue_out.get_nowait()
            if idx is not None and idx < len(progress_labels):
                color = "#2ad47a" if "Done" in msg or "success" in msg_type else ("#d42a2a" if "❌" in msg else ACCENT_COLOR)
                progress_labels[idx].config(text=f"{msg}", fg=color)
            if msg_type == "success":
                completed.append(url)
            elif msg_type == "fail":
                failed.append(url)
    except queue.Empty:
        pass
    root.after(300, process_queue)

def start_download():
    urls = textbox.get("1.0", tk.END).strip().splitlines()
    if not urls:
        messagebox.showwarning("⚠️ Empty", "Paste at least one URL.")
        return

    # Check if format options are set; if not, use default format with ThreadPool
    if not entry_widgets or all(fmt_box is None for _, fmt_box, _ in entry_widgets):
        for lbl in progress_labels:
            lbl.destroy()
        progress_labels.clear()

        for idx, url in enumerate(urls):
            lbl = tk.Label(progress_frame, text=f"🔄 Waiting: {url[:60]}", anchor="w", font=LABEL_FONT, bg=LIGHT_COLOR, fg=ACCENT_COLOR)
            lbl.pack(fill="x", padx=2, pady=2)
            progress_labels.append(lbl)

        class ThreadPool:
            def __init__(self, max_threads):
                self.max = max_threads
                self.q = deque()
                self.active = 0

            def add(self, job):
                self.q.append(job)
                self.try_start()

            def try_start(self):
                while self.active < self.max and self.q:
                    self.active += 1
                    threading.Thread(target=self.worker, args=(self.q.popleft(),)).start()

            def worker(self, job):
                try:
                    job()
                finally:
                    self.active -= 1
                    self.try_start()

        pool = ThreadPool(thread_count_var.get())
        for idx, url in enumerate(urls):
            pool.add(lambda i=idx, u=url: download_worker(i, u, "MP4 - 1080p"))
        root.after(300, process_queue)
    else:
        root.after(1000, continue_download, urls)

def continue_download(urls):
    for lbl in progress_labels:
        lbl.destroy()
    progress_labels.clear()

    if len(entry_widgets) != len(urls):
        entry_widgets.clear()
        for url in urls:
            entry_widgets.append((url, None, None))

    for idx, (url, fmt_box, _) in enumerate(entry_widgets):
        lbl = tk.Label(progress_frame, text=f"🔄 Waiting: {url[:60]}", anchor="w", font=LABEL_FONT, bg=LIGHT_COLOR, fg=ACCENT_COLOR)
        lbl.pack(fill="x", padx=2, pady=2)
        progress_labels.append(lbl)

    class ThreadPool:
        def __init__(self, max_threads):
            self.max = max_threads
            self.q = deque()
            self.active = 0

        def add(self, job):
            self.q.append(job)
            self.try_start()

        def try_start(self):
            while self.active < self.max and self.q:
                self.active += 1
                threading.Thread(target=self.worker, args=(self.q.popleft(),)).start()

        def worker(self, job):
            try:
                job()
            finally:
                self.active -= 1
                self.try_start()

    pool = ThreadPool(thread_count_var.get())
    for idx, (url, fmt_box, _) in enumerate(entry_widgets):
        fmt = fmt_box.get() if fmt_box else "MP4 - 1080p"
        pool.add(lambda i=idx, u=url, f=fmt: download_worker(i, u, f))

    root.after(300, process_queue)

root.mainloop()