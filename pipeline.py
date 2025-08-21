import json
import re
from typing import Dict, Any, Tuple, List

from llm import chat
from prompts import (
    CLASSIFIER_SYSTEM, CLASSIFIER_USER_TEMPLATE,
    STORYTELLER_SYSTEM, STORYTELLER_USER_TEMPLATE,
    JUDGE_SYSTEM, JUDGE_USER_TEMPLATE,
    EDITOR_SYSTEM, EDITOR_USER_TEMPLATE,
    CHAPTER_STORYTELLER_SYSTEM, CHAPTER_USER_TEMPLATE
)

# --- Sanitizer: guarantees no markdown/labels like **Title**, Title:, # etc. ---


def _sanitize_story_text(text: str) -> str:
    """
    Enforce plain text:
    - Remove bold/backticks and heading markers.
    - First non-empty line becomes a plain title (strip 'Title:' and symbols).
    - Trim extra whitespace.
    """
    if not text:
        return text

    # Remove inline emphasis/backticks globally
    text = text.replace("**", "").replace("__", "").replace("`", "")

    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    # First non-empty line -> title cleanup
    first_idx = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first_idx is not None:
        first = lines[first_idx].strip()
        # Strip heading markers and 'Title' labels
        # leading '#'
        first = re.sub(r'^\s*#+\s*', '', first)
        # 'Title:' or 'Title -'
        first = re.sub(r'^\s*title\s*[:\-]\s*', '', first, flags=re.I)
        # line is just 'Title'
        first = re.sub(r'^\s*title\s*$', '', first, flags=re.I)
        first = first.strip(" *:_-")
        lines[first_idx] = first

    # Remove leading '# ' from other lines too
    lines = [re.sub(r'^\s*#+\s*', '', ln) for ln in lines]

    cleaned = "\n".join(lines).strip()
    return cleaned


def _parse_json(s: str) -> Dict[str, Any]:
    s = s.strip()
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end+1]
    return json.loads(s)

# -------------------- Core (classifier / storyteller / judge / editor) --------------------


def classify_request(user_request: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM},
        {"role": "user", "content": CLASSIFIER_USER_TEMPLATE.format(
            request=user_request)}
    ]
    raw = chat(messages, max_tokens=400, temperature=0.2)
    brief = _parse_json(raw)
    # Guardrails
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
    return _sanitize_story_text(story)


def judge_story(brief: Dict[str, Any], story: str, user_tweak: str = "") -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": JUDGE_USER_TEMPLATE.format(
            brief_json=json.dumps(brief),
            user_tweak=(user_tweak or "None"),
            story=story
        )}
    ]
    raw = chat(messages, max_tokens=500, temperature=0.1)
    verdict = _parse_json(raw)
    scores = verdict.get("scores", {})
    if "average" not in scores and scores:
        nums = [v for k, v in scores.items() if isinstance(v, (int, float))]
        if nums:
            verdict["scores"]["average"] = round(sum(nums) / len(nums), 2)
    return verdict


def edit_story(brief: Dict[str, Any], story: str, judge_json: Dict[str, Any], user_tweak: str = "") -> str:
    messages = [
        {"role": "system", "content": EDITOR_SYSTEM},
        {"role": "user", "content": EDITOR_USER_TEMPLATE.format(
            brief_json=json.dumps(brief),
            user_tweak=(user_tweak or "None"),
            story=story,
            judge_json=json.dumps(judge_json)
        )}
    ]
    revised = chat(messages, max_tokens=1200, temperature=0.6)
    return _sanitize_story_text(revised)


def generate_story(user_request: str, max_rounds: int = 2) -> Dict[str, Any]:
    brief = classify_request(user_request)
    story = tell_story(brief)
    history = []

    for round_idx in range(1, max_rounds+1):
        verdict = judge_story(brief, story)
        history.append({"round": round_idx, "verdict": verdict})
        if verdict.get("pass"):
            return {"brief": brief, "story": story, "history": history, "passed": True}
        story = edit_story(brief, story, verdict)

    final_verdict = judge_story(brief, story)
    history.append({"round": max_rounds+1, "verdict": final_verdict})
    return {"brief": brief, "story": story, "history": history, "passed": final_verdict.get("pass", False)}


def apply_tweak(
    brief: Dict[str, Any],
    current_story: str,
    tweak_text: str,
    rounds: int = 2
) -> Tuple[str, Dict[str, Any]]:
    verdict = judge_story(brief, current_story, user_tweak=tweak_text)
    existing = verdict.get("edit_instructions", "")
    verdict["edit_instructions"] = (
        existing + " USER TWEAK: " + tweak_text).strip()

    story = current_story
    for _ in range(max(1, rounds)):
        story = edit_story(brief, story, verdict, user_tweak=tweak_text)
        verdict = judge_story(brief, story, user_tweak=tweak_text)
        if verdict.get("pass") and verdict.get("scores", {}).get("requirements_satisfaction", 8) >= 8:
            break

    return story, verdict

# -------------------- Multi-arc / chapter helpers --------------------


def _concat_chapters(chapters: List[str]) -> str:
    """Join chapters with two newlines for readability."""
    return "\n\n".join(chapters).strip()


def generate_first_chapter(brief: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Create chapter 1 using the CHAPTER storyteller + judge/edit loop.
    Returns (chapter_text, verdict).
    """
    messages = [
        {"role": "system", "content": CHAPTER_STORYTELLER_SYSTEM},
        {"role": "user", "content": CHAPTER_USER_TEMPLATE.format(
            brief_json=json.dumps(brief),
            story_so_far="",
            end_in_next="false",
            end_now="false"
        )}
    ]
    chapter = chat(messages, max_tokens=900, temperature=0.8)
    chapter = _sanitize_story_text(chapter)

    verdict = judge_story(brief, chapter)
    if verdict.get("pass"):
        return chapter, verdict

    # One editing pass if needed
    chapter = edit_story(brief, chapter, verdict)
    verdict = judge_story(brief, chapter)
    return chapter, verdict


def generate_next_chapter(
    brief: Dict[str, Any],
    prior_chapters: List[str],
    end_in_next: bool = False,
    end_now: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate the next chapter considering STORY SO FAR and end flags.
    Returns (chapter_text, verdict).
    """
    story_so_far = _concat_chapters(prior_chapters)
    messages = [
        {"role": "system", "content": CHAPTER_STORYTELLER_SYSTEM},
        {"role": "user", "content": CHAPTER_USER_TEMPLATE.format(
            brief_json=json.dumps(brief),
            story_so_far=story_so_far,
            end_in_next=str(end_in_next).lower(),
            end_now=str(end_now).lower()
        )}
    ]
    chapter = chat(messages, max_tokens=900, temperature=0.8)
    chapter = _sanitize_story_text(chapter)

    verdict = judge_story(brief, chapter)
    if verdict.get("pass"):
        return chapter, verdict

    # One editing pass if needed
    chapter = edit_story(brief, chapter, verdict)
    verdict = judge_story(brief, chapter)
    return chapter, verdict
