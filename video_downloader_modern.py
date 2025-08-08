import itertools, threading, queue, sys, shutil, os, subprocess, json
from urllib.parse import urlparse
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QTextEdit, QScrollArea, QComboBox, QHBoxLayout, QMessageBox, QFrame, QFileDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

DARK_BLUE = "#004080"
ORANGE = "#FF5F15"
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
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("❌ Dependency Error")
    msg.setText(f"🚫 {pkg} could not be installed.\nPlease install it manually.")
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

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Downloader")
        self.setGeometry(250, 100, 1000, 700)
        self.setFixedSize(1000, 700)
        self.download_folder = ""
        self.metadata_cache = {}
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

        # Description label
        label = QLabel("Paste one/multiple URLs per line!")
        label.setFont(QFont("Play", 16))
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        label.setStyleSheet(f"color: {DARK_BLUE}; padding: 10px; font-weight: bold;")
        label.setFixedHeight(50)

        # TextEdit for URLs
        self.url_input = QTextEdit()
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

        label_concurrent = QLabel("Max Concurrent Downloads:")
        label_concurrent.setAlignment(Qt.AlignmentFlag.AlignLeft)
        label_concurrent.setFont(QFont("Play", 16))
        label_concurrent.setStyleSheet(f"color: {DARK_BLUE}; padding: 10px; font-weight: bold;")
        label_concurrent.setFixedHeight(50)

        self.combo = QComboBox()
        self.combo.addItems([str(i) for i in range(1, 6)])
        self.combo.setCurrentIndex(2)
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

        # Preview & Progress Frames
        self.preview_frame = QFrame()
        self.preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_frame.setMinimumHeight(120)

        self.download_progress_label = QLabel("📥 Download Progress")
        self.download_progress_label.setFont(QFont("Play", 14))
        self.download_progress_label.setStyleSheet(f"color: {DARK_BLUE}; font-weight: bold;")

        self.progress_frame = QFrame()
        self.progress_layout = QVBoxLayout(self.progress_frame)
        self.progress_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.progress_frame.setMinimumHeight(120)

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
        scroll_layout.addWidget(self.preview_frame)
        scroll_layout.addWidget(self.download_progress_label, alignment=Qt.AlignmentFlag.AlignLeft)
        scroll_layout.addWidget(self.progress_frame)
        scroll_layout.addStretch(1)
        main_layout.addWidget(scroll_area)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", os.path.expanduser("~"))
        if folder:
            self.download_folder = folder
            self.download_label.setText(folder)
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
        self.metadata_links = [l.strip() for l in self.url_input.toPlainText().strip().splitlines() if l.strip()]
        self.metadata_links_count = len(self.metadata_links)
        self.metadata_custom = custom
        if not self.metadata_links:
            self.show_warning("⚠️ No Input", "Paste at least one URL.")
            return

        # Add loading spinner and cancel button
        spinner_label = QLabel("⏳ Fetching metadata...")
        spinner_label.setFont(QFont("Play", 14))
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
                    ["yt-dlp", "--dump-json", "--skip-download", url],
                    capture_output=True, text=True, timeout=30, check=True)
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
        self.entry_widgets.append((url, combo, lbl))

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

    def download_worker(self, idx, url, fmt):
        try:
            platform = detect_platform(url)
            is_playlist = "playlist" in url.lower()
            output = os.path.join(self.download_folder or ".", "%(playlist_title)s" if is_playlist else "", "%(title)s.%(ext)s")
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

            self.queue_out.put(("status", idx, url, f'<span style="color: {DARK_BLUE}; font-size: 16px; font-family: Play; font-weight: bold;">⬇️ Downloading from {platform}...</span>'))
            proc = subprocess.Popen(cmd + [url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                styled_line = f'<span style="color: {ORANGE}; font-size: 16px; font-family: Play; font-weight: bold;">⏳ {line.strip()}</span>'
                self.queue_out.put(("progress", idx, url, styled_line))
            if proc.wait() == 0:
                self.queue_out.put(("success", idx, url, '<span style="color: green; font-size: 16px; font-family: Play; font-weight: bold;">✅ Done</span>'))
            else:
                self.queue_out.put(("fail", idx, url, '<span style="color: red; font-size: 16px; font-family: Play; font-weight: bold;">❌ Download error</span>'))
        except Exception as e:
            self.queue_out.put(("fail", idx, url, f"❌ {str(e)}"))

    def process_queue(self):
        try:
            while True:
                msg_type, idx, url, msg = self.queue_out.get_nowait()
                if idx is not None and idx < len(self.progress_labels):
                    display = msg[:150] + ('...' if len(msg) > 150 else '')
                    self.progress_labels[idx].setText(display)
        except queue.Empty:
            pass
        QTimer.singleShot(300, self.process_queue)

    def start_download(self):
        if not self.download_folder:
            self.select_folder()
            if not self.download_folder:
                self.show_warning("⚠️ Cancelled", "No folder selected.")
                return

        urls = [l.strip() for l in self.url_input.toPlainText().strip().splitlines() if l.strip()]
        if not urls:
            self.show_warning("⚠️ Empty", "Paste at least one URL.")
            return

        # Clear progress frame
        for i in reversed(range(self.progress_layout.count())):
            widget = self.progress_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.progress_labels.clear()

        # If formats not set (no preview), use default
        if not self.entry_widgets or all(fmt_box is None for _, fmt_box, _ in self.entry_widgets):
            self.pool = ThreadPool(int(self.combo.currentText()))
            for idx, url in enumerate(urls):
                label = QLabel(f"🔄 Waiting: {url[:60]}")
                self.progress_layout.addWidget(label)
                self.progress_labels.append(label)
                self.pool.add(lambda i=idx, u=url: self.download_worker(i, u, "MP4 - 1080p"))
        else:
            # Use selection from preview
            self.pool = ThreadPool(int(self.combo.currentText()))
            for idx, (url, fmt_box, _) in enumerate(self.entry_widgets):
                fmt = fmt_box.currentText() if fmt_box else "MP4 - 1080p"
                label = QLabel(f"🔄 Waiting: {url[:60]}")
                self.progress_layout.addWidget(label)
                self.progress_labels.append(label)
                self.pool.add(lambda i=idx, u=url, f=fmt: self.download_worker(i, u, f))

        self.result_label.setText("🚀 Download started...")
        QTimer.singleShot(300, self.process_queue)

    def show_warning(self, title, msg):
        QMessageBox.warning(self, title, msg)

if __name__ == "__main__":
    ensure_dependencies()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())