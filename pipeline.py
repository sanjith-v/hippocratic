import json
from typing import Dict, Any

from llm import chat
from prompts import (
    CLASSIFIER_SYSTEM, CLASSIFIER_USER_TEMPLATE,
    STORYTELLER_SYSTEM, STORYTELLER_USER_TEMPLATE,
    JUDGE_SYSTEM, JUDGE_USER_TEMPLATE,
    EDITOR_SYSTEM, EDITOR_USER_TEMPLATE
)


def _parse_json(s: str) -> Dict[str, Any]:
    s = s.strip()
    # If the model adds extra text accidentally, try to find JSON block
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end+1]
    return json.loads(s)


def classify_request(user_request: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM},
        {"role": "user", "content": CLASSIFIER_USER_TEMPLATE.format(
            request=user_request)}
    ]
    raw = chat(messages, max_tokens=400, temperature=0.2)
    brief = _parse_json(raw)
    # Ensure minimum guardrails
    brief.setdefault("age_range", "5-10")
    brief.setdefault("length_words", 550)
    avoid = set(brief.get("avoid_topics", []))
    avoid.update({"violence", "bullying", "fear",
                 "adult themes", "weapons", "darkness"})
    brief["avoid_topics"] = sorted(list(avoid))
    return brief


def tell_story(brief: Dict[str, Any]) -> str:
    messages = [
        {"role": "system", "content": STORYTELLER_SYSTEM},
        {"role": "user", "content": STORYTELLER_USER_TEMPLATE.format(
            brief_json=json.dumps(brief))}
    ]
    story = chat(messages, max_tokens=1200, temperature=0.8)
    return story.strip()


def judge_story(brief: Dict[str, Any], story: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": JUDGE_USER_TEMPLATE.format(
            brief_json=json.dumps(brief), story=story)}
    ]
    raw = chat(messages, max_tokens=500, temperature=0.1)
    verdict = _parse_json(raw)
    # compute average if missing
    scores = verdict.get("scores", {})
    if "average" not in scores and scores:
        # average only over numeric fields present
        nums = [v for k, v in scores.items() if isinstance(v, (int, float))]
        if nums:
            verdict["scores"]["average"] = round(sum(nums) / len(nums), 2)
    return verdict


def edit_story(brief: Dict[str, Any], story: str, judge_json: Dict[str, Any]) -> str:
    messages = [
        {"role": "system", "content": EDITOR_SYSTEM},
        {"role": "user", "content": EDITOR_USER_TEMPLATE.format(
            brief_json=json.dumps(brief),
            story=story,
            judge_json=json.dumps(judge_json)
        )}
    ]
    revised = chat(messages, max_tokens=1200, temperature=0.6)
    return revised.strip()


def generate_story(user_request: str, max_rounds: int = 2) -> Dict[str, Any]:
    brief = classify_request(user_request)
    story = tell_story(brief)
    history = []

    for round_idx in range(1, max_rounds+1):
        verdict = judge_story(brief, story)
        history.append({"round": round_idx, "verdict": verdict})
        if verdict.get("pass"):
            return {"brief": brief, "story": story, "history": history, "passed": True}
        # Otherwise, try a revision
        story = edit_story(brief, story, verdict)

    # Final check after last edit
    final_verdict = judge_story(brief, story)
    history.append({"round": max_rounds+1, "verdict": final_verdict})
    return {"brief": brief, "story": story, "history": history, "passed": final_verdict.get("pass", False)}
