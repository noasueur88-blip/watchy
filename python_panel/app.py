from __future__ import annotations

import os
from datetime import timedelta
from functools import wraps
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for


load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    app.config["ADMIN_USERNAME"] = os.getenv("ADMIN_USERNAME", "admin")
    app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "admin123")
    app.config["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_BOT_TOKEN", "")
    app.config["DISCORD_GUILD_ID"] = os.getenv("DISCORD_GUILD_ID", "")
    app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID", "")

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "admin_user" not in session:
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    def discord_headers() -> dict[str, str]:
        return {
            "Authorization": f"Bot {app.config['DISCORD_BOT_TOKEN']}",
            "User-Agent": "PulsePanelPython/1.0",
        }

    def discord_request(path: str) -> Any:
        response = requests.get(
            f"https://discord.com/api/v10{path}",
            headers=discord_headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def get_discord_overview() -> dict[str, Any]:
        token = app.config["DISCORD_BOT_TOKEN"]
        guild_id = app.config["DISCORD_GUILD_ID"]
        client_id = app.config["DISCORD_CLIENT_ID"]

        overview = {
            "connected": False,
            "server_name": "Non configure",
            "member_count": 0,
            "online_count": 0,
            "channel_count": 0,
            "role_count": 0,
            "bot_name": "Bot inconnu",
            "invite_url": "",
            "error": "",
            "config_ready": bool(token and guild_id),
            "missing_settings": [],
        }

        if not token or not guild_id:
            missing_settings = []
            if not token:
                missing_settings.append("DISCORD_BOT_TOKEN")
            if not guild_id:
                missing_settings.append("DISCORD_GUILD_ID")
            overview["missing_settings"] = missing_settings
            overview["error"] = "Ajoute les variables requises dans ton fichier .env pour connecter Discord."
            return overview

        try:
            guild = discord_request(f"/guilds/{guild_id}?with_counts=true")
            channels = discord_request(f"/guilds/{guild_id}/channels")
            application = discord_request("/applications/@me")

            overview.update(
                {
                    "connected": True,
                    "server_name": guild.get("name", "Serveur Discord"),
                    "member_count": guild.get("approximate_member_count", 0),
                    "online_count": guild.get("approximate_presence_count", 0),
                    "channel_count": len(channels),
                    "role_count": len(guild.get("roles", [])),
                    "bot_name": application.get("name", "Bot connecte"),
                    "invite_url": (
                        f"https://discord.com/oauth2/authorize?client_id={client_id}"
                        "&scope=bot%20applications.commands&permissions=8"
                        if client_id
                        else ""
                    ),
                }
            )
        except requests.RequestException as exc:
            overview["error"] = f"Connexion Discord impossible: {exc}"

        return overview

    @app.route("/healthz")
    def healthz():
        return {"ok": True}, 200

    @app.route("/")
    def home():
        return redirect(url_for("dashboard" if "admin_user" in session else "login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "admin_user" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if (
                username == app.config["ADMIN_USERNAME"]
                and password == app.config["ADMIN_PASSWORD"]
            ):
                session.permanent = True
                session["admin_user"] = username
                return redirect(url_for("dashboard"))

            flash("Identifiants invalides.", "error")

        return render_template("login.html")

    @app.route("/logout", methods=["GET", "POST"])
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        overview = get_discord_overview()
        return render_template(
            "dashboard.html",
            admin_user=session["admin_user"],
            overview=overview,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
