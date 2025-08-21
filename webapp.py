from pipeline import (
    generate_story, apply_tweak,
    generate_first_chapter, generate_next_chapter
)
import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash

# Load .env locally; on Heroku use config vars
load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-for-local-only")

    @app.route("/", methods=["GET"])
    def index():
        state = session.get("state")
        return render_template("index.html", state=state)

    @app.route("/generate", methods=["POST"])
    def generate():
        prompt = request.form.get("prompt", "").strip()
        mode = request.form.get("mode", "short")  # 'short' or 'arc'
        if not prompt:
            flash("Please enter a quick story idea.", "warning")
            return redirect(url_for("index"))

        if not os.getenv("OPENAI_API_KEY"):
            flash(
                "OPENAI_API_KEY is not set. Configure it on Heroku or in your .env.", "danger")
            return redirect(url_for("index"))

        try:
            if mode == "arc":
                # Classify and produce Chapter 1
                # Reuse generate_story's classifier path to build a brief quickly:
                # We'll call generate_first_chapter with that brief instead of making a full short story.
                # To avoid an extra call, we can just run generate_first_chapter and let it classify internally if you want,
                # but we'll keep consistency by calling generate_story once, then discard its 'story' and reuse 'brief'.
                # fast brief creation
                init = generate_story(prompt, max_rounds=1)
                brief = init["brief"]

                # Chapter 1
                ch1, verdict1 = generate_first_chapter(brief)
                session["state"] = {
                    "mode": "arc",
                    "prompt": prompt,
                    "brief": brief,
                    "chapters": [ch1],
                    "arc_should_end_next": False,
                    "history": [{"round": "chapter-1", "verdict": verdict1}],
                }
            else:
                # Short story mode (current flow)
                result = generate_story(prompt, max_rounds=2)
                session["state"] = {
                    "mode": "short",
                    "prompt": prompt,
                    "brief": result["brief"],
                    "story": result["story"],
                    "history": result["history"],
                    "passed": result.get("passed", False),
                }

        except Exception as e:
            flash(f"Error generating: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/tweak", methods=["POST"])
    def tweak():
        state = session.get("state")
        if not state:
            flash("Please generate a story first.", "warning")
            return redirect(url_for("index"))

        tweak_text = request.form.get("tweak", "").strip()
        if not tweak_text:
            flash("Type any tweak to apply.", "warning")
            return redirect(url_for("index"))

        try:
            if state.get("mode") == "arc":
                # Apply tweak to the most recent chapter (revise last chapter)
                brief = state["brief"]
                chapters = state["chapters"]
                last = chapters[-1]

                new_chapter, new_verdict = apply_tweak(
                    brief, last, tweak_text, rounds=2)
                chapters[-1] = new_chapter
                state["history"].append(
                    {"round": f"tweak-ch{len(chapters)}", "verdict": new_verdict})
                session["state"] = state
            else:
                # Short story tweak (existing)
                brief = state["brief"]
                story = state["story"]
                new_story, new_verdict = apply_tweak(
                    brief, story, tweak_text, rounds=2)
                state["story"] = new_story
                state["history"].append(
                    {"round": f"tweak-{len(state['history'])+1}", "verdict": new_verdict})
                session["state"] = state

        except Exception as e:
            flash(f"Error applying tweak: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/arc/next", methods=["POST"])
    def arc_next():
        state = session.get("state")
        if not state or state.get("mode") != "arc":
            flash("Start a multi-arc story first.", "warning")
            return redirect(url_for("index"))

        try:
            brief = state["brief"]
            chapters = state["chapters"]
            end_in_next = False
            end_now = False

            chapter, verdict = generate_next_chapter(
                brief, chapters, end_in_next=end_in_next, end_now=end_now)
            chapters.append(chapter)
            state["history"].append(
                {"round": f"chapter-{len(chapters)}", "verdict": verdict})
            state["arc_should_end_next"] = False
            session["state"] = state

        except Exception as e:
            flash(f"Error creating next chapter: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/arc/end_next", methods=["POST"])
    def arc_end_next():
        state = session.get("state")
        if not state or state.get("mode") != "arc":
            flash("Start a multi-arc story first.", "warning")
            return redirect(url_for("index"))

        try:
            brief = state["brief"]
            chapters = state["chapters"]
            # This chapter sets up for the finale in the next one.
            chapter, verdict = generate_next_chapter(
                brief, chapters, end_in_next=True, end_now=False)
            chapters.append(chapter)
            state["history"].append(
                {"round": f"chapter-{len(chapters)} (setup-finale)", "verdict": verdict})
            state["arc_should_end_next"] = True
            session["state"] = state
        except Exception as e:
            flash(f"Error creating penultimate chapter: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/arc/end_now", methods=["POST"])
    def arc_end_now():
        state = session.get("state")
        if not state or state.get("mode") != "arc":
            flash("Start a multi-arc story first.", "warning")
            return redirect(url_for("index"))

        try:
            brief = state["brief"]
            chapters = state["chapters"]
            # Wrap everything up in THIS chapter
            chapter, verdict = generate_next_chapter(
                brief, chapters, end_in_next=False, end_now=True)
            chapters.append(chapter)
            state["history"].append(
                {"round": f"chapter-{len(chapters)} (finale)", "verdict": verdict})
            state["arc_should_end_next"] = False
            session["state"] = state
        except Exception as e:
            flash(f"Error creating final chapter: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/reset", methods=["POST"])
    def reset():
        session.pop("state", None)
        flash("Cleared session. Start fresh!", "info")
        return redirect(url_for("index"))

    return app


app = create_app()
