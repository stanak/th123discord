from .cogmixin import CogMixin
from .common import errors

from discord.ext import commands
import discord

import unicodedata
import asyncio

import binascii
import socket
import datetime
import logging

logger = logging.getLogger(__name__)

_HOST_MESSAGE_SEC = 3600
_DEFAULT_MESSAGE_SEC = 60
_SHORT_MESSAGE_SEC = 10

PACKET_TO_HOST = binascii.unhexlify("056e7365d9ffc46e488d7ca19231347295000000002800000000000000000000000000000000000000000000000000000000000000000000000000000000000000")
PACKET_TO_SOKUROLL = binascii.unhexlify("05647365d9ffc46e488d7ca19231347295000000002800000000000000000000000000000000000000000000000000000000000000000000000000000000000000")

WAIT = 2
BUF_SIZE = 256

class EchoClientProtocol:
    def __init__(self, bot, host_message, message):
        self.bot = bot
        self.loop = bot.loop
        self.host_message = host_message
        self.message = message
        self.transport = None
        self.count = 0
        self.start_date = datetime.datetime.now()
        self.watchable = False

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        status = host_status(data)
        now = datetime.datetime.now()
        seconds = (now - self.start_date).seconds
        time = "{0}m{1}s ".format(int(seconds/60), seconds%60)

        if status == (True, False, True):
            self.count = 0
            self.watchable = True
            status_time_host_message = ":o: :eye: " + (time) + self.host_message
            discord.compat.create_task(self.bot.edit_message(self.message, status_time_host_message), loop=self.loop)
        elif status == (True, False, False):
            self.count = 0
            self.watchable = False
            status_time_host_message = ":o: " + (time) + self.host_message
            discord.compat.create_task(self.bot.edit_message(self.message, status_time_host_message), loop=self.loop)
        elif status == (True, True, False):
            status = ":crossed_swords: "
            if self.watchable:
                status += ":eye: "
            self.count = 0
            status_time_host_message = status + (time) + self.host_message
            discord.compat.create_task(self.bot.edit_message(self.message, status_time_host_message), loop=self.loop)
        else:
            pass

    def error_received(self, exc):
        self.count += 1

    def connection_lost(self, exc):
        pass


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
        募集例「!host 123.456.xxx.xxx:10800 霊夢　レート1500　どなたでもどうぞ！」
        """
        normalized_host = unicodedata.normalize('NFKC', ip_port)
        ip, port = normalized_host.split(":")
        user = ctx.message.author
        ip_port_comments = normalized_host + " | " + " ".join(comment)
        host_message = "{0.mention}, {1}".format(user, ip_port_comments)
        hostlist_ch = discord.utils.get(self.bot.get_all_channels(),
                                           name="hostlist")
        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage

        # 自分の投稿が残っていたら何もせず終了
        async for message in self.bot.logs_from(hostlist_ch):
            if message.mentions and message.mentions[0] == user:
                return

        await self.bot.whisper("ホストの検知を開始します。")
        message = await self.bot.send_message(hostlist_ch, host_message)

        await self._hosting((ip, int(port)), host_message, message, is_sokuroll=False)

        await self.bot.whisper("一定時間ホストが検知されなかったため、募集を終了しました。")

        for i in range(100):
            try:
                await self._delete_messages_from(hostlist_ch, user)
            except Exception as e:
                await asyncio.sleep(5)
                logger.exception(type(e).__name__, exc_info=e)
            else:
                return

    @commands.command(pass_context=True)
    async def rhost(self, ctx, ip_port: str, *comment):
        """
        #holtlistにsokuroll有の対戦募集を投稿します。
        募集例「!host 123.456.xxx.xxx:10800 霊夢　レート1500　どなたでもどうぞ！」
        """
        normalized_host = unicodedata.normalize('NFKC', ip_port)
        ip, port = normalized_host.split(":")
        user = ctx.message.author
        ip_port_comments = normalized_host + " | " + " ".join(comment)
        host_message = "{0.mention}, {1}".format(user, ip_port_comments)
        hostlist_ch = discord.utils.get(self.bot.get_all_channels(),
                                           name="hostlist")

        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage

        # 自分の投稿が残っていたら何もせず終了
        async for message in self.bot.logs_from(hostlist_ch):
            if message.mentions and message.mentions[0] == user:
                return

        await self.bot.whisper("ホストの検知を開始します。")
        message = await self.bot.send_message(hostlist_ch, host_message)

        await self._hosting((ip, int(port)), ":regional_indicator_r: " + host_message, message, is_sokuroll=True)

        await self.bot.whisper("一定時間ホストが検知されなかったため、募集を終了しました。")

        for i in range(100):
            try:
                await self._delete_messages_from(hostlist_ch, user)
            except Exception as e:
                await asyncio.sleep(5)
                logger.exception(type(e).__name__, exc_info=e)
            else:
                return

    async def _hosting(self, addr, host_message, message, is_sokuroll):
        if is_sokuroll:
            send_data = PACKET_TO_SOKUROLL
        else:
            send_data = PACKET_TO_HOST
        connect = self.bot.loop.create_datagram_endpoint(
            lambda: EchoClientProtocol(self.bot, host_message, message),
            remote_addr=addr
        )
        transport, protocol = await connect
        while protocol.count <= 10:
            n_bytes = transport.sendto(send_data)
            await asyncio.sleep(WAIT)
            if protocol.count > 1:
                protocol.start_date = datetime.datetime.now()
                status_host_message = ":x: " + protocol.host_message
                discord.compat.create_task(self.bot.edit_message(protocol.message, status_host_message), loop=protocol.loop)
            protocol.count += 1
        transport.close()

    async def _delete_messages_from(self, channel: discord.Channel, user: discord.User):
        async for message in self.bot.logs_from(channel):
            if message.mentions and message.mentions[0] == user:
                await self.bot.delete_message(message)
