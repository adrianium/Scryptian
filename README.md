Scryptian

Writing tools for Windows. Inline AI text editing — offline, private, free.

https://adrianium.github.io/Scryptian/ (tool WebPage)

<video src="https://github.com/user-attachments/assets/0c794465-b705-4983-9c2b-291fdc372977" autoplay loop muted playsinline></video>

How it works

1. Press `Ctrl+Alt` — command bar appears
2. Pick a skill (or type to filter)
3. Press `Enter` — text from clipboard is processed by a local AI model
4. Result appears — press `Enter` again to copy and close

Skills

- Translate to my language
- Translate to English
- Summarize
- Improve writing
- Fix spelling and grammar
- Change tone to friendly
- Change tone to professional
- Explain this in simple terms
- Humanize

Add your own: one `.py` file in `skills/` = one skill.

```python
# @title: My Skill
# @description: What it does
# @author: YourName

import bridge

def run(text):
    prompt = f"Your prompt here:\n\n{text}"
    return bridge.generate(prompt)
```

Setup

Download `Scryptian.exe` from [Releases](https://github.com/adrianium/Scryptian/releases) and run. Model downloads automatically on first use (~2 GB, one time).

Hotkey

Default: `Ctrl+Alt`. Change in `config.py`:

```python
HOTKEY = "ctrl+alt"
```

License

MIT





