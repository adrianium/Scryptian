# @title: Fix Code
# @description: Fix syntax & logic errors in code
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Fix the following code. Provide only the corrected version, "
        "no explanations:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: code from clipboard, passed by main.py
    """
    return bridge.generate(prompt(text))
