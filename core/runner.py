# core/runner.py — Unified skill execution engine.
#
# Every skill invocation flows through here. The runner:
#   1. Looks up the skill in the registry
#   2. Ensures the LLM is ready (if needed)
#   3. Dispatches to prompt / run_stream / run
#   4. Collects and returns the result
#
# Skills can call other skills via bridge.call_skill(name, text).
# The runner injects this function into bridge at import time.

import re
import bridge
from config import MAX_SKILL_INPUT_CHARS

from .registry import scan_skills, find_skill


def _check_input_limit(skill, input_text):
    if skill.get("background", False) or not skill.get("needs_llm", True):
        return None
    n = len(input_text or "")
    if n <= MAX_SKILL_INPUT_CHARS:
        return None
    return (
        "Text too long.\n"
        f"Limit: {MAX_SKILL_INPUT_CHARS} characters.   Your text: {n}.\n"
        "Please select less text and try again."
    )


def call_skill(name, text, settings=None):
    """Call another skill by id or filename. Usable from inside any skill."""
    skills = scan_skills()
    skill = find_skill(skills, name)
    if not skill:
        return f"[Scryptian Error] Skill not found: {name}"
    return run_skill(skill, text, settings)


def run_skill(skill, input_text, settings=None):
    """Execute a skill and return the full result string.

    skill: skill dict from registry
    input_text: str
    settings: optional dict of skill settings
    """
    limit_msg = _check_input_limit(skill, input_text)
    if limit_msg:
        return limit_msg

    if skill.get("needs_llm", True) and not bridge.is_model_in_memory():
        bridge._get_llm()

    mod = skill["module"]
    try:
        if hasattr(mod, "prompt"):
            full_text = ""
            for chunk in bridge.generate_stream(mod.prompt(input_text)):
                full_text += chunk
            result = re.sub(r"<think>[\s\S]*?</think>", "", full_text).strip()
        elif hasattr(mod, "run_stream"):
            full_text = ""
            for chunk in mod.run_stream(input_text):
                full_text += chunk
            result = full_text.strip()
        else:
            result = mod.run(input_text)

        if not result:
            return "Skill returned an empty result."
        return result
    except Exception as e:
        return f"[Scryptian Error] {e}"


def run_skill_stream(skill, input_text, settings=None):
    """Execute a skill and yield result chunks (for streaming UI)."""
    limit_msg = _check_input_limit(skill, input_text)
    if limit_msg:
        yield limit_msg
        return

    if skill.get("needs_llm", True) and not bridge.is_model_in_memory():
        bridge._get_llm()

    mod = skill["module"]
    try:
        if hasattr(mod, "prompt"):
            full_text = ""
            for chunk in bridge.generate_stream(mod.prompt(input_text)):
                full_text += chunk
                yield full_text
        elif hasattr(mod, "run_stream"):
            full_text = ""
            for chunk in mod.run_stream(input_text):
                full_text += chunk
                yield full_text
        else:
            result = mod.run(input_text)
            yield result or "Skill returned an empty result."
    except Exception as e:
        yield f"[Scryptian Error] {e}"


# Inject call_skill into bridge so skills can compose.
bridge.call_skill = call_skill
