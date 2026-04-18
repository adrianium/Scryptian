# @title: snake_case
# @description: text → snake_case
# @author: Scryptian

import re


def run(text):
    """
    text: text from clipboard to convert
    """
    # Split camelCase/PascalCase boundaries, then spaces/dashes/underscores
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', text.strip())
    words = re.split(r'[\s_\-]+', s)
    return '_'.join(w.lower() for w in words if w)
