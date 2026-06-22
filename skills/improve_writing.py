# @title: Improve writing
# @description: Polish text to sound clearer and more confident
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Improve the following text to make it clearer, more concise, and confident. "
        "Fix awkward phrasing and remove redundancy. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the improved text:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to improve
    """
    return bridge.generate(prompt(text))
