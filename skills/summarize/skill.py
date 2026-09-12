import json
import urllib.error
from urllib import request

_WORKER = "https://scryptian-llm.nurlannapo.workers.dev/v1/chat/completions"


def _ask(prompt):
    payload = json.dumps({
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Follow instructions precisely. Output only what is asked, nothing extra. Never ask questions back. This is not a chat."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0,
        "stream": False,
    }).encode("utf-8")
    req = request.Request(_WORKER, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Scryptian"}, method="POST")
    try:
        resp = request.urlopen(req, timeout=60)
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        return f"[Scryptian Error] {e}"
    except Exception as e:
        return f"[Scryptian Error] {e}"


def prompt(text):
    return (
        "CRITICAL RULE: You MUST respond in the EXACT SAME language as the input text. "
        "If the input is Russian, respond in Russian. If English, respond in English. "
        "Never switch languages.\n\n"
        "Task: Summarize the following text concisely in 2-4 sentences. "
        "Keep the key points, skip the fluff. "
        "Output ONLY the summary:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to summarize
    """
    return _ask(prompt(text))
