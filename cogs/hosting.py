from .cogmixin import CogMixin
from .common import errors

from discord.ext import commands
import discord
import unicodedata
import asyncio
import binascii
import socket

import logging

logger = logging.getLogger(__name__)


PACKET_TO_HOST=[
    binascii.unhexlify("056e7365d9ffc46e488d7ca19231347295000000002800000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
    binascii.unhexlify("05647365d9ffc46e488d7ca19231347295000000002800000000000000000000000000000000000000000000000000000000000000000000000000000000000000")
]
WAIT = 3
BUF_SIZE = 256


# hosting, matching, watchable
def host_status(packet):
    if packet.startswith(b'\x07\x01'):
        return True, False, True
    elif packet.startswith(b'\x07\x00'):
        return True, False, False
    elif packet.startswith(b'\x08\x01'):
        return True, True, False
    else:
        return False, False, False

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
        await self._host_impl(ctx, ip_port, comment)

    @commands.command(pass_context=True)
    async def rhost(self, ctx, ip_port: str, *comment):
        await self._host_impl(ctx, ip_port, comment, True)

    async def _host_impl(self, ctx, ip_port: str, *comment, is_sokuroll=False):
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
            n_bytes = sock.sendto(PACKET_TO_HOST[is_sokuroll], (ip, int(port)))
            await asyncio.sleep(WAIT)
            try:
                packet, _ = sock.recvfrom(BUF_SIZE)
            except (BlockingIOError, InterruptedError):
                packet = b""

            status = host_status(packet)
            if status == (True, False, True):
                count = 0
                message = await self.bot.edit_message(message, "{0.mention}, :o: :eye: {1}".format(user, host_message))
            elif status == (True, False, False):
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
