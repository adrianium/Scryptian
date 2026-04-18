# @title: JSON Format
# @description: Fix & pretty-print broken JSON
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Fix and format this JSON. Close any open brackets, add missing quotes, "
        "and fix values. Output ONLY valid, pretty-printed JSON, nothing else:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: raw/broken JSON from clipboard
    """
    return bridge.generate(prompt(text))
