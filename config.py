import os

from dotenv import load_dotenv

load_dotenv()


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"La variable d'environnement '{name}' est manquante.")

    return value


def get_required_int(name: str) -> int:
    value = get_required_env(name)

    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"La variable '{name}' doit contenir un nombre entier.")


DISCORD_TOKEN = get_required_env("DISCORD_TOKEN")
DATABASE_URL = get_required_env("DATABASE_URL")

GUILD_ID = get_required_int("GUILD_ID")

MOVEMENT_CHANNEL_ID = get_required_int("MOVEMENT_CHANNEL_ID")
LEVEL_CHANNEL_ID = get_required_int("LEVEL_CHANNEL_ID")
GAMES_CHANNEL_ID = get_required_int("GAMES_CHANNEL_ID")
POLL_CHANNEL_ID = get_required_int("POLL_CHANNEL_ID")
COMMANDS_CHANNEL_ID = get_required_int("COMMANDS_CHANNEL_ID")
WEBTOON_CHANNEL_ID = get_required_int("WEBTOON_CHANNEL_ID")
WEBTOON_MESSAGE_ID = get_required_int("WEBTOON_MESSAGE_ID")

TWITCH_NOTIFICATIONS_CHANNEL_ID = get_required_int("TWITCH_NOTIFICATIONS_CHANNEL_ID")

TWITCH_CLIENT_ID = get_required_env("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = get_required_env("TWITCH_CLIENT_SECRET")


def get_role_ids() -> list[int]:
    raw = os.getenv("REQUIRED_ROLE_IDS", "")

    if not raw:
        return []

    return [int(role_id.strip()) for role_id in raw.split(",") if role_id.strip()]


REQUIRED_ROLE_IDS = get_role_ids()
