# @title: Change tone to professional
# @description: Rewrite text in a professional, formal tone
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Rewrite the following text in a professional, formal, and polished tone. "
        "Keep the original meaning and length. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the rewritten text:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to rewrite in a professional tone
    """
    return bridge.generate(prompt(text))
