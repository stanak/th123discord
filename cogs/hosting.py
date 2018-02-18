from .cogmixin import CogMixin
from .common import errors

from discord.ext import commands
import discord

import unicodedata
import asyncio

import binascii
import socket
from datetime import (datetime, timedelta)
import logging

logger = logging.getLogger(__name__)

PACKET_TO_HOST = binascii.unhexlify(
    "056e7365" "d9ffc46e" "488d7ca1" "92313472"
    "95000000" "00280000" "00000000" "00000000"
    "00000000" "00000000" "00000000" "00000000"
    "00000000" "00000000" "00000000" "00000000" "00")
PACKET_TO_SOKUROLL = binascii.unhexlify(
    "05647365" "d9ffc46e" "488d7ca1" "92313472"
    "95000000" "00280000" "00000000" "00000000"
    "00000000" "00000000" "00000000" "00000000"
    "00000000" "00000000" "00000000" "00000000" "00")

WAIT = 2
BUF_SIZE = 256


def get_echo_packet(is_sokuroll=None):
    return PACKET_TO_SOKUROLL if is_sokuroll else PACKET_TO_HOST


class EchoClientProtocol:
    def __init__(self, bot, host_message, message, echo_packet):
        self.bot = bot
        self.loop = bot.loop
        self.host_message = host_message
        self.message = message
        self.echo_packet = echo_packet
        self.transport = None
        self.start_datetime = datetime.now()
        self.hosting = False
        self.matching = False
        self.watchable = False

        self.ack_datetime = datetime.now()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.update_host_status(data)
        if not self.hosting and not self.matching and not self.watchable:
            logger.error(data)

        if not self.hosting:
            return

        self.ack_datetime = datetime.now()

    def error_received(self, exc):
        pass

    def connection_lost(self, exc):
        pass

    def try_echo(self):
        _ = self.transport.sendto(self.echo_packet)

    def elapsed_time_from_ack(self):
        return datetime.now() - self.ack_datetime

    def update_host_status(self, packet):
        if packet.startswith(b'\x07\x01'):
            self.hosting = True
            self.matching = False
            self.watchable = True
        elif packet.startswith(b'\x07\x00'):
            self.hosting = True
            self.matching = False
            self.watchable = False
        elif packet.startswith(b'\x08\x01'):
            self.hosting = True
            self.matching = True
            self.watchable = self.watchable
        else:
            self.hosting = False
            self.matching = False
            self.watchable = False

    def get_host_message(self, ack_lost_threshold_time):
        if not self.hosting:
            return f":x: {self.host_message}"

        if self.elapsed_time_from_ack() >= ack_lost_threshold_time:
            return f":x: {self.host_message}"

        elapsed_seconds = (datetime.now() - self.start_datetime).seconds
        elapsed_time = f"{int(elapsed_seconds / 60)}m{elapsed_seconds % 60}s"
        return " ".join([
            ":crossed_swords:" if self.matching else ":o:",
            ":eye:" if self.watchable else ":see_no_evil:",
            elapsed_time,
            self.host_message])


class Hosting(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    def get_hostlist_ch(self):
        return discord.utils.get(self.bot.get_all_channels(), name="hostlist")

    @commands.command(pass_context=True)
    async def host(self, ctx, ip_port: str, *comment):
        """
        #holtlistに対戦募集を投稿します。
        約20秒間ホストが検知されなければ、自動で投稿を取り下げます。
        募集例「!host 123.456.xxx.xxx:10800 霊夢　レート1500　どなたでもどうぞ！」
        """
        user = ctx.message.author
        ip, port = unicodedata.normalize('NFKC', ip_port).split(":")
        try:
            int(port)
        except ValueError:
            raise commands.BadArgument
        ip_port_comments = f"{ip}:{port} |  {' '.join(comment)}"
        host_message = f"{user.mention}, {ip_port_comments}"

        not_private = not ctx.message.channel.is_private
        if not_private:
            await self.bot.delete_message(ctx.message)
            raise errors.OnlyPrivateMessage

        # 自分の投稿が残っていたら何もせず終了
        async for message in self.bot.logs_from(self.get_hostlist_ch()):
            if message.mentions and message.mentions[0] == user:
                return

        await self.bot.whisper("ホストの検知を開始します。")
        message = await self.bot.send_message(
            self.get_hostlist_ch(),
            host_message)

        connect = self.bot.loop.create_datagram_endpoint(
            lambda: EchoClientProtocol(
                self.bot,
                host_message,
                message,
                get_echo_packet(is_sokuroll=False)),
            remote_addr=(ip, int(port)))

        transport, protocol = await connect
        while True:
            protocol.try_echo()
            await asyncio.sleep(WAIT)
            elapsed_time = protocol.elapsed_time_from_ack()
            if elapsed_time >= timedelta(seconds=WAIT*10):
                break

            discord.compat.create_task(
                self.bot.edit_message(
                    protocol.message,
                    protocol.get_host_message(timedelta(seconds=WAIT))),
                loop=protocol.loop)
        transport.close()

        await self.bot.whisper(
            "一定時間ホストが検知されなかったため、"
            "募集を終了しました。")
        for i in range(100):
            try:
                await self._delete_messages_from(self.get_hostlist_ch(), user)
            except Exception as e:
                await asyncio.sleep(5)
                logger.exception(type(e).__name__, exc_info=e)
            else:
                return

    async def _delete_messages_from(
        self,
        channel: discord.Channel,
        user: discord.User
    ):
        async for message in self.bot.logs_from(channel):
            if message.mentions and message.mentions[0] == user:
                await self.bot.delete_message(message)
