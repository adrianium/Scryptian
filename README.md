Scryptian v0.1. (Proof of Concept)

Local AI-powered command bar for Windows & Linux. Like Raycast, but absolutely free because local llm.

![Scryptian Demo](https://github.com/user-attachments/assets/0b781294-9683-4f87-8f69-f98d76d7fa1b)


How it works?

1. Press `Ctrl+Alt` - command bar appears
2. Pick a skill from the list (or type to filter)
3. Press `Enter` - skill processes text from your clipboard via local LLM
4. Result appears below - press `Enter` again to copy and close

Stack

Python + tkinter (zero external UI deps)
Ollama (local LLM backend, default model: `qwen2.5:3b`)
Modular skill system — one file = one command

Setup

```bash
# 1. Install Ollama and pull the model
ollama pull qwen2.5:3b

#if already installed
ollama run qwen2.5:3b

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

Project structure

```
scryptian/
├── main.py            # Core: skill scanner, hotkey listener, UI
├── bridge.py          # Connector to Ollama (settings, generate())
├── config.py          # Central configuration
├── telemetry.py       # Lightweight anonymous analytics
├── requirements.txt
├── LICENSE
└── skills/
    ├── fix_code.py        # Fix syntax & logic errors in code
    ├── improve_text.py    # Rewrite text cleaner & more professional
    ├── json_format.py     # Fix & pretty-print broken JSON
    ├── camel.py           # text → camelCase
    ├── snake.py           # text → snake_case
    └── slug.py            # text → url-slug
```


Skill standard (Scryptian v0.1)

Every skill is a single `.py` file in `skills/` with:

```python
# @title: My Command
# @description: What it does.
# @author: YourName

import bridge

def run(text):
    prompt = f"Your prompt here:\n\n{text}"
    return bridge.generate(prompt)
```

Rules

One file = one command
Must have `run(text)` function — takes string, returns string
No UI access — skills are black boxes
Metadata (`@title`, `@description`, `@author`) shown in the command bar

Hotkey

Default: `Ctrl+Alt`. Change in `config.py`:

```python
HOTKEY = "ctrl+alt"
```

License

MIT





