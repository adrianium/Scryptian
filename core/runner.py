# core/runner.py — Unified skill execution engine with Unix-style pipelines.
#
# Every skill invocation flows through here. The runner:
#   1. Looks up the skill in the registry
#   2. Dispatches to run
#   3. Checks for pipeline.json in the skill's directory — if present,
#      chains the declared steps (output of each → input of next)
#   4. Repeats until a terminal result (no pipeline) is reached
#
# Skills never call each other. A skill author declares a pipeline.json
# next to manifest.json: [{"skill_id": "..."}, {"skill_id": "..."}]
# The runner reads it and connects the chain — like Unix pipes.

import json
import os

from .registry import scan_skills, find_skill


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
    mod = skill["module"]
    try:
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


