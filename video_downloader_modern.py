"""
Fixed Video Downloader GUI using yt-dlp and PyQt6
- Safer MP4 format selection to avoid WebM/Opus remux failures
- URL sanitization (removes noisy share params like `si`)
- Writes per-download log files so you can inspect yt-dlp output
- Uses full path to yt-dlp binary when available
- Better ffmpeg dependency error handling (requests binary install)

Save this file and run with Python (requires PyQt6 and yt-dlp installed).
"""

import threading, queue, sys, shutil, os, subprocess, json
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QTextEdit, QScrollArea, QComboBox, QHBoxLayout, QMessageBox, QFrame, QFileDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

# ---------- UI constants ----------
DARK_BLUE = "#004080"
LIGHT_BLUE = "#0069D2"
ORANGE = "#FF5F15"
LIGHT_GRAY = "#F0F0F0"
CONFIG_FILE = os.path.expanduser("~/.video_downloader_config.json")

modern_scrollbar_style = f"""
QScrollBar:vertical {{
    border: none;
    background: {LIGHT_GRAY};
    width: 14px;
    margin: 0px 0px 0px 0px;
    border-radius: 7px;
}}
QScrollBar::handle:vertical {{
    background: {DARK_BLUE};
    min-height: 40px;
    border-radius: 7px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    border: none;
    background: {LIGHT_GRAY};
    height: 14px;
    margin: 0px 0px 0px 0px;
    border-radius: 7px;
}}
QScrollBar::handle:horizontal {{
    background: {DARK_BLUE};
    min-width: 40px;
    border-radius: 7px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}
QScrollBar::handle:vertical:hover {{
  background: {LIGHT_BLUE};
}}
QScrollBar::handle:horizontal:hover {{
  background: {LIGHT_BLUE};
}}
"""

SUPPORTED_SITES = {
    "YouTube": ["youtube.com", "youtu.be"], "Vimeo": ["vimeo.com"],
    "TikTok": ["tiktok.com"], "Instagram": ["instagram.com"],
    "Twitter/X": ["twitter.com", "x.com"], "Reddit": ["reddit.com"],
    "SoundCloud": ["soundcloud.com"], "Dailymotion": ["dailymotion.com"],
    "Facebook": ["facebook.com"], "Other": []
}

button_style = f"""
    QPushButton {{
        background-color: {DARK_BLUE};
        color: white;
        font-weight: bold;
        padding: 10px;
        border-radius: 8px;
    }}
    QPushButton:hover {{
        background-color: white;
        color: {DARK_BLUE};
        font-weight: bold;
        padding: 10px;
        border: 2px solid {DARK_BLUE};
        border-radius: 8px;
    }}
"""

# ---------- Utilities ----------

def save_last_folder(folder_path):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"last_folder": folder_path}, f)
    except Exception:
        pass


def load_last_folder():
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_folder", "")
    except Exception:
        return ""


def show_dep_error(pkg):
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("❌ Dependency Error")
    # Be explicit what binary is required
    if pkg == "ffmpeg":
        msg.setText("🚫 ffmpeg binary not found. Please install ffmpeg (system binary).\nWindows: winget install Gyan.FFmpeg or download from gyan.dev\nLinux: apt/yum/pacman install ffmpeg")
    else:
        msg.setText(f"🚫 {pkg} could not be installed. Please install it manually.")
    msg.exec()
    sys.exit(1)


def detect_platform(url):
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.replace("www.", "")
        for platform, domains in SUPPORTED_SITES.items():
            if any(domain in hostname for domain in domains):
                return platform
        return "Other"
    except Exception:
        return "Other"


def format_duration(seconds):
    try:
        seconds = int(seconds)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
    except:
        return "--:--"


# sanitize share params (strip noisy tokens like si, feature)
def sanitize_url(u: str) -> str:
    try:
        s = urlsplit(u.strip())
        qs = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if k.lower() not in {"si", "feature"}]
        return urlunsplit((s.scheme or 'https', s.netloc, s.path, urlencode(qs), s.fragment))
    except Exception:
        return u


# Choose an MP4-safe format selector (prefers mp4 + m4a, falls back safely)
def format_for(fmt: str):
    # audio
    if "MP3" in fmt:
        return ["-f", "bestaudio/best", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]

    # target max resolution
    if "2160" in fmt:
        res = 2160
    elif "1080" in fmt:
        res = 1080
    elif "720" in fmt:
        res = 720
    else:
        res = 1080

    # prefer mp4 container with m4a audio; fallback to best mp4; then best
    selector = (f"bestvideo[ext=mp4][height<={res}]+bestaudio[ext=m4a]/"
                f"best[ext=mp4][height<={res}]/best[height<={res}]/best")
    return ["-f", selector, "--merge-output-format", "mp4", "--embed-subs"]


# Find yt-dlp binary path (use full path if available)
YTDLP_BIN = shutil.which("yt-dlp") or "yt-dlp"

# ---------- Thread pool ----------
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
            threading.Thread(target=self.worker, args=(self.q.popleft(),), daemon=True).start()

    def worker(self, job):
        try:
            job()
        finally:
            self.active -= 1
            self.try_start()


# ---------- Main Window ----------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Downloader")
        self.download_folder = load_last_folder()
        self.metadata_cache = {}
        self.setGeometry(250, 100, 1000, 700)
        self.setFixedSize(1000, 700)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {LIGHT_GRAY};
            }}
        """)
        self.entry_widgets = []
        self.progress_labels = []
        self.completed = []
        self.failed = []
        self.queue_out = queue.Queue()
        self.pool = None
        self.metadata_queue = queue.Queue()
        self.metadata_threads = []
        self.metadata_cancel_flag = False
        self.metadata_links = []
        self.metadata_links_count = 0
        self.metadata_custom = False
        self.metadata_loading_widgets = []
        self.metadata_loading_cancel_btn = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area Setup
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        scroll_layout = QVBoxLayout(content_widget)
        scroll_layout.setContentsMargins(20, 20, 20, 20)
        scroll_layout.setSpacing(10)

        # Header
        header = QLabel("🚀 Video Downloader!")
        header.setFixedSize(950, 100)
        header.setFont(QFont("Play", 20))
        header.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        header.setStyleSheet(f"background-color: {DARK_BLUE}; color: white; padding: 10px; font-weight: bold;")

        # Download folder label & button
        self.download_label = QLabel("No folder selected")
        self.download_label.setStyleSheet("color: gray; font-style: italic;")
        self.download_label.setFont(QFont("Play", 12))
        button_select_folder = QPushButton("📁 Select Download Folder")
        button_select_folder.setStyleSheet(button_style)
        button_select_folder.setFont(QFont("Play", 14))
        button_select_folder.setFixedHeight(50)
        button_select_folder.setFixedWidth(300)
        button_select_folder.clicked.connect(self.select_folder)
        if self.download_folder:
            self.download_label.setText(self.download_folder)
        else:
            self.download_label.setText("No folder selected")

        # Description label
        label = QLabel("📋 Paste one or multiple URLs/playlists per line!")
        label.setFont(QFont("Play", 16))
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        label.setStyleSheet(f"color: {DARK_BLUE}; padding: 10px; font-weight: bold;")
        label.setFixedHeight(50)

        # TextEdit for URLs
        self.url_input = QTextEdit()
        self.url_input.setStyleSheet(f"border: 2px solid {DARK_BLUE}; border-radius: 5px; padding: 5px;")
        self.url_input.setPlaceholderText("Paste URLs here, one per line...")
        self.url_input.setFont(QFont("Play", 12))
        self.url_input.setFixedHeight(200)

        # Format option button
        self.button_setFormat = QPushButton("🎯 Set Format Option")
        self.button_setFormat.setStyleSheet(button_style)
        self.button_setFormat.setFont(QFont("Play", 14))
        self.button_setFormat.setFixedHeight(50)
        self.button_setFormat.setFixedWidth(250)
        self.button_setFormat.clicked.connect(lambda: self.prepare_links(custom=True))

        # Start download button
        self.button_startDownload = QPushButton("📥 Start Download")
        self.button_startDownload.setStyleSheet(button_style)
        self.button_startDownload.setFont(QFont("Play", 14))
        self.button_startDownload.setFixedHeight(50)
        self.button_startDownload.setFixedWidth(250)
        self.button_startDownload.clicked.connect(self.start_download)

        # Reset button
        self.button_reset = QPushButton("🔄 Reset")
        self.button_reset.setStyleSheet(button_style)
        self.button_reset.setFont(QFont("Play", 14))
        self.button_reset.setFixedHeight(50)
        self.button_reset.setFixedWidth(250)
        self.button_reset.clicked.connect(self.reset_ui)

        label_concurrent = QLabel("⚡ Max Concurrent Downloads:")
        label_concurrent.setAlignment(Qt.AlignmentFlag.AlignLeft)
        label_concurrent.setFont(QFont("Play", 16))
        label_concurrent.setStyleSheet(f"color: {DARK_BLUE}; padding: 10px; font-weight: bold;")
        label_concurrent.setFixedHeight(50)

        self.combo = QComboBox()
        self.combo.setStyleSheet(f"border: 2px solid {DARK_BLUE}; border-radius: 5px; padding: 5px;")
        self.combo.addItems([str(i) for i in range(1, 6)])
        self.combo.setCurrentIndex(2) # Default to 3 concurrent downloads.
        self.combo.setFixedWidth(50)
        self.combo.setFont(QFont("Play", 14))

        combo_layout = QHBoxLayout()
        combo_layout.addWidget(label_concurrent)
        combo_layout.addWidget(self.combo)
        combo_layout.addStretch()

        self.result_label = QLabel("")
        self.result_label.setFont(QFont("Play", 14))
        self.result_label.setStyleSheet("color: green; font-weight: bold;")

        self.video_info_label = QLabel("✨ Video Info & Format Selection")
        self.video_info_label.setFont(QFont("Play", 14))
        self.video_info_label.setStyleSheet(f"color: {DARK_BLUE}; font-weight: bold;")

        # Preview Area (for video info and format selection)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setFixedHeight(160)  # adjust as needed
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_widget = QWidget()
        self.preview_widget.setStyleSheet(f"border: 1px solid {DARK_BLUE}; border-radius: 5px; background-color: {LIGHT_GRAY}; padding: 10px;")
        self.preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_scroll.setWidget(self.preview_widget)

        self.download_progress_label = QLabel("📥 Download Progress")
        self.download_progress_label.setFont(QFont("Play", 14))
        self.download_progress_label.setStyleSheet(f"color: {DARK_BLUE}; font-weight: bold;")

        # Progress Area (for download progress)
        self.progress_scroll = QScrollArea()
        self.progress_scroll.setWidgetResizable(True)
        self.progress_scroll.setFixedHeight(160)  # adjust as needed
        self.progress_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.progress_widget = QWidget()
        self.progress_widget.setStyleSheet(f"border: 1px solid {DARK_BLUE}; border-radius: 5px; background-color: {LIGHT_GRAY}; padding: 10px;")
        self.progress_layout = QVBoxLayout(self.progress_widget)
        self.progress_layout.setContentsMargins(0, 20, 0, 20)
        self.progress_scroll.setWidget(self.progress_widget)

        # Add widgets in order
        scroll_layout.addWidget(header)
        scroll_layout.addWidget(button_select_folder, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(self.download_label, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(label)
        scroll_layout.addWidget(self.url_input)
        scroll_layout.addWidget(self.button_setFormat, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(self.button_startDownload, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(self.button_reset, alignment=Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addLayout(combo_layout)
        scroll_layout.addWidget(self.result_label)
        scroll_layout.addWidget(self.video_info_label, alignment=Qt.AlignmentFlag.AlignLeft)
        scroll_layout.addWidget(self.preview_scroll)
        scroll_layout.addWidget(self.download_progress_label, alignment=Qt.AlignmentFlag.AlignLeft)
        scroll_layout.addWidget(self.progress_scroll)
        scroll_layout.addStretch(1)
        main_layout.addWidget(scroll_area)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", os.path.expanduser("~"))
        if folder:
            self.download_folder = folder
            self.download_label.setText(folder)
            save_last_folder(folder)
        else:
            self.download_label.setText("No folder selected")
            self.download_folder = ""

    def prepare_links(self, custom=False):
        # Clear preview frame
        for i in reversed(range(self.preview_layout.count())):
            widget = self.preview_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.entry_widgets.clear()
        self.metadata_cancel_flag = False
        raw_links = [l.strip() for l in self.url_input.toPlainText().strip().splitlines() if l.strip()]
        self.metadata_links = [sanitize_url(l) for l in raw_links]
        self.metadata_links_count = len(self.metadata_links)
        self.metadata_custom = custom
        if not self.metadata_links:
            self.show_warning("⚠️ No Input", "Paste at least one URL.")
            return

        # Add loading spinner and cancel button
        spinner_label = QLabel("⏳ Fetching metadata...")
        spinner_label.setFont(QFont("Play", 14))
        spinner_label.setStyleSheet(f"color: {ORANGE}; font-weight: bold;")
        self.preview_layout.addWidget(spinner_label)
        self.metadata_loading_widgets = [spinner_label]
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.setStyleSheet(button_style)
        cancel_btn.clicked.connect(self.cancel_metadata_loading)
        self.preview_layout.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.metadata_loading_cancel_btn = cancel_btn

        # Start threads for metadata fetching
        for idx, url in enumerate(self.metadata_links):
            t = threading.Thread(target=self.metadata_fetch_worker, args=(url, idx, custom), daemon=True)
            t.start()
            self.metadata_threads.append(t)

        # Start polling the queue for results
        QTimer.singleShot(100, self.metadata_poll_queue)

    def cancel_metadata_loading(self):
        self.metadata_cancel_flag = True
        # Disable cancel button and show cancelled
        if self.metadata_loading_widgets:
            self.metadata_loading_widgets[0].setText("❌ Metadata fetch cancelled.")
        if self.metadata_loading_cancel_btn:
            self.metadata_loading_cancel_btn.setDisabled(True)

    def metadata_fetch_worker(self, url, idx, custom):
        if self.metadata_cancel_flag:
            return
        try:
            if url in self.metadata_cache:
                meta = self.metadata_cache[url]
            else:
                res = subprocess.run(
                    [YTDLP_BIN, "--dump-json", "--skip-download", url],
                    capture_output=True, text=True, timeout=40, check=True)
                meta = json.loads(res.stdout)
                self.metadata_cache[url] = meta
        except Exception:
            meta = {"error": True}
        # Push result to the queue
        if not self.metadata_cancel_flag:
            self.metadata_queue.put((url, idx, meta, custom))

    def metadata_poll_queue(self):
        while True:
            try:
                url, idx, meta, custom = self.metadata_queue.get_nowait()
                self.metadata_display_result(url, idx, meta, custom)
            except queue.Empty:
                break
        # If all results are in or cancelled, update spinner label and cancel btn
        if (len(self.entry_widgets) == self.metadata_links_count or self.metadata_cancel_flag):
            if self.metadata_loading_widgets:
                if self.metadata_cancel_flag:
                    self.metadata_loading_widgets[0].setText("❌ Metadata fetch cancelled.")
                else:
                    self.metadata_loading_widgets[0].setText("✅ Metadata loaded.")
            if self.metadata_loading_cancel_btn:
                self.metadata_loading_cancel_btn.setDisabled(True)
        else:
            # Keep polling until done
            QTimer.singleShot(100, self.metadata_poll_queue)

    def metadata_display_result(self, url, idx, meta, custom):
        # Remove spinner/cancel from preview area (once)
        if self.metadata_loading_widgets:
            for w in self.metadata_loading_widgets:
                w.deleteLater()
            self.metadata_loading_widgets = []
            if self.metadata_loading_cancel_btn:
                self.metadata_loading_cancel_btn.deleteLater()
                self.metadata_loading_cancel_btn = None

        if "error" in meta:
            text = "❌ Failed to fetch info"
            title = "Unknown"
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

        row = QHBoxLayout()
        lbl = QLabel(text if len(text) < 80 else text[:80] + "...")
        lbl.setMinimumWidth(400)
        lbl.setFont(QFont("Play", 14))
        row.addWidget(lbl)
        if custom:
            format_list = ["MP4 - 2160p", "MP4 - 1080p", "MP4 - 720p", "MP3 - best"]
        else:
            format_list = ["MP4", "MP3"]
        combo = QComboBox()
        combo.addItems(format_list)
        combo.setCurrentText("MP4 - 1080p" if custom else "MP4")
        combo.setFont(QFont("Play", 12))
        combo.setFixedWidth(150)
        row.addWidget(combo)
        frame = QFrame()
        frame.setLayout(row)
        self.preview_layout.addWidget(frame)
        self.entry_widgets.append((url, combo, lbl, title))  # url, combo, lbl, title

    def reset_ui(self):
        self.url_input.clear()
        for i in reversed(range(self.progress_layout.count())):
            widget = self.progress_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        for i in reversed(range(self.preview_layout.count())):
            widget = self.preview_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.progress_labels.clear()
        self.entry_widgets.clear()
        self.metadata_cache.clear()
        self.completed.clear()
        self.failed.clear()
        self.result_label.setText("")

    def download_worker(self, idx, url, fmt, title):
        try:
            platform = detect_platform(url)
            # Detect playlist by metadata instead of "playlist" in url
            meta = self.metadata_cache.get(url, {})
            is_playlist = meta.get("_type") == "playlist"
            output = os.path.join(self.download_folder or ".", "%(playlist_title)s" if is_playlist else "", "%(title)s.%(ext)s")
            output = output.replace("\\", "/")

            # logs
            safe_name = title.replace("/", "_").replace("\\", "_")[:80]
            log_dir = os.path.join(self.download_folder or ".", "yt-dlp-logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"yt-dlp-{idx}-{safe_name}.log")

            cmd = [YTDLP_BIN, "-o", output]

            # Subs always requested for video formats
            if "MP3" in fmt:
                cmd += ["-f"] + ["bestaudio/best", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
            else:
                # ask for subtitles (silent if not available)
                cmd += ["--write-auto-subs", "--write-subs", "--sub-langs", "en", "--sub-format", "srt"]
                cmd += format_for(fmt)

            # Add network retries to be robust
            cmd += ["--retries", "3", "--fragment-retries", "3"]

            self.queue_out.put(("status", idx, url, f'<span style="color: {DARK_BLUE}; font-size: 16px; font-family: Play; font-weight: bold;">⬇️ Downloading from {platform}...</span>'))

            # Launch and write combined output to log
            with open(log_path, "w", encoding="utf-8", errors="ignore") as lf:
                proc = subprocess.Popen(cmd + [url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    lf.write(line)
                    lf.flush()
                    styled_line = f'<span style="color: {ORANGE}; font-size: 16px; font-family: Play; font-weight: bold;">⏳ {line.strip()}</span>'
                    self.queue_out.put(("progress", idx, url, styled_line))
                ret = proc.wait()

            if ret == 0:
                self.queue_out.put(("success", idx, url, f'<span style="color: green; font-size: 16px; font-family: Play; font-weight: bold;">✅ Done: {title}</span>'))
            else:
                self.queue_out.put(("fail", idx, url, f'<span style="color: red; font-size: 16px; font-family: Play; font-weight: bold;">❌ Download error: {title}<br>See log: {log_path}</span>'))
                print(f"Error downloading {url}: Process exited with code {ret}. See {log_path}")
        except Exception as e:
            self.queue_out.put(("fail", idx, url, f"❌ {str(e)}: {title}"))

    def process_queue(self):
        try:
            while True:
                msg_type, idx, url, msg = self.queue_out.get_nowait()
                if idx is not None and idx < len(self.progress_labels):
                    display = msg[:180] + ('...' if len(msg) > 180 else '')
                    self.progress_labels[idx].setText(display)
        except queue.Empty:
            pass

        all_done = all(
            ('Done:' in label.text() or 'Download error' in label.text() or '❌' in label.text())
            for label in self.progress_labels
        ) if self.progress_labels else False
        if all_done and self.progress_labels:
            self.result_label.setText("✅ Download Finished")
            self.result_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            QTimer.singleShot(300, self.process_queue)

    def start_download(self):
        if not self.download_folder:
            self.select_folder()
            if not self.download_folder:
                self.show_warning("⚠️ Cancelled", "No folder selected.")
                return

        raw_urls = [l.strip() for l in self.url_input.toPlainText().strip().splitlines() if l.strip()]
        urls = [sanitize_url(u) for u in raw_urls]
        if not urls:
            self.show_warning("⚠️ Empty", "Paste at least one URL.")
            return

        # Find URLs that need metadata
        urls_to_fetch = [url for url in urls if url not in self.metadata_cache]

        if urls_to_fetch:
            self.result_label.setText("⏳ Fetching metadata...")
            self.result_label.setFont(QFont("Play", 14))
            self.result_label.setStyleSheet(f"color: {ORANGE}; font-weight: bold;")
            self.fetching_count = len(urls_to_fetch)
            self.fetching_done = 0
            self.metadata_fetch_queue = queue.Queue()
            for url in urls_to_fetch:
                threading.Thread(target=self._fetch_metadata_bg, args=(url,), daemon=True).start()
            self._poll_metadata_fetch_queue(urls, urls_to_fetch)
        else:
            self._proceed_to_download(urls)

    def _fetch_metadata_bg(self, url):
        try:
            res = subprocess.run(
                [YTDLP_BIN, "--dump-json", "--skip-download", url],
                capture_output=True, text=True, timeout=40, check=True)
            meta = json.loads(res.stdout)
        except Exception:
            meta = {}
        self.metadata_fetch_queue.put((url, meta))

    def _poll_metadata_fetch_queue(self, all_urls, urls_to_fetch):
        while not self.metadata_fetch_queue.empty():
            url, meta = self.metadata_fetch_queue.get()
            self.metadata_cache[url] = meta
            self.fetching_done += 1

        if self.fetching_done < self.fetching_count:
            QTimer.singleShot(100, lambda: self._poll_metadata_fetch_queue(all_urls, urls_to_fetch))
        else:
            self.result_label.setText("✅ Metadata loaded. Starting downloads...")
            self._proceed_to_download(all_urls)

    def _proceed_to_download(self, urls):
        # Clear progress frame
        for i in reversed(range(self.progress_layout.count())):
            widget = self.progress_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.progress_labels.clear()

        # If formats not set (no preview), use default and fetch title from metadata_cache
        if not self.entry_widgets or all(fmt_box is None for _, fmt_box, *_ in self.entry_widgets):
            self.pool = ThreadPool(int(self.combo.currentText()))
            for idx, url in enumerate(urls):
                meta = self.metadata_cache.get(url, {})
                title = meta.get("title", "Unknown")
                label = QLabel(f'<span style="font-size:14px; font-weight: bold; font-family: Play;">🔄 Waiting:</span> '
                   f'<span style="font-size:14px; font-weight: bold; font-family: Play;">{url[:60]}</span>')
                self.progress_layout.addWidget(label)
                self.progress_labels.append(label)
                self.pool.add(lambda i=idx, u=url, t=title: self.download_worker(i, u, "MP4 - 1080p", t))
        else:
            # Use selection from preview
            self.pool = ThreadPool(int(self.combo.currentText()))
            for idx, (url, fmt_box, _, title) in enumerate(self.entry_widgets):
                fmt = fmt_box.currentText() if fmt_box else "MP4 - 1080p"
                label = QLabel(f'<span style="font-size:14px; font-weight: bold; font-family: Play;">🔄 Waiting:</span> '
                   f'<span style="font-size:14px; font-weight: bold; font-family: Play;">{url[:60]}</span>')
                self.progress_layout.addWidget(label)
                self.progress_labels.append(label)
                self.pool.add(lambda i=idx, u=url, f=fmt, t=title: self.download_worker(i, u, f, t))

        self.result_label.setText("🚀 Download started...")
        self.result_label.setStyleSheet("color: green; font-weight: bold;")
        QTimer.singleShot(300, self.process_queue)

    def show_warning(self, title, msg):
        QMessageBox.warning(self, title, msg)


# ---------- Dependency check (run early) ----------
def ensure_dependencies():
    # check yt-dlp
    if not shutil.which("yt-dlp"):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
        except Exception:
            show_dep_error("yt-dlp")

    # check ffmpeg binary exists
    if not shutil.which("ffmpeg"):
        show_dep_error("ffmpeg")


if __name__ == "__main__":
    ensure_dependencies()
    app = QApplication(sys.argv)
    app.setStyleSheet(modern_scrollbar_style)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())