import math
import asyncpg


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    # =========================================================
    # CONNECTION
    # =========================================================

    async def connect(self) -> None:
        if self.pool is not None:
            return

        self.pool = await asyncpg.create_pool(
            dsn=self.database_url, min_size=1, max_size=10, command_timeout=30
        )

        print("✅ Connexion PostgreSQL établie.")

    async def disconnect(self) -> None:
        if self.pool is None:
            return

        await self.pool.close()
        self.pool = None

        print("🔌 Connexion PostgreSQL fermée.")

    def _get_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("La connexion PostgreSQL n'est pas initialisée.")

        return self.pool

    async def test_connection(self) -> bool:
        pool = self._get_pool()

        async with pool.acquire() as connection:
            result = await connection.fetchval("SELECT 1;")

        return result == 1

    # =========================================================
    # WEBTOONS
    # =========================================================

    async def get_all_webtoons(self) -> list[tuple[str, int, str]]:

        pool = self._get_pool()

        query = """
            SELECT Name, Chapter, Status
            FROM Webtoons
        """

        async with pool.acquire() as connection:
            rows = await connection.fetch(query)

        return [(row["name"], row["chapter"], row["status"]) for row in rows]

    async def add_webtoon(self, name: str, chapter: int, status: str) -> bool:

        pool = self._get_pool()

        query = """
            INSERT INTO Webtoons (Name, Chapter, Status)
            VALUES ($1, $2, $3)
            ON CONFLICT (Name) DO NOTHING
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name, chapter, status)

        return result != "INSERT 0 0"

    async def delete_webtoon(self, name: str) -> bool:
        pool = self._get_pool()

        query = """
            DELETE FROM Webtoons
            WHERE Name = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name)

        return result != "DELETE 0"

    async def update_webtoon(self, name: str, chapter: int, status: str) -> bool:

        pool = self._get_pool()

        query = """
            UPDATE Webtoons
            SET Chapter = $2,
                Status = $3
            WHERE Name = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name, chapter, status)

        return result != "UPDATE 0"

    # =========================================================
    # GIFS
    # =========================================================

    async def add_gif(self, name: str, url: str) -> bool:

        pool = self._get_pool()

        query = """
            INSERT INTO Gifs (Name, Url)
            VALUES ($1, $2)
            ON CONFLICT (Name) DO NOTHING
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name, url)

        return result != "INSERT 0 0"

    async def delete_gif(self, name: str) -> bool:
        pool = self._get_pool()

        query = """
            DELETE FROM Gifs
            WHERE Name = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name)

        return result != "DELETE 0"

    async def get_gifs(self) -> list[tuple[str, str]]:

        pool = self._get_pool()

        query = """
            SELECT Name, Url
            FROM Gifs
        """

        async with pool.acquire() as connection:
            rows = await connection.fetch(query)

        return [(row["name"], row["url"]) for row in rows]

    async def update_gif(self, name: str, new_url: str) -> bool:

        pool = self._get_pool()

        query = """
            UPDATE Gifs
            SET Url = $2
            WHERE Name = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name, new_url)

        return result != "UPDATE 0"

    # =========================================================
    # XP
    # =========================================================

    async def get_user_xp(self, user_id: int) -> int:

        pool = self._get_pool()

        query = """
            SELECT XP
            FROM UserXP
            WHERE UserId = $1
        """

        async with pool.acquire() as connection:
            result = await connection.fetchval(query, user_id)

        return int(result) if result is not None else 0

    async def get_user_level(self, user_id: int) -> int:

        pool = self._get_pool()

        query = """
            SELECT Level
            FROM UserXP
            WHERE UserId = $1
        """

        async with pool.acquire() as connection:
            result = await connection.fetchval(query, user_id)

        return int(result) if result is not None else 0

    async def add_xp(
        self, user_id: int, username: str, xp_to_add: int = 1
    ) -> tuple[bool, int, int]:

        pool = self._get_pool()

        try:
            async with pool.acquire() as connection:

                async with connection.transaction():

                    row = await connection.fetchrow(
                        """
                        SELECT XP, Level
                        FROM UserXP
                        WHERE UserId = $1
                        FOR UPDATE
                        """,
                        user_id,
                    )

                    if row is None:
                        current_xp = 0
                        current_level = 0
                    else:
                        current_xp = row["xp"]
                        current_level = row["level"]

                    new_xp = current_xp + xp_to_add

                    # Exactement la même formule que ton bot C#
                    new_level = math.floor(math.sqrt(new_xp / 10.0))

                    leveled_up = new_level > current_level

                    await connection.execute(
                        """
                        INSERT INTO UserXP (
                            UserId,
                            UserName,
                            XP,
                            Level
                        )
                        VALUES ($1, $2, $3, $4)

                        ON CONFLICT (UserId)
                        DO UPDATE SET
                            XP = EXCLUDED.XP,
                            UserName = EXCLUDED.UserName,
                            Level = EXCLUDED.Level
                        """,
                        user_id,
                        username,
                        new_xp,
                        new_level,
                    )

            return (leveled_up, new_level, new_xp)

        except Exception as error:
            print(f"❌ DB error for {username}: {error}")

            return False, 0, 0

    async def get_leaderboard(self) -> list[tuple[int, str, int, int]]:

        pool = self._get_pool()

        query = """
            SELECT
                UserId,
                UserName,
                Level,
                XP
            FROM UserXP
            ORDER BY Level DESC, XP DESC
        """

        async with pool.acquire() as connection:
            rows = await connection.fetch(query)

        return [
            (row["userid"], row["username"], row["level"], row["xp"]) for row in rows
        ]

    @staticmethod
    def get_xp_stats(xp: int, level: int) -> tuple[int, int, int, int]:

        current_level_total_xp = level * level * 10
        next_level_total_xp = (level + 1) * (level + 1) * 10

        current_xp = max(0, xp - current_level_total_xp)

        next_level_xp = next_level_total_xp - current_level_total_xp

        xp_remaining = max(0, next_level_xp - current_xp)

        return (level, current_xp, next_level_xp, xp_remaining)

    async def get_user_rank(self, user_id: int) -> int:

        pool = self._get_pool()

        query = """
            SELECT COUNT(*) + 1
            FROM UserXP
            WHERE
                Level > (
                    SELECT Level
                    FROM UserXP
                    WHERE UserId = $1
                )

                OR

                (
                    Level = (
                        SELECT Level
                        FROM UserXP
                        WHERE UserId = $1
                    )

                    AND XP > (
                        SELECT XP
                        FROM UserXP
                        WHERE UserId = $1
                    )
                )
        """

        async with pool.acquire() as connection:
            result = await connection.fetchval(query, user_id)

        return int(result or 1)

    async def set_user_xp(
        self, user_id: int, username: str, xp: int
    ) -> tuple[int, int]:

        pool = self._get_pool()

        xp = max(0, xp)

        new_level = math.floor(math.sqrt(xp / 10.0))

        query = """
            INSERT INTO UserXP (
                UserId,
                UserName,
                XP,
                Level
            )
            VALUES ($1, $2, $3, $4)

            ON CONFLICT (UserId)
            DO UPDATE SET
                UserName = EXCLUDED.UserName,
                XP = EXCLUDED.XP,
                Level = EXCLUDED.Level
        """

        async with pool.acquire() as connection:
            await connection.execute(query, user_id, username, xp, new_level)

        return xp, new_level

    # =========================================================
    # COMMANDS / HELP
    # =========================================================

    async def add_command(self, name: str, description: str) -> bool:

        pool = self._get_pool()

        query = """
            INSERT INTO Commands (
                Name,
                Description
            )
            VALUES ($1, $2)
            ON CONFLICT (Name) DO NOTHING
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name, description)

        return result != "INSERT 0 0"

    async def update_command(self, name: str, description: str) -> bool:

        pool = self._get_pool()

        query = """
            UPDATE Commands
            SET Description = $2
            WHERE Name = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name, description)

        return result != "UPDATE 0"

    async def delete_command(self, name: str) -> bool:

        pool = self._get_pool()

        query = """
            DELETE FROM Commands
            WHERE Name = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, name)

        return result != "DELETE 0"

    async def get_all_commands(self) -> list[tuple[str, str]]:

        pool = self._get_pool()

        query = """
            SELECT Name, Description
            FROM Commands
            ORDER BY Name
        """

        async with pool.acquire() as connection:
            rows = await connection.fetch(query)

        return [(row["name"], row["description"]) for row in rows]

    # =========================================================
    # TWITCH STREAMERS
    # =========================================================

    async def get_all_streamers(self) -> list[tuple[int, str, int]]:

        pool = self._get_pool()

        query = """
            SELECT
                DiscordUserId,
                TwitchUsername,
                LastLiveStatus
            FROM Streamers
        """

        async with pool.acquire() as connection:
            rows = await connection.fetch(query)

        return [
            (row["discorduserid"], row["twitchusername"], row["lastlivestatus"])
            for row in rows
        ]

    async def update_live_status(self, discord_user_id: int, is_live: bool) -> bool:

        pool = self._get_pool()

        query = """
            UPDATE Streamers
            SET LastLiveStatus = $2
            WHERE DiscordUserId = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(
                query, discord_user_id, 1 if is_live else 0
            )

        return result != "UPDATE 0"

    async def add_streamer(self, discord_id: int, twitch_name: str) -> bool:

        pool = self._get_pool()

        query = """
            INSERT INTO Streamers (
                DiscordUserId,
                TwitchUsername,
                LastLiveStatus
            )
            VALUES ($1, $2, 0)

            ON CONFLICT (DiscordUserId)
            DO NOTHING
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, discord_id, twitch_name)

        return result != "INSERT 0 0"

    async def delete_streamer(self, discord_id: int) -> bool:

        pool = self._get_pool()

        query = """
            DELETE FROM Streamers
            WHERE DiscordUserId = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, discord_id)

        return result != "DELETE 0"

    async def update_streamer(self, discord_id: int, new_twitch_name: str) -> bool:

        pool = self._get_pool()

        query = """
            UPDATE Streamers
            SET TwitchUsername = $2
            WHERE DiscordUserId = $1
        """

        async with pool.acquire() as connection:
            result = await connection.execute(query, discord_id, new_twitch_name)

        return result != "UPDATE 0"
