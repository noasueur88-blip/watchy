from __future__ import annotations

import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for

load_dotenv()


def create_panel(bot) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("PANEL_SECRET_KEY", "panel-secret")
    panel_password = os.getenv("PANEL_PASSWORD", "change-moi")

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("authenticated"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.get("/login")
    def login():
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        if request.form.get("password") == panel_password:
            session["authenticated"] = True
            return redirect(url_for("dashboard"))
        flash("Mot de passe incorrect.", "error")
        return redirect(url_for("login"))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        snapshot = bot.get_dashboard_snapshot()
        return render_template("index.html", snapshot=snapshot)

    @app.post("/actions/maintenance")
    @login_required
    def maintenance():
        enabled = request.form.get("enabled") == "true"
        bot.set_maintenance(enabled)
        flash(f"Maintenance {'activee' if enabled else 'desactivee'}.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/actions/lockdown")
    @login_required
    def lockdown():
        guild_id = int(request.form["guild_id"])
        try:
            bot.run_coro(bot.lockdown_guild(guild_id))
            flash("Serveur verrouille.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    @app.post("/actions/unlock")
    @login_required
    def unlock():
        guild_id = int(request.form["guild_id"])
        try:
            bot.run_coro(bot.unlock_guild(guild_id))
            flash("Serveur deverrouille.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    @app.post("/actions/clear")
    @login_required
    def clear():
        channel_id = int(request.form["channel_id"])
        amount = max(1, min(int(request.form["amount"]), 100))
        try:
            deleted = bot.run_coro(bot.clear_channel(channel_id, amount))
            flash(f"{deleted} messages supprimes.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    return app
