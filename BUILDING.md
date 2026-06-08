# Building Scryptian from Source

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/) (tested with 3.12)
- [Git](https://git-scm.com/)
- Windows 10/11 x64
- [Visual Studio 2022](https://visualstudio.microsoft.com/) with **"Desktop development with C++"** workload (required to compile llama.cpp)

## 1. Clone the repository

```bash
git clone https://github.com/adrianium/Scryptian.git
cd Scryptian
```

## 2. Install Python dependencies

```bash
pip install pyinstaller pystray keyboard pyperclip certifi posthog
```

## 3. Install llama-cpp-python (compiles from source)

This step compiles the local AI inference engine. It takes 5–10 minutes.

```bash
pip install cmake ninja scikit-build-core
git clone --recursive https://github.com/abetlen/llama-cpp-python.git vendor/llama-cpp-python
pip install vendor/llama-cpp-python --no-cache-dir --no-build-isolation
```

## 4. Run in development mode

```bash
python main.py
```

The app will start in the system tray. Press `Ctrl+Alt` to open the panel.

## 5. Build the EXE

```bash
pyinstaller build.spec --noconfirm
```

Output: `dist/Scryptian.exe`

## 6. Build the installer (optional)

Install [Inno Setup 6](https://jrsoftware.org/isdl.php), then:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Output: `dist/Scryptian_Setup.exe`

## Notes

- The AI model (~1.9 GB) is downloaded automatically on first launch to `%LOCALAPPDATA%\Scryptian\models\`
- Skills are Python files in the `skills/` folder — you can add your own
- Hotkey can be changed in `config.py`
