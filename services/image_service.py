from io import BytesIO
from pathlib import Path
import tempfile
import uuid

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

import discord


class ImageService:

    def __init__(self):
        self.assets_path = Path(__file__).resolve().parent.parent / "assets"

    # =====================================================
    # FONTS
    # =====================================================

    @staticmethod
    def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:

        candidates = []

        if bold:
            candidates.extend(
                [
                    "C:/Windows/Fonts/seguisb.ttf",
                    "C:/Windows/Fonts/arialbd.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
            )
        else:
            candidates.extend(
                [
                    "C:/Windows/Fonts/segoeui.ttf",
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                ]
            )

        for path in candidates:
            if Path(path).exists():
                return ImageFont.truetype(path, size)

        return ImageFont.load_default()

    # =====================================================
    # AVATAR
    # =====================================================

    @staticmethod
    async def download_avatar(user: discord.User | discord.Member) -> Image.Image:

        avatar_url = user.display_avatar.replace(size=256, format="png").url

        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as response:

                response.raise_for_status()

                data = await response.read()

        image = Image.open(BytesIO(data)).convert("RGBA")

        return image

    # =====================================================
    # RANK CARD
    # =====================================================

    async def generate_rank_card(
        self,
        user: discord.User | discord.Member,
        display_name: str,
        status: discord.Status,
        level: int,
        rank: int,
        current_xp: int,
        next_level_xp: int,
    ) -> Path:

        background_path = self.assets_path / "rank.jpg"

        if not background_path.exists():
            raise FileNotFoundError(f"Image introuvable : " f"{background_path}")

        background = Image.open(background_path).convert("RGBA")

        width = background.width
        height = max(1, background.height - 200)

        # Equivalent ResizeMode.Crop + Center
        background = ImageOps.fit(
            background,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

        canvas = background.copy()

        # =================================================
        # OVERLAY NOIR
        # =================================================

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))

        overlay_pixels = overlay.load()

        gradient_width = int(width * 0.75)

        for x in range(gradient_width):

            progress = x / max(1, gradient_width)

            alpha = int(140 * (1 - progress))

            for y in range(height):
                overlay_pixels[x, y] = (0, 0, 0, alpha)

        canvas = Image.alpha_composite(canvas, overlay)

        draw = ImageDraw.Draw(canvas)

        # =================================================
        # DIMENSIONS
        # =================================================

        margin = 40
        avatar_size = 150

        bar_width = 500
        bar_height = 28

        base_y = height // 2 - avatar_size // 2

        # =================================================
        # AVATAR
        # =================================================

        avatar = await self.download_avatar(user)

        avatar = ImageOps.fit(
            avatar, (avatar_size, avatar_size), method=Image.Resampling.LANCZOS
        )

        mask = Image.new("L", (avatar_size, avatar_size), 0)

        mask_draw = ImageDraw.Draw(mask)

        mask_draw.ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)

        avatar_x = margin
        avatar_y = base_y

        canvas.paste(avatar, (avatar_x, avatar_y), mask)

        # Bordure avatar
        draw.ellipse(
            (avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size),
            outline="white",
            width=4,
        )

        # =================================================
        # STATUS
        # =================================================

        status_colors = {
            discord.Status.online: (67, 181, 129),
            discord.Status.idle: (250, 166, 26),
            discord.Status.dnd: (240, 71, 71),
            discord.Status.offline: (116, 127, 141),
        }

        status_color = status_colors.get(status, (116, 127, 141))

        dot_size = 28

        dot_x = avatar_x + avatar_size - 50

        dot_y = avatar_y + avatar_size - dot_size + 10

        draw.ellipse(
            (dot_x, dot_y, dot_x + dot_size, dot_y + dot_size),
            fill=status_color,
            outline="black",
            width=2,
        )

        # =================================================
        # TEXT
        # =================================================

        text_x = avatar_x + avatar_size + 40

        name_y = base_y
        rank_y = name_y + 50
        bar_y = rank_y + 60

        username_font = self.get_font(36, bold=True)

        small_font = self.get_font(20)

        safe_display_name = (
            display_name[:20] + "..." if len(display_name) > 20 else display_name
        )

        # Nom
        draw.text((text_x, name_y), safe_display_name, font=username_font, fill="white")

        # Rank
        draw.text((text_x, rank_y), f"RANK #{rank}", font=small_font, fill="white")

        # Level
        draw.text(
            (text_x + 250, rank_y),
            f"LEVEL {level}",
            font=small_font,
            fill=(255, 80, 80),
        )

        # =================================================
        # XP BAR
        # =================================================

        percent = current_xp / next_level_xp if next_level_xp > 0 else 0

        percent = max(0, min(percent, 1))

        filled_width = int(bar_width * percent)

        # Ombre
        draw.rounded_rectangle(
            (text_x + 2, bar_y + 2, text_x + bar_width + 2, bar_y + bar_height + 2),
            radius=bar_height // 2,
            fill=(0, 0, 0, 100),
        )

        # Fond
        draw.rounded_rectangle(
            (text_x, bar_y, text_x + bar_width, bar_y + bar_height),
            radius=bar_height // 2,
            fill=(60, 60, 60),
            outline="black",
            width=2,
        )

        # Progression
        if filled_width > 0:

            draw.rounded_rectangle(
                (text_x, bar_y, text_x + filled_width, bar_y + bar_height),
                radius=bar_height // 2,
                fill=(144, 238, 144),
            )

        # XP
        draw.text(
            (text_x, bar_y + 32),
            (f"{current_xp:,} / " f"{next_level_xp:,} XP"),
            font=small_font,
            fill="white",
        )

        # =================================================
        # SAVE
        # =================================================

        temp_path = Path(tempfile.gettempdir()) / f"rank_{user.id}_{uuid.uuid4()}.png"

        canvas.convert("RGB").save(temp_path, "PNG")

        return temp_path
