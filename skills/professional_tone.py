# @title: Change tone to professional
# @description: Rewrite text in a professional, formal tone
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "CRITICAL RULE: You MUST respond in the EXACT SAME language as the input text. "
        "If the input is Russian, respond in Russian. If English, respond in English. "
        "Never switch languages.\n\n"
        "Task: Rewrite the following text in a professional, formal, and polished tone. "
        "Keep the original meaning and length. "
        "Output ONLY the rewritten text:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to rewrite in a professional tone
    """
    return bridge.generate(prompt(text))
