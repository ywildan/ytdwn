<div align="center">

# 🎬🎵 YTDWN — YouTube Downloader & Music Player

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.08%2B-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Textual](https://img.shields.io/badge/Textual-8.2%2B-007ACE?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2ZmZiI+PHBhdGggZD0iTTEyIDJMNCA3djEwbDggNSA4LTVMNCA3bDgtNXoiLz48L3N2Zz4=&logoColor=white)](https://github.com/Textualize/textual)
[![mpv](https://img.shields.io/badge/mpv-0.41%2B-607C8E?style=for-the-badge&logo=mpv&logoColor=white)](https://mpv.io)
[![Platform](https://img.shields.io/badge/Platform-Linux-1793D1?style=for-the-badge&logo=linux&logoColor=white)](https://archlinux.org)
[![License](https://img.shields.io/badge/License-MIT-2ecc71?style=for-the-badge)](LICENSE)

**A sleek terminal-based YouTube downloader with built-in music player.**

*Download single videos or full playlists, play your music — all without leaving your terminal.*

[Installation](#installation) • [Usage](#usage) • [Features](#features) • [Keyboard Shortcuts](#keyboard-shortcuts)

</div>

---

## ✨ Features

### 🎬 Downloader (`ytdwn`)

| | |
|---|---|
| 🎵 **Audio Extraction** | Download as MP3 with selectable bitrate (320/192/128/64 kbps) |
| 🎬 **Video Download** | MP4 format with quality options (Best/1080p/720p/480p) |
| 📋 **Playlist Support** | Auto-detects playlists and downloads all videos |
| 📊 **Live Progress** | Real-time progress bar and download log |
| 📁 **Smart Output** | Auto-organizes playlists into subfolders |
| ⌨️ **Keyboard Driven** | Full TUI navigation — no mouse required |
| 📋 **Clipboard Paste** | Paste URLs directly from clipboard |

### 🎵 Music Player (`ytdwn-music`)

| | |
|---|---|
| 📂 **Auto Scan** | Scans download folder for audio files automatically |
| 🔀 **Reorder** | Drag & drop or ▲▼ buttons to reorder playlist |
| ⏯️ **Playback** | Play, Pause, Stop, Next, Prev with progress bar |
| 🎵 **Background** | Uses mpv for lightweight background playback |

---

## 🚀 Installation

### Prerequisites

- **Python 3.10+**
- **yt-dlp** — for downloading YouTube content
- **mpv** — for music playback

```bash
# Arch Linux
sudo pacman -S yt-dlp mpv

# Other platforms
pip install yt-dlp
# Install mpv from https://mpv.io/installation/
```

### Setup

```bash
# Clone the repository
git clone https://github.com/ywildan/ytdwn.git
cd ytdwn

# Create virtual environment
python3 -m venv .venv
.venv/bin/pip install textual python-mpv

# Create global symlinks (optional)
ln -sf "$(pwd)/ytdwn" ~/.local/bin/ytdwn
ln -sf "$(pwd)/ytdwn-music" ~/.local/bin/ytdwn-music
```

---

## 🎮 Usage

### Downloader

```bash
ytdwn
```

**Workflow:**
1. Paste URL (or press `v` to paste from clipboard)
2. Auto-detects: single video or playlist (+ video count)
3. Choose type: Audio (MP3) or Video (MP4)
4. Select quality
5. Set output folder (default: `~/Downloads/youtube-dl/`)
6. Watch live progress and logs

### Music Player

```bash
ytdwn-music
```

**Workflow:**
1. Player auto-scans `~/Downloads/youtube-dl/` for audio files
2. Click any track to play
3. Use ▲▼ buttons or drag & drop to reorder
4. Control playback with keyboard or buttons

---

## ⌨️ Keyboard Shortcuts

### Downloader

| Key | Action |
|:---:|---|
| `d` | Start download |
| `h` | View download history |
| `v` | Paste from clipboard |
| `c` | Clear form |
| `r` | Refresh history |
| `q` | Quit |

### Music Player

| Key | Action |
|:---:|---|
| `Space` | Play/Pause |
| `n` | Next track |
| `p` | Previous track |
| `s` | Stop |
| `u` | Move track up |
| `d` | Move track down |
| `x` | Remove track |
| `r` | Rescan folder |
| `q` | Quit |

---

## 📁 Project Structure

```
ytdwn/
├── tui.py                 # Downloader TUI (Textual)
├── music_player.py        # Music Player TUI (Textual + mpv)
├── youtube_downloader.py  # CLI fallback (original)
├── ytdwn                  # Executable → Downloader TUI
├── ytdwn-music            # Executable → Music Player TUI
├── .venv/                 # Python virtual environment
└── README.md              # This file
```

---

## ⚙️ Configuration

| Setting | Default | Description |
|---|---|---|
| Output Directory | `~/Downloads/youtube-dl/` | Where downloaded files are saved |
| Audio Format | MP3 | Output format for audio downloads |
| Video Format | MP4 | Output format for video downloads |
| Audio Quality | 0 (Best) | 0=320kbps, 2=192kbps, 5=128kbps, 7=64kbps |

---

## 🛠️ Troubleshooting

| Issue | Solution |
|---|---|
| `yt-dlp not found` | Install yt-dlp: `sudo pacman -S yt-dlp` |
| `mpv not found` | Install mpv: `sudo pacman -S mpv` |
| `textual not found` | Run `.venv/bin/pip install textual` |
| Download fails | Update yt-dlp: `yt-dlp -U` |
| `ytdwn: command not found` | Ensure `~/.local/bin` is in your `$PATH` |

---

## 📝 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

Made with ❤️ and [Textual](https://github.com/Textualize/textual)

**[⬆ Back to Top](#ytdwn--youtube-downloader--music-player)**

</div>
