from .cogmixin import CogMixin
from .common import errors, checks

from discord.ext import commands
import discord

import unicodedata
import asyncio

import binascii
from datetime import (datetime, timedelta)
from ipaddress import IPv4Address as ipv4
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


def get_echo_packet(is_sokuroll=None):
    return PACKET_TO_SOKUROLL if is_sokuroll else PACKET_TO_HOST


def get_hostlist_ch(bot):
    return discord.utils.get(bot.get_all_channels(), name="hostlist")


class HostStatus:
    def __init__(self):
        self.hosting = False
        self.matching = False
        self.watchable = False

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

    def is_unknown(self):
        return (
            not self.hosting and
            not self.matching and
            not self.watchable)


class EchoClientProtocol:
    def __init__(self, echo_packet, lifetime=timedelta(seconds=20)):
        self.echo_packet = echo_packet
        self.lifetime = lifetime
        self.transport = None
        self.host_status = HostStatus()
        self.ack_datetime = datetime.now()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.host_status.update_host_status(data)
        if self.host_status.is_unknown():
            logger.error(data)

        if not self.host_status.hosting:
            return

        self.ack_datetime = datetime.now()

    def error_received(self, exc):
        pass

    def connection_lost(self, exc):
        pass

    def try_echo(self):
        try:
            self.transport.sendto(self.echo_packet)
        except Exception as e:
            logger.exception(type(e).__name__, exc_info=e)
            self.transport.sendto(self.echo_packet)

    def elapsed_time_from_ack(self):
        return datetime.now() - self.ack_datetime

    def is_expired(self):
        return self.elapsed_time_from_ack() >= self.lifetime


class HostPostAsset:
    def __init__(self, user, host_message, protocol):
        self.user = user
        self.host_message = host_message
        self.protocol = protocol
        self.terminates = False

        self.start_datetime = datetime.now()

    def get_host_message(self, ack_loses):
        host_status = self.protocol.host_status
        if ack_loses or not host_status.hosting:
            return f":x: {self.host_message}"

        elapsed_seconds = (datetime.now() - self.start_datetime).seconds
        elapsed_time = f"{int(elapsed_seconds / 60)}m{elapsed_seconds % 60}s"
        return " ".join([
            ":crossed_swords:" if host_status.matching else ":o:",
            ":eye:" if host_status.watchable else ":see_no_evil:",
            elapsed_time,
            self.host_message])

    def get_close_message(self):
        if self.terminates:
            return str()
        return "一定時間ホストが検知されなかったため、募集を終了します。"

    def should_close(self):
        return self.terminates or self.protocol.is_expired()

    def terminate(self):
        self.terminates = True


class HostListObserver:
    WAIT = timedelta(seconds=2)

    _bot = None
    _host_list = []

    @classmethod
    async def update_hostlist(cls, bot):
        cls._bot = bot

        base_message = "**{}人が対戦相手を募集しています:**\n"
        message = await cls._bot.send_message(
            get_hostlist_ch(cls._bot),
            base_message.format(0))

        while True:
            try:
                host_list = cls._host_list[:]
                for host in host_list:
                    host.protocol.try_echo()

                await asyncio.sleep(cls.WAIT.seconds)

                host_messages = list()
                for host in host_list:
                    elapsed_time = host.protocol.elapsed_time_from_ack()
                    if host.should_close():
                        await cls.close(host)
                        continue

                    ack_loses = elapsed_time >= (cls.WAIT * 3)
                    host_messages.append(host.get_host_message(ack_loses))

                post_message = (
                    base_message.format(len(host_messages)) +
                    "\n".join(host_messages))
                await cls._bot.edit_message(message, post_message)
            except Exception as e:
                logger.exception(type(e).__name__, exc_info=e)

    @classmethod
    async def close(cls, host):
        close_message = host.get_close_message()
        if close_message:
            await cls._bot.send_message(host.user, close_message)

        cls._remove(host)
        host.protocol.transport.close()

    @classmethod
    def append(cls, host):
        cls._host_list.append(host)

    @classmethod
    def terminate(cls, *, user):
        target_posts = [host for host in cls._host_list if host.user == user]
        for post in target_posts:
            post.terminate()

    @classmethod
    def _remove(cls, host):
        cls._host_list.remove(host)


class Hosting(CogMixin):
    def __init__(self, bot):
        self.bot = bot
        self.observer = None

    @checks.only_private()
    @commands.command(pass_context=True)
    async def host(self, ctx, ip_port: str, *comment):
        """
        #holtlistに対戦募集を投稿します。
        約20秒間ホストが検知されなければ、自動で投稿を取り下げます。
        募集例「!host 198.51.100.123:10800 霊夢　レート1500　どなたでもどうぞ！」
        """
        if self.observer is None:
            self.observer = discord.compat.create_task(
                HostListObserver.update_hostlist(self.bot))

        user = ctx.message.author
        try:
            ip, port = unicodedata.normalize('NFKC', ip_port).split(":", 1)
            ip = ipv4(ip)
            port = int(port)
            if port > 65535:
                raise ValueError
        except ValueError:
            raise commands.BadArgument
        ip_port_comments = f"{ip.exploded}:{port} | {' '.join(comment)}"
        host_message = f"{user.mention}, {ip_port_comments}"

        await self.bot.whisper("ホストの検知を開始します。")
        connect = self.bot.loop.create_datagram_endpoint(
            lambda: EchoClientProtocol(get_echo_packet(is_sokuroll=False)),
            remote_addr=(ip.exploded, port))
        _, protocol = await connect
        host = HostPostAsset(user, host_message, protocol)
        HostListObserver.append(host)

    @checks.only_private()
    @commands.command(pass_context=True)
    async def rhost(self, ctx, ip_port: str, *comment):
        """
        #holtlistにsokuroll有りの対戦募集を投稿します。
        約20秒間ホストが検知されなければ、自動で投稿を取り下げます。
        募集例「!rhost 198.51.100.123:10800 霊夢　レート1500　どなたでもどうぞ！」
        """
        if self.observer is None:
            self.observer = discord.compat.create_task(
                HostListObserver.update_hostlist(self.bot))

        user = ctx.message.author
        try:
            ip, port = unicodedata.normalize('NFKC', ip_port).split(":", 1)
            ip = ipv4(ip)
            port = int(port)
            if port > 65535:
                raise ValueError
        except ValueError:
            raise commands.BadArgument
        ip_port_comments = f"{ip.exploded}:{port} | {' '.join(comment)}"
        sokuroll_icon = ":regional_indicator_r:"
        host_message = f"{sokuroll_icon} {user.mention}, {ip_port_comments}"

        await self.bot.whisper("ホストの検知を開始します。")
        connect = self.bot.loop.create_datagram_endpoint(
            lambda: EchoClientProtocol(get_echo_packet(is_sokuroll=True)),
            remote_addr=(ip.exploded, port))
        _, protocol = await connect
        host = HostPostAsset(user, host_message, protocol)
        HostListObserver.append(host)

    @checks.only_private()
    @commands.command(pass_context=True)
    async def close(self, ctx):
        """
        #hostlistへの投稿を取り下げます。
        """
        await self.bot.whisper("対戦相手の募集を取り下げます。")
        user = ctx.message.author
        HostListObserver.terminate(user=user)
