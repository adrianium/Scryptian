# nespatch

## What is nespatch

<h3>nespatch is a tool for using file services (like convertors) without visiting their webpages or desktop apps.</h3>

<h3>Works with:<br>
• Documents<br>
• Video<br>
• Audio<br>
• Image<br>
• Ebook</h3>

<picture><img width="100%" alt="Demo" src="landing/product-demo-1920x1080.gif"></picture>

<h3 align="center">Select. Copy a file. Actions for this file type appear. Windows.</h3>

<h3>Screenshot:</h3>

<picture><img width="100%" alt="Screenshot" src="landing/pagey.png"></picture>

<a href="https://github.com/adrianium/nespatch/releases/latest/download/nespatch_Setup.exe"><img src="docs/design/download-installer.svg" width="50%" alt="Download for Windows"></a><a href="https://www.virustotal.com/gui/file/1d929007958b311a34aa3b68705d831f21fa3af5a095f6026cdd33faaed81c0f?nocache=1"><img src="docs/design/virustotal.svg" width="50%" alt="Check on VirusTotal"></a>


## Actions list

<h3>• Convertors (PDF to DOCX, MP4 to MP3 and etc.)<br>
• Remove Background (Image/Video)<br>
• Translate PDF with preserved layout (DeepL)<br>
• Text to Speech (Male/Female)<br>
• Audio to Text<br>
• AI Upscale (Image/Video)</h3>

<h3>list will be bigger and bigger in future.</h3>

## Build

<h3>Windows 10/11, Python 3.10+.</h3>

```
python main.py
pyinstaller packaging/build.spec --noconfirm

```

<h3>The full installer is <code>packaging/installer.iss</code>. Details are in <a href="BUILDING.md">BUILDING.md</a>.</h3>

## License

<h3><a href="LICENSE">MIT</a></h3>
