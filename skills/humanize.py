# @title: Humanize
# @description: Make AI-generated text sound natural and human
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Rewrite the following text so it sounds like a real person wrote it, not an AI. "
        "Use natural speech patterns, varied sentence length, casual connectors, and subtle imperfections. "
        "Remove robotic phrasing, generic filler, and overly structured formatting. "
        "Keep the original meaning. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the rewritten text:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: AI-generated text from clipboard to humanize
    """
    return bridge.generate(prompt(text))
