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


class Lifetime:
    def __init__(self, lifetime):
        self.lifetime = lifetime
        self.reset()

    def reset(self):
        self.ack_datetime = datetime.now()

    def elapsed_datetime(self):
        return datetime.now() - self.ack_datetime

    def is_expired(self):
        return self.elapsed_datetime() >= self.lifetime


class HostStatus:
    def __init__(self):
        self.reset()

    def reset(self):
        self.hosting = False
        self.matching = False
        self.watchable = False

    def __call__(self, packet):
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
            self.reset()

    def is_unknown(self):
        return (
            not self.hosting and
            not self.matching and
            not self.watchable)

    def __str__(self):
        if self.is_unknown():
            return ":question:"

        return " ".join([
            ":crossed_swords:" if self.matching else ":o:",
            ":eye:" if self.watchable else ":see_no_evil:"])


class Th123DatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self, lifetime, ack_lifetime):
        self.lifetime = lifetime
        self.ack_lifetime = ack_lifetime

    def try_echo(self):
        pass

    def discard(self):
        pass


class Th123HostProtocol(Th123DatagramProtocol):
    def __init__(self, echo_packet, *, lifetime=None, ack_lifetime=None):
        super().__init__(
            lifetime or Lifetime(timedelta(seconds=20)),
            ack_lifetime or Lifetime(timedelta(seconds=6)))
        self.echo_packet = echo_packet

        self.transport = None
        self.host_status = HostStatus()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.ack_lifetime.reset()
        self.host_status(data)

        if self.host_status.is_unknown():
            logger.error(data)
            return

        self.lifetime.reset()

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

    def discard(self):
        if self.transport and not self.transport.is_closing():
            self.transport.close()


class Th123ClientProtocol(Th123DatagramProtocol):
    def __init__(self, *, lifetime=None):
        super().__init__(
            lifetime or Lifetime(timedelta(hours=1)),
            Lifetime(timedelta()))


class PostAsset:
    def get_message_body(self):
        raise NotImplementedError

    def get_close_message(self):
        raise NotImplementedError

    def should_close(self):
        raise NotImplementedError

    def terminate(self):
        raise NotImplementedError


class HostPostAsset(PostAsset):
    def __init__(self, user, message_body, protocol):
        self.user = user
        self.message_body = message_body
        self.protocol = protocol
        self.terminates = False

        self.start_datetime = datetime.now()

    def get_message_body(self):
        if self.protocol.ack_lifetime.is_expired():
            return f":x: {self.message_body}"

        elapsed_seconds = (datetime.now() - self.start_datetime).seconds
        elapsed_time = f"{int(elapsed_seconds / 60)}m{elapsed_seconds % 60}s"
        return " ".join([
            str(self.protocol.host_status),
            elapsed_time,
            self.message_body])

    def get_close_message(self):
        if self.terminates:
            return str()
        return "一定時間ホストが検知されなかったため、募集を終了します。"

    def should_close(self):
        return self.terminates or self.protocol.lifetime.is_expired()

    def terminate(self):
        self.terminates = True
        self.protocol.discard()


class ClientPostAsset(PostAsset):
    def __init__(self, user, message_body, protocol):
        self.user = user
        self.message_body = message_body
        self.protocol = protocol
        self.terminates = False

        self.start_datetime = datetime.now()

    def get_message_body(self):
        elapsed_seconds = (datetime.now() - self.start_datetime).seconds
        elapsed_time = f"{int(elapsed_seconds / 60)}m{elapsed_seconds % 60}s"
        return " ".join([
            ":loudspeaker:",
            elapsed_time,
            self.message_body])

    def get_close_message(self):
        if self.terminates:
            return str()
        return "投稿から一定時間経過したため、募集を終了します。"

    def should_close(self):
        return self.terminates or self.protocol.lifetime.is_expired()

    def terminate(self):
        self.terminates = True
        self.protocol.discard()


class HostListObserver:
    _bot = None
    _host_list = []

    @classmethod
    async def update_hostlist(cls, bot, interval=timedelta(seconds=2)):
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

                await asyncio.sleep(interval.seconds)

                message_body_list = list()
                for host in host_list:
                    if host.should_close():
                        await cls.close(host)
                        continue

                    message_body_list.append(host.get_message_body())

                post_message = (
                    base_message.format(len(message_body_list)) +
                    "\n".join(message_body_list))
                await cls._bot.edit_message(message, post_message)
            except Exception as e:
                logger.exception(type(e).__name__, exc_info=e)

    @classmethod
    async def close(cls, host):
        close_message = host.get_close_message()
        if close_message:
            await cls._bot.send_message(host.user, close_message)

        cls._remove(host)
        host.terminate()

    @classmethod
    async def append(cls, host):
        cls._host_list.append(host)
        message = await cls._bot.send_message(
            get_hostlist_ch(cls._bot),
            ".")
        await cls._bot.delete_message(message)

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
        await self.invite_as_host(user, ip_port, comment, sokuroll_uses=False)

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
        await self.invite_as_host(user, ip_port, comment, sokuroll_uses=True)

    async def invite_as_host(self, user, ip_port, comment, *, sokuroll_uses):
        try:
            ip, port = unicodedata.normalize('NFKC', ip_port).split(":", 1)
            ip = ipv4(ip)
            port = int(port)
            if port not in range(0x0000, 0xffff):
                raise ValueError
        except ValueError:
            raise commands.BadArgument

        message_body = " ".join([
            ":regional_indicator_r:" if sokuroll_uses else "",
            f"{user.mention},",
            f"{ip.exploded}:{port} | {' '.join(comment)}"]).strip()

        await self.bot.whisper("ホストの検知を開始します。")
        connect = self.bot.loop.create_datagram_endpoint(
            lambda: Th123HostProtocol(get_echo_packet(sokuroll_uses)),
            remote_addr=(ip.exploded, port))
        _, protocol = await connect
        host = HostPostAsset(user, message_body, protocol)
        await HostListObserver.append(host)

    @checks.only_private()
    @commands.command(pass_context=True)
    async def client(self, ctx, *comment):
        """
        #holtlistにホスト検知を行わない対戦募集を投稿します。
        投稿から60分経過するか、closeコマンドで、投稿を取り下げます。
        募集例「!client 霊夢　レート1500　どなたでもどうぞ！」
        """
        if self.observer is None:
            self.observer = discord.compat.create_task(
                HostListObserver.update_hostlist(self.bot))

        user = ctx.message.author
        message_body = f"{user.mention}, {' '.join(comment)}"

        await self.bot.whisper("対戦募集を投稿します。")
        protocol = Th123ClientProtocol()
        host = ClientPostAsset(user, message_body, protocol)
        await HostListObserver.append(host)

    @checks.only_private()
    @commands.command(pass_context=True)
    async def close(self, ctx):
        """
        #hostlistへの投稿を取り下げます。
        """
        await self.bot.whisper("対戦相手の募集を取り下げます。")
        user = ctx.message.author
        HostListObserver.terminate(user=user)
