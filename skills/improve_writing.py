# @title: Improve writing
# @description: Polish text to sound clearer and more confident
# @author: Scryptian

import threading
import bridge

_SKILL_ID = "improve_writing"


def _analyze(text: str) -> dict:
    """Deterministic rule-based tone and topic detection."""
    t = text.lower()

    formal_signals = ["dear ", "i am writing", "please be advised", "regarding",
                      "sincerely", "kind regards", "i would like", "hereby",
                      "attached", "pursuant", "on behalf"]
    casual_signals = ["hey", "yo ", "lol", "idk", "btw", "gonna", "wanna",
                      "tbh", "ngl", "omg", "asap", "thx", "ok so"]
    technical_signals = ["bug", "deploy", "database", "code", "server", "api",
                         "error", "function", "script", "commit", "repo"]

    formal_score = sum(1 for s in formal_signals if s in t)
    casual_score = sum(1 for s in casual_signals if s in t)
    technical_score = sum(1 for s in technical_signals if s in t)

    if technical_score >= 2:
        tone = "technical"
    elif formal_score > casual_score:
        tone = "formal"
    elif casual_score > 0:
        tone = "casual"
    else:
        tone = "formal"

    complaint_signals = ["disappointed", "unacceptable", "refund", "complaint",
                         "terrible", "awful", "disgusted", "demand", "immediately"]
    business_signals = ["deadline", "project", "client", "team", "meeting",
                        "report", "delivery", "milestone", "stakeholder"]
    email_signals = ["dear ", "regards", "i am writing", "subject", "attached"]
    chat_signals = ["yo ", "hey ", "bro", "lol", "idk", "tbh", "ngl", "omg",
                    "gonna", "wanna", "can u", "help me", "btw", "ok so"]
    legal_signals = ["agreement", "contract", "clause", "hereby", "pursuant",
                     "whereas", "liability", "indemnify", "jurisdiction", "party"]
    medical_signals = ["patient", "diagnosis", "symptoms", "treatment", "doctor",
                       "medication", "clinical", "prescription", "hospital", "surgery"]
    marketing_signals = ["brand", "campaign", "audience", "conversion", "engagement",
                         "launch", "promotion", "revenue", "growth", "strategy"]
    academic_signals = ["research", "hypothesis", "methodology", "findings", "study",
                        "abstract", "literature", "citation", "analysis", "conclude"]

    if sum(1 for s in complaint_signals if s in t) >= 1:
        topic = "complaint"
    elif sum(1 for s in legal_signals if s in t) >= 2:
        topic = "legal"
    elif sum(1 for s in medical_signals if s in t) >= 2:
        topic = "medical"
    elif sum(1 for s in academic_signals if s in t) >= 2:
        topic = "academic"
    elif sum(1 for s in marketing_signals if s in t) >= 2:
        topic = "marketing"
    elif sum(1 for s in technical_signals if s in t) >= 2:
        topic = "report"
    elif sum(1 for s in business_signals if s in t) >= 1:
        topic = "business"
    elif sum(1 for s in email_signals if s in t) >= 1:
        topic = "email"
    elif sum(1 for s in chat_signals if s in t) >= 1:
        topic = "chat"
    else:
        topic = "other"

    return {"tone": tone, "topic": topic}


def run(text):
    """
    text: text from clipboard to improve
    """
    state = bridge.get_state(_SKILL_ID)

    count = state.get("count", 0)
    avg_length = state.get("avg_length", 0)
    tones = state.get("tones", {})
    topics = state.get("topics", {})

    context = ""
    if count > 0:
        top_tone = max(tones, key=tones.get) if tones else "neutral"
        top_topics = sorted(topics, key=topics.get, reverse=True)[:3]
        context = (
            f"User profile: {top_tone} tone, ~{int(avg_length)} words avg"
            + (f", topics: {', '.join(top_topics)}" if top_topics else "")
            + ".\n\n"
        )

    prompt = (
        f"{context}"
        "Improve the following text to make it clearer, more concise, and confident. "
        "Fix awkward phrasing and remove redundancy. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the improved text:\n\n"
        f"{text}"
    )

    result = bridge.generate(prompt)

    def _update_state():
        meta = _analyze(text)
        new_avg = (avg_length * count + len(text.split())) / (count + 1)
        if meta.get("tone"):
            tones[meta["tone"]] = tones.get(meta["tone"], 0) + 1
        if meta.get("topic"):
            topics[meta["topic"]] = topics.get(meta["topic"], 0) + 1
        bridge.set_state(_SKILL_ID, {
            "count": count + 1,
            "avg_length": round(new_avg, 1),
            "tones": tones,
            "topics": topics,
        })

    threading.Thread(target=_update_state, daemon=True).start()

    return result


def run_stream(text):
    """
    Streaming version — yields chunks as they arrive, updates state in background.
    """
    state = bridge.get_state(_SKILL_ID)

    count = state.get("count", 0)
    avg_length = state.get("avg_length", 0)
    tones = state.get("tones", {})
    topics = state.get("topics", {})

    context = ""
    if count > 0:
        top_tone = max(tones, key=tones.get) if tones else "neutral"
        top_topics = sorted(topics, key=topics.get, reverse=True)[:3]
        context = (
            f"User profile: {top_tone} tone, ~{int(avg_length)} words avg"
            + (f", topics: {', '.join(top_topics)}" if top_topics else "")
            + ".\n\n"
        )

    prompt = (
        f"{context}"
        "Improve the following text to make it clearer, more concise, and confident. "
        "Fix awkward phrasing and remove redundancy. "
        "IMPORTANT: Respond in the SAME language as the input text. "
        "Output ONLY the improved text:\n\n"
        f"{text}"
    )

    yield from bridge.generate_stream(prompt)

    def _update_state():
        meta = _analyze(text)
        new_avg = (avg_length * count + len(text.split())) / (count + 1)
        if meta.get("tone"):
            tones[meta["tone"]] = tones.get(meta["tone"], 0) + 1
        if meta.get("topic"):
            topics[meta["topic"]] = topics.get(meta["topic"], 0) + 1
        bridge.set_state(_SKILL_ID, {
            "count": count + 1,
            "avg_length": round(new_avg, 1),
            "tones": tones,
            "topics": topics,
        })

    threading.Thread(target=_update_state, daemon=True).start()
