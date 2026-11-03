# Scryptian [<scryptian.com>](https://github.com/adrianium/Scryptian)

## What is Scryptian

<h4>Scryptian is a tool for using file services without visiting their webpages or desktop apps.</h4>

<h4>Works with:</h4>

- Documents
- Video
- Audio
- Image
- Ebook

<picture><img width="640" alt="Demo" src="landing/product-demo-1920x1080.gif"></picture>

<p align="center">Select. Copy a file. Actions for this file type appear. Windows.</p>

<h4>Screenshot:</h4>

<picture><img width="640" alt="Screenshot" src="landing/pagey.png"></picture>

<a href="https://github.com/adrianium/Scryptian/releases/latest/download/ScryptianSetup.exe"><img src="docs/design/download-installer.svg" width="190" height="52" alt="Download for Windows"></a>


## Actions list

- Convertors (PDF to DOCX, MP4 to MP3 and etc.)
- Remove Background (Image/Video)
- Translate PDF with preserved layout (DeepL)
- Text to Speech (Male/Female)
- Audio to Text
- AI Upscale (Image/Video)

list will be bigger and bigger in future.

## Build

Windows 10/11, Python 3.10+.

```
python main.py
pyinstaller build.spec --noconfirm

```

The full installer is `installer.iss`. Details are in [BUILDING.md](BUILDING.md).

## License

[MIT](LICENSE)
