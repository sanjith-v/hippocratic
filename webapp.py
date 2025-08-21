from pipeline import (
    generate_story, apply_tweak,
    generate_first_chapter, generate_next_chapter
)
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash

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
        mode = request.form.get("mode", "short")
        if not prompt:
            flash("Please enter a quick story idea.", "warning")
            return redirect(url_for("index"))

        if not os.getenv("OPENAI_API_KEY"):
            flash(
                "OPENAI_API_KEY is not set. Configure it on Heroku or in your .env.", "danger")
            return redirect(url_for("index"))

        try:
            if mode == "arc":
                # Build brief quickly via the short flow (to get a brief) then start Chapter 1
                init = generate_story(prompt, max_rounds=1)
                brief = init["brief"]

                ch1, verdict1 = generate_first_chapter(brief)
                session["state"] = {
                    "mode": "arc",
                    "prompt": prompt,
                    "brief": brief,
                    "chapters": [ch1],
                    # final chapter already produced? (False initially)
                    "arc_ready_to_end": False,
                    "history": [{"round": "chapter-1", "verdict": verdict1}],
                }
            else:
                # Short story mode
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
                # If the final chapter was already created, don't allow tweaks (user should End Now)
                if state.get("arc_ready_to_end"):
                    flash(
                        "The final chapter is ready. Click 'End Now' to finish.", "info")
                    return redirect(url_for("index"))

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
        if state.get("arc_ready_to_end"):
            flash(
                "The final chapter is already created. Click 'End Now' to finish.", "info")
            return redirect(url_for("index"))

        try:
            brief = state["brief"]
            chapters = state["chapters"]
            chapter, verdict = generate_next_chapter(
                brief, chapters, end_now=False)
            chapters.append(chapter)
            state["history"].append(
                {"round": f"chapter-{len(chapters)}", "verdict": verdict})
            session["state"] = state

        except Exception as e:
            flash(f"Error creating next chapter: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/arc/end_next", methods=["POST"])
    def arc_end_next():
        """
        Generate the FINAL chapter now, then show only 'End Now' on the page.
        """
        state = session.get("state")
        if not state or state.get("mode") != "arc":
            flash("Start a multi-arc story first.", "warning")
            return redirect(url_for("index"))

        if state.get("arc_ready_to_end"):
            # Already produced the final chapter; just show End Now on UI
            return redirect(url_for("index"))

        try:
            brief = state["brief"]
            chapters = state["chapters"]
            # Produce the final chapter immediately
            chapter, verdict = generate_next_chapter(
                brief, chapters, end_now=True)
            chapters.append(chapter)
            state["history"].append(
                {"round": f"chapter-{len(chapters)} (final)", "verdict": verdict})
            state["arc_ready_to_end"] = True  # UI will only show End Now
            session["state"] = state

        except Exception as e:
            flash(f"Error creating final chapter: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/arc/end_now", methods=["POST"])
    def arc_end_now():
        """
        When End Now is clicked, immediately reset the session and return to start.
        (We assume the final chapter has already been generated by /arc/end_next.)
        """
        session.pop("state", None)
        flash("Story ended. Start a new one!", "info")
        return redirect(url_for("index"))

    @app.route("/reset", methods=["POST"])
    def reset():
        session.pop("state", None)
        flash("Cleared session. Start fresh!", "info")
        return redirect(url_for("index"))

    return app


app = create_app()
