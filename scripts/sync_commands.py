from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot import create_bot


def main() -> None:
    bot = create_bot()
    bot.sync_app_commands()


if __name__ == "__main__":
    main()
