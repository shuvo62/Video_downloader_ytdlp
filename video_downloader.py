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

# ---------------------- GUI Setup ----------------------
root = tk.Tk()
root.withdraw()
download_folder = filedialog.askdirectory(title="📁 Select download folder")
if not download_folder:
    messagebox.showwarning("⚠️ Cancelled", "No folder selected. Exiting.")
    sys.exit()

root.deiconify()
root.title("🎬 Video Downloader")
root.geometry("950x650")
root.configure(bg="#f0f2f5")
root.protocol("WM_DELETE_WINDOW", root.quit)

style = ttk.Style()
style.theme_use("clam")
style.configure("TButton", padding=6, relief="flat", background="#0078D7", foreground="white")
style.configure("TLabel", background="#f0f2f5")
style.configure("TCombobox", padding=5)

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
url_frame = tk.LabelFrame(root, text="📋 Paste video URLs (one per line)", padx=10, pady=10)
url_frame.pack(padx=15, pady=10, fill="x")
textbox = tk.Text(url_frame, width=100, height=8, font=("Segoe UI", 10))
textbox.pack()

btn_frame = tk.Frame(root, bg="#f0f2f5")
btn_frame.pack(pady=5)
tk.Button(btn_frame, text="➕ Set Format Options", command=lambda: prepare_links(custom=True), font=("Segoe UI", 10)).pack(side="left", padx=10)
tk.Button(btn_frame, text="🚀 Start Download", command=lambda: start_download(), font=("Segoe UI", 10)).pack(side="left")
tk.Button(btn_frame, text="🔄 Reset", command=lambda: reset_ui(), font=("Segoe UI", 10)).pack(side="left", padx=10)

tk.Label(root, text="🔁 Max Concurrent Downloads:", font=("Segoe UI", 10), bg="#f0f2f5").pack()
thread_count_var = tk.IntVar(value=2)
thread_count_menu = ttk.Combobox(root, values=[1, 2, 3, 4, 5], state="readonly", textvariable=thread_count_var, width=5)
thread_count_menu.pack()

preview_frame = tk.LabelFrame(root, text="📄 Video Info & Format Selection", padx=10, pady=10)
preview_frame.pack(padx=15, pady=10, fill="both")
entry_widgets = []
metadata_cache = {}
fetch_cancel_flag = False

progress_frame = tk.LabelFrame(root, text="📥 Download Progress", padx=10, pady=10)
progress_frame.pack(padx=15, pady=10, fill="both", expand=True)
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
    spinner_label.config(text="❌ Metadata fetch cancelled.")
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

    spinner_label = tk.Label(preview_frame, text="⏳ Fetching metadata..."); spinner_label.pack()
    cancel_btn = tk.Button(preview_frame, text="❌ Cancel", command=lambda: cancel_metadata(spinner_label, cancel_btn))
    cancel_btn.pack(anchor="e")

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

        row = tk.Frame(preview_frame); row.pack(fill="x", pady=2)
        lbl = tk.Label(row, text=text[:80] + ("..." if len(text) > 80 else ""), anchor="w", width=80)
        lbl.pack(side="left")

        if custom:
            format_list = ["MP4 - 2160p", "MP4 - 1080p", "MP4 - 720p", "MP3 - best"]
        else:
            format_list = ["MP4", "MP3"]

        combo = ttk.Combobox(row, values=format_list, state="readonly", width=15)
        combo.set("MP4 - 1080p" if custom else "MP4")
        combo.pack(side="right")

        entry_widgets.append((url, combo, lbl))

        if idx == len(links) - 1:
            spinner_label.config(text="✅ Metadata loaded.")
            cancel_btn.destroy()

    for idx, url in enumerate(links):
        threading.Thread(target=fetch, args=(url.strip(), idx), daemon=True).start()

def reset_ui():
    textbox.delete("1.0", tk.END)
    for lbl in progress_labels:
        lbl.destroy()
    progress_labels.clear()
    entry_widgets.clear()
    metadata_cache.clear()  # Clear cached metadata to avoid stale data
    completed.clear()
    failed.clear()
    # Clear preview frame to remove old metadata
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
            # Add subtitle options only for video formats
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
                progress_labels[idx].config(text=f"{msg}")
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
            lbl = tk.Label(progress_frame, text=f"🔄 Waiting: {url[:60]}", anchor="w")
            lbl.pack(fill="x")
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
            pool.add(lambda i=idx, u=url: download_worker(i, u, "MP4 - 1080p"))  # Default to 1080p
        root.after(300, process_queue)
    else:
        root.after(1000, continue_download, urls)  # Restore 1000ms delay

def continue_download(urls):
    # Clear previous progress labels
    for lbl in progress_labels:
        lbl.destroy()
    progress_labels.clear()

    # Ensure entry_widgets matches URLs
    if len(entry_widgets) != len(urls):
        entry_widgets.clear()
        for url in urls:
            entry_widgets.append((url, None, None))

    for idx, (url, fmt_box, _) in enumerate(entry_widgets):
        lbl = tk.Label(progress_frame, text=f"🔄 Waiting: {url[:60]}", anchor="w")
        lbl.pack(fill="x")
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
        fmt = fmt_box.get() if fmt_box else "MP4 - 1080p"  # Use selected format or default
        pool.add(lambda i=idx, u=url, f=fmt: download_worker(i, u, f))

    root.after(300, process_queue)

root.mainloop()