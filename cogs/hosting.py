from .cogmixin import CogMixin
from .common import errors

from discord.ext import commands
import discord
import unicodedata
import asyncio

import logging

logger = logging.getLogger(__name__)

_HOST_MESSAGE_SEC = 3600
_DEFAULT_MESSAGE_SEC = 60
_SHORT_MESSAGE_SEC = 10


class Hosting(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def host(self, ctx, ip_port: str, *comment):
        """
        #holtlistに対戦募集を投稿します。
        投稿は60分経過か、closeで消去されます。
        もう一度呼ぶと古い投稿は削除され、新しい内容が投稿されます。
        募集例「!host 123.456.xxx.xxx:10800 霊夢　レート1500　どなたでもどうぞ！」
        """
        normalized_host = unicodedata.normalize('NFKC', ip_port)
        host_message = normalized_host + " | " + " ".join(comment)
        user = ctx.message.author
        hostlist_ch = discord.utils.get(self.bot.get_all_channels(),
                                           name="hostlist")
        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage

        await self._delete_messages_from(hostlist_ch, user)
        await self.bot.post(hostlist_ch, "{0.mention}, {1}".format(user, host_message), delete_after=_HOST_MESSAGE_SEC)
        await self.bot.whisper("募集を開始しました。")

    @commands.command(pass_context=True)
    async def client(self, ctx, *comment):
        """
        #hostlistに募集を投稿するクライアント専用コマンドです。
        投稿は60分経過か、closeで消去されます。
        もう一度呼ぶと古い投稿は削除され、新しい内容が投稿されます。
        募集例「!client 霊夢　レート1500　どなたでもどうぞ！」
        """
        host_message = "クラ専。DMかメンションでIPをお願いします。" + " | " + " ".join(comment)
        user = ctx.message.author
        hostlist_ch = discord.utils.get(self.bot.get_all_channels(),
                                           name="hostlist")
        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage

        await self._delete_messages_from(hostlist_ch, user)
        await self.bot.post(hostlist_ch, "{0.mention}, {1}".format(user, host_message), delete_after=_HOST_MESSAGE_SEC)
        await self.bot.whisper("クラ専募集を開始しました。")

    @commands.command(pass_context=True)
    async def close(self, ctx):
        """
        host,clientコマンドで投稿した内容を消去します。
        """
        user = ctx.message.author
        hostlist_ch = discord.utils.get(self.bot.get_all_channels(),
                                           name="hostlist")
        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage
        await self._delete_messages_from(hostlist_ch, user)
        await self.bot.whisper("募集を締め切りました。")

    async def _delete_messages_from(self, channel: discord.Channel, user: discord.User):
        async for message in self.bot.logs_from(channel):
            if message.mentions and message.mentions[0] == user:
                await self.bot.delete_message(message)
