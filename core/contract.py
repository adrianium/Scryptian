# core/contract.py — stdin/stdout JSON protocol for skill execution.
#
# Every skill receives input on stdin and writes output to stdout.
# This is the narrow waist: skills in any language can participate
# as long as they respect this contract.
#
# Input (stdin):
#   {"text": "<input text>", "settings": {...}, "caller": "<skill_id or null>"}
#
# Output (stdout):
#   {"result": "<output text>", "error": null}
#   {"result": null, "error": "<error message>"}

import json
import sys


def encode_input(text, settings=None, caller=None):
    return json.dumps({
        "text": text or "",
        "settings": settings or {},
        "caller": caller,
    }, ensure_ascii=False)


def decode_input(raw):
    try:
        data = json.loads(raw)
        return (
            data.get("text", ""),
            data.get("settings", {}),
            data.get("caller"),
        )
    except Exception:
        return (raw or "", {}, None)


def encode_output(result=None, error=None):
    return json.dumps({
        "result": result,
        "error": error,
    }, ensure_ascii=False)


def decode_output(raw):
    try:
        data = json.loads(raw)
        return (data.get("result"), data.get("error"))
    except Exception:
        return (raw, None)


def read_input():
    raw = sys.stdin.read()
    return decode_input(raw)


def write_output(result=None, error=None):
    sys.stdout.write(encode_output(result=result, error=error))
    sys.stdout.flush()
