# Building nespatch from Source

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/) (tested with 3.12)
- [Git](https://git-scm.com/)
- Windows 10/11 x64

## 1. Clone the repository

```bash
git clone https://github.com/adrianium/nespatch.git
cd nespatch
```

## 2. Install Python dependencies

```bash
pip install pyinstaller pystray keyboard pyperclip certifi posthog
```

## 3. Run in development mode

```bash
python main.py
```

The app will start in the system tray. Press `Ctrl+Alt` to open the panel.

## 4. Build the EXE

```bash
pyinstaller packaging/build.spec --noconfirm
```

Output: `dist/nespatch.exe`

## 5. Build the installer (optional)

Install [Inno Setup 6](https://jrsoftware.org/isdl.php), then:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging/installer.iss
```

Output: `dist/nespatch_Setup.exe`

This full installer is what auto-update downloads. Do not rename it.

## 6. Build the Chrome-style stub (website download)

```bash
pyinstaller packaging/stub.spec --noconfirm
```

Output: `dist/nespatchSetup.exe`

This is the small file the website should offer. It shows a download window, silently runs `nespatch_Setup.exe`, then launches the real app. Upload **both** assets to the GitHub release:

- `nespatchSetup.exe` — website / first-time download
- `nespatch_Setup.exe` — auto-update (name must stay exact)

## Notes

- The LLM runs in the cloud (OpenRouter via a Cloudflare Worker) — no local model download needed
- Skills are Python files in the `skills/` folder — you can add your own
- Hotkey can be changed in `app/config.py`
