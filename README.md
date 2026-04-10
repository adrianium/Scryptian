Scryptian v0.1. (Proof of Concept)

Local AI-powered command bar for Windows & Linux. Like Raycast, but absolutely free because local llm.

How it works?

1. Press `Ctrl+Alt` - command bar appears
2. Pick a plugin from the list (or type to filter)
3. Press `Enter` - plugin processes text from your clipboard via local LLM
4. Result appears below - press `Enter` again to copy and close

Stack

Python + tkinter (zero external UI deps)
Ollama (local LLM backend, default model: `qwen2.5:3b`)
Modular plugin system — one file = one command

Setup

```bash
# 1. Install Ollama and pull the model
ollama pull qwen2.5:3b

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

Project structure

```
scryptian/
├── main.py            # Core: plugin scanner, hotkey listener, UI
├── bridge.py          # Connector to Ollama (settings, generate())
├── requirements.txt
└── scripts/
    ├── fix_code.py        # Fix code errors
    ├── explain_log.py     # Explain logs/errors
    └── improve_text.py    # Make text more professional
```


Plugin standard (Scryptian v0.1)

Every plugin is a single `.py` file in `scripts/` with:

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
No UI access — plugins are black boxes
Metadata (`@title`, `@description`, `@author`) shown in the command bar

Hotkey

Default: `Ctrl+Alt`. Change in `main.py`:

```python
HOTKEY = "ctrl+alt"
```

License

MIT





