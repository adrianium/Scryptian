# @title: camelCase
# @description: text → camelCase
# @author: Scryptian

import re


def run(text):
    """
    text: text from clipboard to convert
    """
    words = re.split(r'[\s_\-]+', text.strip())
    if not words:
        return text
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:])
