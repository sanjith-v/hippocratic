from pipeline import generate_story, apply_tweak
import os
import json
from dotenv import load_dotenv

# Load .env variables
load_dotenv()


def main():
    print("🌙 Hippocratic AI — Bedtime Story Generator (ages 5–10)")
    print("-----------------------------------------------------")
    user_input = input("What kind of story do you want to hear?\n> ").strip()
    if not user_input:
        print("Please provide a short request (e.g., 'A gentle story about a kitten learning to share').")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set. Create .env and add OPENAI_API_KEY, or export it.")
        return

    # ---- First story generation ----
    print("\nGenerating your bedtime story... (this may take a moment)\n")
    result = generate_story(user_input, max_rounds=2)

    print("\n=== Your Story ===\n")
    print(result["story"])
    print("\n===================\n")

    print("Quality Check (Judge):")
    for r in result["history"]:
        v = r["verdict"]
        scores = v.get("scores", {})
        avg = scores.get("average")
        print(
            f"  Round {r['round']}: pass={v.get('pass')} avg={avg} scores={scores}")

    # ---- Tweak loop ----
    preset_map = {
        "shorter": "Reduce to ~450 words. Simplify sentences further.",
        "calmer": "Lower stakes, slower cadence, extra reassurance in the last two paragraphs.",
        "more-dialogue": "Add gentle dialogue between characters with simple tags.",
        "new-moral": "Change the moral to 'kindness and sharing' clearly in the final line."
    }

    while True:
        tweak = input(
            "\nWould you like to make changes? Type ANY tweak (e.g., 'make the cat shyer and add a lullaby ending').\n"
            "Type 'no' to finish.\n> "
        ).strip()

        if tweak.lower() in {"no", "n", ""}:
            print("Okay! Good night and sweet dreams. 🌟")
            break

        tweak_text = preset_map.get(tweak.lower(), tweak)

        print("\nApplying your tweak and regenerating...\n")
        new_story, new_verdict = apply_tweak(
            result["brief"], result["story"], tweak_text, rounds=2)

        result["story"] = new_story
        result["history"].append(
            {"round": f"tweak-{len(result['history'])+1}", "verdict": new_verdict})

        print("\n=== Revised Story ===\n")
        print(new_story)
        print("\n======================\n")
        scores = new_verdict.get("scores", {})
        print(
            f"Re-judged: pass={new_verdict.get('pass')} avg={scores.get('average')} scores={scores}")


if __name__ == "__main__":
    main()
