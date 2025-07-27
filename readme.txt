🎥 Video Downloader - User Manual 🚀
====================================

🌟 Overview
-----------
Video Downloader is a slick Python-based GUI app that lets you grab videos and audio from platforms like YouTube, Vimeo, TikTok, Instagram, Twitter/X, Reddit, SoundCloud, Dailymotion, and Facebook! 🎬 It uses yt-dlp and ffmpeg to power downloads and supports multiple formats (MP4 at 2160p, 1080p, 720p, or MP3). 🖱️

🔥 Features
-----------
- 📥 Download videos in MP4 (2160p, 1080p, 720p) or audio in MP3.
- 📃 Supports playlists and single videos.
- 📜 Auto-downloads subtitles for MP4 videos.
- ⚡ Concurrent downloads with adjustable thread limits (1-5).
- ℹ️ Preview video metadata (title, duration, size) before downloading.
- 🖼️ Sleek, user-friendly GUI built with Tkinter.

🛠️ Requirements
---------------
- 🐍 Python 3.9 or higher
- 📦 yt-dlp (auto-installed via winget or pip)
- 🎞️ ffmpeg (auto-installed via winget or pip)
- 💻 Windows OS (for winget support)
- 🌐 Internet connection for downloading

🔧 Installation
---------------
1. Make sure Python is installed. Get it from https://www.python.org/downloads/ if needed. 🐍
2. Save the script (e.g., `video_downloader.py`) to a folder. 📂
3. Open a terminal in the script’s directory. 💻
4. run_video_downloader.bat' or run_video_downloader_modern.bat'  🚀
5. The app will auto-install yt-dlp and ffmpeg:
   - Tries winget first. 📦
   - Falls back to pip if needed. 🛠️
   - If both fail, you’ll get a prompt to install manually:
     - yt-dlp: `pip install yt-dlp` 📥
     - ffmpeg: Download from https://ffmpeg.org/download.html and add to PATH. 🎥
6. Once dependencies are set, the GUI launches! 🎉

📋 Usage
--------
1. **Launch the App** 🌟
   - Run 'run_video_downloader.bat' or run_video_downloader_modern.bat'
   - A folder picker will pop up. Choose where to save downloads. 📁 If you cancel, the app exits. 😢

2. **GUI Breakdown** 🖥️
   - **URL Input**: Paste video/playlist URLs (one per line). 📝
   - **➕ Set Format Options**: Shows metadata and lets you pick formats (MP4 - 2160p, 1080p, 720p, or MP3). 🎚️
   - **🚀 Start Download**: Kicks off downloads for entered URLs. ⚡
   - **🔄 Reset**: Clears URLs, metadata, and progress displays. 🧹
   - **🔁 Max Concurrent Downloads**: Choose 1-5 simultaneous downloads (default: 2). 🔢
   - **📄 Video Info & Format Selection**: Displays metadata and format options after clicking "Set Format Options". ℹ️
   - **📥 Download Progress**: Tracks download status in real-time. 📊

3. **Downloading Videos or Audio** 🎥🎵
   - Paste URLs (e.g., YouTube video or playlist links) in the text box. 📎
   - Click **Set Format Options** to see metadata and choose formats:
     - 🎥 MP4 - 2160p: Ultra HD video (up to 4K).
     - 🎬 MP4 - 1080p: Full HD video (default).
     - 📺 MP4 - 720p: Standard HD video.
     - 🎵 MP3 - best: Audio-only, saved as MP3.
   - Or skip format selection and hit **Start Download** for default (MP4 - 1080p). 🚀
   - Watch progress in the "Download Progress" section:
     - 🔄 Waiting: Download is queued.
     - ⬇️ Downloading: In progress, with platform name.
     - ✔️ Done: Download completed! 🎉
     - ❌ Download error: Something went wrong (check URL or network). 😕
   - Subtitles (.srt) are auto-downloaded for MP4 formats if available. 📜 MP3 downloads skip subtitles.

4. **Resetting the App** 🔄
   - Hit **Reset** to clear URLs, metadata, and progress. 🧼
   - Enter new URLs and select formats as needed. Reset ensures old formats (e.g., MP3) don’t linger. ✅

5. **Concurrent Downloads** ⚡
   - Use the "Max Concurrent Downloads" dropdown to set 1-5 simultaneous downloads. 🔢
   - More threads = faster for multiple files, but may stress your network or system. 🌐

🛠️ Troubleshooting
------------------
- **Dependency Errors** 🚫
  - If yt-dlp or ffmpeg fails to install, a prompt will guide you:
    - yt-dlp: `pip install yt-dlp`
    - ffmpeg: Download from https://ffmpeg.org/download.html and add to PATH.
- **Download Errors** 😕
  - Verify URLs are valid and from supported platforms.
  - Check your internet connection. 🌐
  - Private content (e.g., Instagram) may require login, which isn’t supported.
- **Metadata Fetch Fails** ⚠️
  - If fetching takes too long, click "Cancel" and retry with fewer URLs. 🔄
- **Wrong Format Downloaded** ❓
  - Click "Set Format Options" and select your format before downloading.
  - After resetting, reselect formats to avoid defaulting to MP4 - 1080p.

🌍 Supported Platforms
---------------------
- 🎥 YouTube (youtube.com, youtu.be)
- 📹 Vimeo (vimeo.com)
- 🎶 TikTok (tiktok.com)
- 📸 Instagram (instagram.com)
- 🐦 Twitter/X (twitter.com, x.com)
- 📰 Reddit (reddit.com)
- 🎧 SoundCloud (soundcloud.com)
- 📺 Dailymotion (dailymotion.com)
- 📘 Facebook (facebook.com)
- 🌐 Other platforms supported by yt-dlp (check compatibility)

📝 Notes
--------
- The app stays responsive during downloads thanks to threading. 🧵
- Downloads save to your chosen folder. Playlists go into a subfolder named after the playlist. 📂
- Metadata fetching has a 1-second delay. Slow networks may need tweaks (ask the developer). ⏳
- Subtitles are embedded in MP4 files and saved as .srt files when available. 📜

📜 License
----------
Free and open-source, provided as-is. Built on yt-dlp and ffmpeg, which have their own licenses. 🆓

📧 Contact
----------
Got issues or ideas? Reach out to the developer or check the project repository (if available). ✉️