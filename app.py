from pipeline import generate_story
import os
import json

from dotenv import load_dotenv

load_dotenv()


def main():
    print("🌙 Hippocratic AI — Bedtime Story Generator (ages 5–10)")
    print("-----------------------------------------------------")
    user_input = input("What kind of story do you want to hear?\n> ").strip()
    if not user_input:
        print("Please provide a short request (e.g., 'A gentle story about a kitten learning to share').")
        return

    print("\nGenerating... (this may take a moment)\n")
    result = generate_story(user_input, max_rounds=2)

    print("\n=== Your Story ===\n")
    print(result["story"])
    print("\n===================\n")

    # Optional: show judge history compactly
    print("Quality Check (Judge):")
    for r in result["history"]:
        v = r["verdict"]
        scores = v.get("scores", {})
        avg = scores.get("average")
        print(
            f"  Round {r['round']}: pass={v.get('pass')} avg={avg} scores={scores}")

    # Offer quick tweak pass
    choice = input(
        "\nWould you like a tweak? (no/shorter/calmer/more-dialogue/new-moral)\n> ").strip().lower()
    if choice in {"shorter", "calmer", "more-dialogue", "new-moral"}:
        tweak_map = {
            "shorter": "Reduce to ~450 words. Simplify sentences further.",
            "calmer": "Lower stakes, slower cadence, extra reassurance in last two paragraphs.",
            "more-dialogue": "Add gentle dialogue between characters with simple tags.",
            "new-moral": "Change the moral to 'kindness and sharing' clearly in the final line."
        }
        # Inject a small edit request by reusing the last judge verdict as container
        last_verdict = result["history"][-1]["verdict"] if result["history"] else {
            "edit_instructions": ""}
        last_verdict["edit_instructions"] = (last_verdict.get(
            "edit_instructions", "") + " " + tweak_map[choice]).strip()

        from pipeline import edit_story, judge_story
        story2 = edit_story(result["brief"], result["story"], last_verdict)
        verdict2 = judge_story(result["brief"], story2)

        print("\n=== Revised Story ===\n")
        print(story2)
        print("\n======================\n")
        print(
            f"Re-judged: pass={verdict2.get('pass')} avg={verdict2.get('scores',{}).get('average')}")
    else:
        print("Okay! Good night and sweet dreams. 🌟")


if __name__ == "__main__":
    # Ensure the key is present; warn if not
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "WARNING: OPENAI_API_KEY not set. Export it before running (see .env.example).")
    main()
