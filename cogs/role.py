from .cogmixin import CogMixin
from discord.ext import commands
import discord
import logging

logger = logging.getLogger(__name__)


characters = [
    "reimu",
    "marisa",
    "sakuya",
    "youmu",
    "alice",
    "patchouli",
    "remilia",
    "yuyuko",
    "yukari",
    "suika",
    "reisen",
    "aya",
    "komachi",
    "iku",
    "sanae",
    "cirno",
    "meiling",
    "utsuho",
    "suwako",
    "tenshi"
]


class Role(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        pass_context=True
    )
    async def character(self, ctx):
        """
        使用キャラ表明の役職に関連するコマンドです。
        サブコマンドと合わせて使用します。
        setの使用例「!character set reimu」
        """
        pass

    @character.command(
        name="set",
        pass_context=True
    )
    async def set_character_roll(self, ctx, *roles: discord.Role):
        """
        役職を設定します。
        使用キャラを霊夢と魔理沙に設定する例「!character set reimu marisa」
        DMから利用不可。
        """
        user = ctx.message.author
        if not all([role.name in characters for role in roles]):
            raise commands.BadArgument
        await self.bot.add_roles(user, *roles)
        await self.bot.say("役職を追加しました。", delete_after=10)


    @character.command(
        name="unset",
        pass_context=True
    )
    async def unset_character_roll(self, ctx, *roles: discord.Role):
        """
        役職を解除します。
        使用キャラの霊夢を外す例「!character unset reimu」
        DMから利用不可。
        """
        user = ctx.message.author
        if not all([role.name in characters for role in roles]):
            raise commands.BadArgument
        await self.bot.remove_roles(user, *roles)
        await self.bot.say("役職を解除しました。", delete_after=10)
