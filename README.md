# Scryptian [<scryptian.com>](https://github.com/adrianium/Scryptian)

Copy a file and theres appears actions bar. Windows.

## Demo

<img width="640" height="360" alt="Demo" src="https://github.com/user-attachments/assets/07a592a1-c185-4657-afd5-4458ea769cda" />

## Install

<a href="https://github.com/adrianium/Scryptian/releases/latest/download/ScryptianSetup.exe"><img src="docs/design/download-installer.svg" width="190" height="52" alt="Download for Windows"></a>

## Build

Windows 10/11, Python 3.10+.

```
python main.py
pyinstaller build.spec --noconfirm
pyinstaller stub.spec --noconfirm
```

The full installer is `installer.iss`. Details are in [BUILDING.md](BUILDING.md).

## License

[MIT](LICENSE)
