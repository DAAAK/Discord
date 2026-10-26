import aiohttp


class TwitchService:

    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    STREAMS_URL = "https://api.twitch.tv/helix/streams"
    USERS_URL = "https://api.twitch.tv/helix/users"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
    ):
        self.client_id = client_id
        self.client_secret = client_secret

        self.access_token: str | None = None

    # =====================================================
    # TOKEN
    # =====================================================

    async def get_access_token(
        self,
        force_refresh: bool = False,
    ) -> str:

        if self.access_token and not force_refresh:
            return self.access_token

        async with aiohttp.ClientSession() as session:

            async with session.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            ) as response:

                if response.status != 200:

                    text = await response.text()

                    raise RuntimeError(
                        "Impossible de récupérer le token Twitch : "
                        f"{response.status} - {text}"
                    )

                data = await response.json()

                self.access_token = data["access_token"]

                return self.access_token

    # =====================================================
    # HEADERS
    # =====================================================

    async def get_headers(
        self,
    ) -> dict[str, str]:

        token = await self.get_access_token()

        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}",
        }

    # =====================================================
    # REQUEST
    # =====================================================

    async def _get(
        self,
        url: str,
        params: dict | None = None,
    ) -> dict:

        headers = await self.get_headers()

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                headers=headers,
                params=params,
            ) as response:

                # Token expiré / invalide
                if response.status == 401:

                    await self.get_access_token(force_refresh=True)

                    headers = await self.get_headers()

                    async with session.get(
                        url,
                        headers=headers,
                        params=params,
                    ) as retry_response:

                        if retry_response.status != 200:

                            text = await retry_response.text()

                            raise RuntimeError(
                                "Erreur Twitch API : "
                                f"{retry_response.status} "
                                f"- {text}"
                            )

                        return await retry_response.json()

                if response.status != 200:

                    text = await response.text()

                    raise RuntimeError(
                        "Erreur Twitch API : " f"{response.status} - {text}"
                    )

                return await response.json()

    # =====================================================
    # STREAM
    # =====================================================

    async def get_stream(
        self,
        username: str,
    ) -> dict | None:

        data = await self._get(
            self.STREAMS_URL,
            params={"user_login": username.lower()},
        )

        streams = data.get("data", [])

        if not streams:
            return None

        return streams[0]

    # =====================================================
    # USER
    # =====================================================

    async def get_user(
        self,
        username: str,
    ) -> dict | None:

        data = await self._get(
            self.USERS_URL,
            params={"login": username.lower()},
        )

        users = data.get("data", [])

        if not users:
            return None

        return users[0]

    # =====================================================
    # EXISTS
    # =====================================================

    async def user_exists(
        self,
        username: str,
    ) -> bool:

        user = await self.get_user(username)

        return user is not None
