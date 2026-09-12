# Building Scryptian from Source

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/) (tested with 3.12)
- [Git](https://git-scm.com/)
- Windows 10/11 x64

## 1. Clone the repository

```bash
git clone https://github.com/adrianium/Scryptian.git
cd Scryptian
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
pyinstaller build.spec --noconfirm
```

Output: `dist/Scryptian.exe`

## 5. Build the installer (optional)

Install [Inno Setup 6](https://jrsoftware.org/isdl.php), then:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Output: `dist/Scryptian_Setup.exe`

## Notes

- The LLM runs in the cloud (OpenRouter via a Cloudflare Worker) — no local model download needed
- Skills are Python files in the `skills/` folder — you can add your own
- Hotkey can be changed in `config.py`
