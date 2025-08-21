from pipeline import generate_story, apply_tweak
import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash

# Load .env locally; on Heroku you'll use config vars instead
load_dotenv()


def create_app():
    app = Flask(__name__)
    # IMPORTANT: set a strong secret; on Heroku set as config var SECRET_KEY
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-for-local-only")

    @app.route("/", methods=["GET"])
    def index():
        state = session.get("state")
        return render_template("index.html", state=state)

    @app.route("/generate", methods=["POST"])
    def generate():
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            flash("Please enter a quick story idea.", "warning")
            return redirect(url_for("index"))

        if not os.getenv("OPENAI_API_KEY"):
            flash(
                "OPENAI_API_KEY is not set. Configure it on Heroku or in your .env.", "danger")
            return redirect(url_for("index"))

        try:
            result = generate_story(prompt, max_rounds=2)
            session["state"] = {
                "brief": result["brief"],
                "story": result["story"],
                "history": result["history"],
                "passed": result.get("passed", False),
                "prompt": prompt,
            }
        except Exception as e:
            flash(f"Error generating story: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/tweak", methods=["POST"])
    def tweak():
        tweak_text = request.form.get("tweak", "").strip()
        state = session.get("state")
        if not state:
            flash("Please generate a story first.", "warning")
            return redirect(url_for("index"))
        if not tweak_text:
            flash(
                "Type any tweak to apply (e.g., 'shorter ending, clearer moral').", "warning")
            return redirect(url_for("index"))

        try:
            new_story, new_verdict = apply_tweak(
                state["brief"], state["story"], tweak_text, rounds=2
            )
            # Append to history and update story
            state["story"] = new_story
            state["history"].append({
                "round": f"tweak-{len(state['history'])+1}",
                "verdict": new_verdict
            })
            session["state"] = state
        except Exception as e:
            flash(f"Error applying tweak: {e}", "danger")

        return redirect(url_for("index"))

    @app.route("/reset", methods=["POST"])
    def reset():
        session.pop("state", None)
        flash("Cleared session. Start fresh!", "info")
        return redirect(url_for("index"))

    return app


app = create_app()
