import asyncio
import logging
import os
import signal

from .bot import Plexcord


async def main():
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token or token == "incolla_il_token_del_bot":
        raise SystemExit("Imposta DISCORD_TOKEN nel file .env (Docker) o nell'ambiente.")
    bot = Plexcord(os.environ.get("PLEXCORD_DATA", "data"))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
        except NotImplementedError:
            pass  # Windows: asyncio.run gestisce Ctrl+C.
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    # Evitiamo traceback HTTP/FFmpeg contenenti credenziali o URL privati.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("discord.http").setLevel(logging.CRITICAL)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
