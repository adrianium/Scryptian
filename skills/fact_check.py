# @title: Fact Check
# @description: Verify a claim using AI analysis
# @author: Scryptian

import bridge


def run(text):
    """
    Fact-check the given claim using the local AI model.
    Responds in ultra-short simple English — understandable even with basic English.
    """
    prompt = (
        "Fact-check this claim. Reply in VERY SHORT simple English (max 2 short sentences).\n"
        "Use basic words. Be direct. No fluff.\n\n"
        f"Claim: {text}\n\n"
        "Format:\n"
        "VERDICT: TRUE/FALSE/MISLEADING/UNVERIFIED\n"
        "WHY: one short sentence"
    )
    return bridge.generate(prompt)
