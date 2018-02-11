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


# cheetsheets https://www.pythonsheets.com/notes/python-asyncio.html
def recvfrom(loop, sock, n_bytes, fut=None, registed=False):
    fd = sock.fileno()
    if fut is None:
        fut = loop.create_future()
    if registed:
        loop.remove_reader(fd)

    try:
        data, addr = sock.recvfrom(n_bytes)
    except (BlockingIOError, InterruptedError):
        loop.add_reader(fd, recvfrom, loop, sock, n_bytes, fut, True)
    else:
        fut.set_result((data, addr))
    return fut

def sendto(loop, sock, data, addr, fut=None, registed=False):
    fd = sock.fileno()
    if fut is None:
        fut = loop.create_future()
    if registed:
        loop.remove_writer(fd)
    if not data:
        return

    try:
        n = sock.sendto(data, addr)
    except (BlockingIOError, InterruptedError):
        loop.add_writer(fd, sendto, loop, sock, data, addr, fut, True)
    else:
        fut.set_result(n)
    return fut

def host_status(packet, is_sokuroll=False):
    if packet == b'\x03':
        return 1
    else:
        return 0


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

        await self._delete_messages_from(hostlist_ch, user)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        message = await self.bot.send_message(hostlist_ch, "{0.mention}, {1}".format(user, host_message))
        await self.bot.whisper("募集を開始しました。")
        count = 0
        while(count <= 10):
            await sendto(self.bot.loop, sock, PACKET_TO_HOST, (ip, int(port)))
            await asyncio.sleep(3)
            data, _ = await recvfrom(self.bot.loop, sock, 1024)
            status = host_status(data)
            if status == 1:
                count = 0
                message = await self.bot.edit_message(message, "{0.mention}, :o: {1}".format(user, host_message))
            elif status == 0:
                count += 1
                message = await self.bot.edit_message(message, "{0.mention}, :x: {1}".format(user, host_message))
        await self._delete_messages_from(hostlist_ch, user)
        await self.bot.whisper("募集を終了しました。")
        sock.close()

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
