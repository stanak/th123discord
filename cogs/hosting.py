from .cogmixin import CogMixin
from .common import errors

from discord.ext import commands
import discord
import unicodedata
import asyncio
import struct
import socket

import logging

logger = logging.getLogger(__name__)


s = struct.Struct("!"+"B"*37)
binary_data = [0x01, 0x02, 0x00, 0x2a, 0x30, 0x8c,
        0x71, 0x3e, 0xeb, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x2a, 0x30, 0x8c,
        0x71, 0x3e, 0xeb, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x77, 0xbc]
PACKET_TO_HOST = s.pack(*binary_data)

WAIT = 3
BUF_SIZE = 256


def host_status(packet, is_sokuroll=False):
    if packet == b'\x03':
        return (True, False, False)
    else:
        return (False, False, False)


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
        ip, port = normalized_host.split(":")
        host_message = normalized_host + " | " + " ".join(comment)
        user = ctx.message.author
        hostlist_ch = discord.utils.get(self.bot.get_all_channels(),
                                           name="hostlist")

        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage

        # ソケットのノンブロッキング設定
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        fd = sock.fileno()
        self.bot.loop.add_writer(fd, lambda x=1:1)  # callback捨てる
        self.bot.loop.add_reader(fd, lambda x=1:1)

        await self._delete_messages_from(hostlist_ch, user)
        message = await self.bot.send_message(hostlist_ch, "{0.mention}, {1}".format(user, host_message))
        await self.bot.whisper("募集を開始しました。")

        count = 0
        while count <= WAIT*10:
            n_bytes = sock.sendto(PACKET_TO_HOST, (ip, int(port)))
            await asyncio.sleep(WAIT)
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
            except (BlockingIOError, InterruptedError):
                data = ""

            status = host_status(data)
            if status == (True, False, False):
                count = 0
                message = await self.bot.edit_message(message, "{0.mention}, :o: {1}".format(user, host_message))
            elif status == (True, True, False):
                count = 0
                message = await self.bot.edit_message(message, "{0.mention}, :crossed_swords: {1}".format(user, host_message))
            elif status == (False, False, False):
                count += 1
                message = await self.bot.edit_message(message, "{0.mention}, :x: {1}".format(user, host_message))

        await self._delete_messages_from(hostlist_ch, user)
        await self.bot.whisper("募集を終了しました。")
        self.bot.loop.remove_reader(fd)
        self.bot.loop.remove_writer(fd)
        sock.close()

    async def _delete_messages_from(self, channel: discord.Channel, user: discord.User):
        async for message in self.bot.logs_from(channel):
            if message.mentions and message.mentions[0] == user:
                await self.bot.delete_message(message)
