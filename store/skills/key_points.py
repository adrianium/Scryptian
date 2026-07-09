# @title: Extract key points
# @description: Pull out the main points from text as a short bullet list
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Extract the key points from the following text. "
        "Return a short bullet list (use '- ' for each point), "
        "one clear idea per line, no repetition, no intro or outro. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the bullet list:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to extract key points from
    """
    return bridge.generate(prompt(text))
