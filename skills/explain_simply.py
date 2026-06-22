# @title: Explain this in simple terms
# @description: Simplify complex text so anyone can understand
# @author: Scryptian

import bridge


def prompt(text):
    return (
        "Explain the text below as if you are talking to a 10-year-old child.\n\n"
        "Rules:\n"
        "- Use ONLY everyday words, no technical terms\n"
        "- Use analogies or comparisons to familiar things\n"
        "- Keep it short: 2-4 sentences max\n"
        "- Only reply with the explanation, nothing else\n"
        "- IMPORTANT: Respond in the SAME language as the input text\n\n"
        "Example:\n"
        "Text: Photosynthesis is the process by which plants convert light energy into chemical energy.\n"
        "Explanation: Plants eat sunlight. They take light and turn it into food so they can grow, "
        "kind of like how you eat lunch to get energy.\n\n"
        f"Text: {text}\n\n"
        "Explanation:"
    )


def run(text):
    """
    text: text from clipboard to explain simply
    """
    return bridge.generate(prompt(text))
