from __future__ import annotations

import os
import time

from dotenv import load_dotenv

from bot import DiscordSecurityBot
from panel import create_panel

load_dotenv()


def main() -> None:
    bot = DiscordSecurityBot()
    bot.start_in_thread()

    # Petite attente pour laisser le thread Discord demarrer avant d'ouvrir le panel.
    time.sleep(2)

    app = create_panel(bot)
    host = os.getenv("PANEL_HOST", "127.0.0.1")
    port = int(os.getenv("PANEL_PORT", "5000"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
