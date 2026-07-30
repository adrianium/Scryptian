# core/runner.py — Unified skill execution engine with Unix-style pipelines.
#
# Every skill invocation flows through here. The runner:
#   1. Looks up the skill in the registry
#   2. Ensures the LLM is ready (if needed)
#   3. Dispatches to prompt / run_stream / run
#   4. Checks for pipeline.json in the skill's directory — if present,
#      chains the declared steps (output of each → input of next)
#   5. Repeats until a terminal result (no pipeline) is reached
#
# Skills never call each other. A skill author declares a pipeline.json
# next to manifest.json: [{"skill_id": "..."}, {"skill_id": "..."}]
# The runner reads it and connects the chain — like Unix pipes.

import json
import os
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


def _read_pipeline(skill):
    """Read pipeline.json from the skill's directory. Return list of steps or None."""
    skill_dir = skill.get("_dir")
    if not skill_dir:
        return None
    pipeline_path = os.path.join(skill_dir, "pipeline.json")
    try:
        if os.path.exists(pipeline_path):
            with open(pipeline_path, "r", encoding="utf-8") as f:
                steps = json.load(f)
            if isinstance(steps, list) and len(steps) > 0:
                return steps
    except Exception:
        pass
    return None


def _run_single(skill, input_text, settings=None):
    """Run one skill. Returns result string."""
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


def run_skill(skill, input_text, settings=None):
    """Execute a skill, then follow its pipeline.json chain.

    If the skill's directory contains pipeline.json (a list of
    {"skill_id": "..."} steps), the runner executes each step in
    order, feeding the output of one as the input of the next.
    Any step can have its own pipeline.json for nested chains.
    """
    current_skill = skill
    current_text = input_text
    current_settings = settings
    visited = set()

    while True:
        sid = current_skill.get("id") or current_skill.get("filename", "")
        if sid in visited:
            return "[Scryptian Error] Pipeline loop detected."
        visited.add(sid)

        result = _run_single(current_skill, current_text, current_settings)
        if isinstance(result, str) and result.startswith("[Scryptian Error]"):
            return result
        if result == "Skill returned an empty result.":
            return result

        steps = _read_pipeline(current_skill)
        if not steps:
            return result

        skills = scan_skills()
        for step in steps:
            step_id = step.get("skill_id", "")
            next_skill = find_skill(skills, step_id)
            if not next_skill:
                return f"[Scryptian Error] Pipeline skill not found: {step_id}"

            step_sid = next_skill.get("id") or next_skill.get("filename", "")
            if step_sid in visited:
                return "[Scryptian Error] Pipeline loop detected."
            visited.add(step_sid)

            result = _run_single(next_skill, result, step.get("settings"))
            if isinstance(result, str) and result.startswith("[Scryptian Error]"):
                return result
            if result == "Skill returned an empty result.":
                return result

            sub_steps = _read_pipeline(next_skill)
            if sub_steps:
                for sub_step in sub_steps:
                    sub_id = sub_step.get("skill_id", "")
                    sub_skill = find_skill(skills, sub_id)
                    if not sub_skill:
                        return f"[Scryptian Error] Pipeline skill not found: {sub_id}"
                    sub_sid = sub_skill.get("id") or sub_skill.get("filename", "")
                    if sub_sid in visited:
                        return "[Scryptian Error] Pipeline loop detected."
                    visited.add(sub_sid)
                    result = _run_single(sub_skill, result, sub_step.get("settings"))
                    if isinstance(result, str) and result.startswith("[Scryptian Error]"):
                        return result
                    if result == "Skill returned an empty result.":
                        return result

        return result


def run_skill_stream(skill, input_text, settings=None):
    """Execute a skill and yield result chunks (for streaming UI).

    Pipeline chaining is not supported in streaming mode — if a
    streaming skill writes pipeline.json it is ignored.
    """
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


