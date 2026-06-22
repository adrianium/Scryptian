# @title: Fix spelling and grammar
# @description: Correct spelling, grammar, and punctuation errors
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Fix all spelling, grammar, and punctuation errors in the following text. "
        "Do not change the meaning or style. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the corrected text:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to fix spelling and grammar
    """
    return bridge.generate(prompt(text))
