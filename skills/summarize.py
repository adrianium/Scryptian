# @title: Summarize
# @description: Summarize text in a few sentences
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Summarize the following text concisely in 2-4 sentences. "
        "Keep the key points, skip the fluff. Output ONLY the summary:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to summarize
    """
    return bridge.generate(prompt(text))
