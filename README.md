# Video Downloader with yt-dlp

A modern, user-friendly GUI video downloader built with PyQt6.
Supports YouTube, Vimeo, TikTok, Instagram, Twitter/X, Reddit, SoundCloud, Dailymotion, and more via [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

## Features

- **Paste multiple URLs:** Download many videos at once.
- **Metadata preview:** See info and select download format before downloading.
- **Format selection:** Choose resolution and file type (MP4/MP3).
- **Concurrent downloads:** Choose up to 5 parallel downloads.
- **Progress display:** Real-time download progress with color feedback.
- **Supports playlists & subtitles** (where available).
- **Automatic dependency install:** Installs `yt-dlp` and `ffmpeg` if missing.

## Requirements

- Python 3.8+
- See [`requirements.txt`](./requirements.txt) for PyQt6 and other dependencies.
- `yt-dlp` and `ffmpeg` (auto-installed if missing).

## Installation

1. **Clone this repository or copy the files.**

2. **Install Python dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

3. **Run the application:**

   ```sh
   python video_downloader_pyqt6.py
   ```

   The app will attempt to install `yt-dlp` and `ffmpeg` automatically if not found.

## Usage

1. **Select Download Folder:** Click the folder button to choose where videos will be saved.
2. **Paste URLs:** Enter one or more video URLs (one per line).
3. **(Optional) Set Format:** Click "Set Format Option" to preview and select format for each video.
4. **Choose Concurrent Downloads:** Set how many downloads to run in parallel.
5. **Start Download:** Click "Start Download".
6. **Monitor Progress:** Watch the progress display for real-time updates and completion.

## Supported Sites

YouTube, Vimeo, TikTok, Instagram, Twitter/X, Reddit, SoundCloud, Dailymotion, and more!

## Notes

- On first run, the app will attempt to auto-install `yt-dlp` and `ffmpeg` using `pip` or `winget`.
- If auto-install fails, you may need to install these tools manually.
- Long progress lines are word-wrapped and will never overflow the window.

## License

MIT License. See [LICENSE](./LICENSE) if included.

## Credits

- Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for downloads.
- Built with [PyQt6](https://pypi.org/project/PyQt6/).
