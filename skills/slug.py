# @title: Slugify
# @description: text → url-slug
# @author: Scryptian

import re


def run(text):
    """
    text: text from clipboard to slugify
    """
    s = text.strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)  # remove special chars
    s = re.sub(r'[\s_]+', '-', s)    # spaces/underscores to dashes
    s = re.sub(r'-+', '-', s)         # collapse multiple dashes
    return s.strip('-')
