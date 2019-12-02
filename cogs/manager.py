from .cogmixin import CogMixin
from .common import checks
import discord
from discord.ext import commands


class Manager(CogMixin, commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="shanghai",
    )
    @checks.is_manager()
    async def _speak_as_shanghai(self, ctx,
                                 channel: discord.TextChannel, *, messages):
        """
        特定のチャンネルに上海botがメッセージを送ります。
        アナウンスの例「!shanghai #announcements botを更新しました。」
        """
        joined_message = "".join(messages)
        await channel.send(joined_message)
