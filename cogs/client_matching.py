from .cogmixin import CogMixin
from .common.networks import (Lifetime, IpPort)
import discord
from discord.ext import commands

import socket
import binascii
import asyncio
from datetime import (datetime, timedelta)
import os
import logging

logger = logging.getLogger(__name__)


def get_client_ch(bot):
    return discord.utils.get(bot.get_all_channels(), name="client")


class Th123Packet(object):
    def __init__(self, raw):
        self.raw = raw
        self.ipport = None
        self.matching_flag = None
        self.profile_length = None
        self.profile_name = None
        self.header = raw[0]
        if self.is_(1):
            self.ipport = IpPort.create_with_bin(raw[3:9])
        elif self.is_(5):
            self.matching_flag = raw[25]
            self.profile_length = raw[26]
            self.profile_name = raw[27: 27+self.profile_length].decode("shift-jis")

    def is_(self, b):
        return self.header == b

    def __str__(self):
        return (f"ipport: {self.ipport}\n"
                f"flag: {self.matching_flag}\n"
                f"plength: {self.profile_length}\n"
                f"profile_name: {self.profile_name}\n"
                f"raw: {binascii.hexlify(self.raw)}\n"
                )


packet_03 = binascii.unhexlify("03")
packet_06 = binascii.unhexlify(
    "06000000" "00100000" "00440000" "00"
    "5368616e" "67686169" "00000000" "00000000" "00000000" "00000000" "00"
    "00000000" "000000"
    "00000000" "00000000" "00000000" "00000000" "00000000" "00000000" "00"
    "00000000" "00000000" "000000"
)

packet_07 = binascii.unhexlify(
    "0700" "000000"
)

# host to client
packet_0d_sp = binascii.unhexlify("0d0203")
packet_0d_parts = [binascii.unhexlify(p) for p in ["0d03", "030200000000"]]


def get_packet_0d(ack):
    return packet_0d_parts[0]+(ack).to_bytes(4, byteorder='little')+packet_0d_parts[1]


def get_ack(data):
    return int.from_bytes(data, 'little')


# host to watcher
def get_packet_08(port_ip: bytes) -> bytes:
    return bytes.fromhex(
        "08010000" "000200"
        f"{port_ip.hex()}" "00000000" "00000000"
        "70000000" "0000060c" "00000000" "00100000" "00000000" "00010e03"
        "97ce0010" "10101010" "10000000" "010d0905" "0e010000" "00100000"
    )


def get_packet_02(port_ip: bytes) -> bytes:
    return bytes.fromhex(
        "020200" f"{port_ip.hex()}" "00000000" "00000000" "00000000"
    )


class Th123HolePunchingProtocol:
    def __init__(self):
        self.initialize()

    def initialize(self):
        self.client_addr = None
        self.watcher_addr = None
        self.profile_name = None
        self.ack_datetime = Lifetime(timedelta(seconds=3))
        self.punched_flag = None

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def datagram_received(self, data, addr):
        packet = Th123Packet(data)
        self.ack_datetime.reset()
        if packet.is_(1):
            if self.watcher_addr is None:
                self.transport.sendto(packet_03, addr)
            else:
                self.transport.sendto(
                    get_packet_02(bytes(self.watcher_addr)),
                    tuple(self.client_addr))
                self.punched_flag = True
        elif packet.is_(5):
            if not packet.matching_flag:
                self.transport.sendto(packet_07, addr)
            elif self.client_addr is None:
                self.profile_name = packet.profile_name
                self.transport.sendto(packet_06, addr)
                self.ack = 1
            else:
                self.transport.sendto(
                    get_packet_08(bytes(self.client_addr)),
                    addr)
                self.watcher_addr = IpPort.create(*addr)
        elif packet.is_(14):
            if len(packet.raw) == 3:
                self.transport.sendto(packet_0d_sp, addr)
                self.client_addr = IpPort.create(*addr)
            else:
                self.transport.sendto(get_packet_0d(self.ack), addr)
                if packet.raw[2:6] == b"\xff\xff\xff\xff":
                    self.ack = get_ack(packet.raw[2:6])
                else:
                    self.ack = get_ack(packet.raw[2:6])+1
        else:
            self.transport.sendto(data, addr)


async def task_func(bot: commands.Bot, ipport: IpPort) -> None:
    local_addr = IpPort.create('0.0.0.0', ipport.port())

    base_message = f"***___{ipport}は空いています。___***"
    message = await bot.send_message(
        get_client_ch(bot), base_message
    )
    transport = None

    while True:
        try:
            # クロック
            await asyncio.sleep(3)

            # 閉じていればサーバー再起動
            if transport is None or transport.is_closing():
                transport, protocol = await bot.loop.create_datagram_endpoint(
                    Th123HolePunchingProtocol,
                    local_addr=tuple(local_addr))

            # 一定時間通信なければ初期化
            if protocol.ack_datetime.is_expired():
                protocol.initialize()

            if protocol.profile_name is None:
                message = await bot.edit_message(message, base_message)
            else:
                # 一瞬メッセージを送信して通知を付ける
                if message.content == base_message:
                    notify = await bot.send_message(
                        get_client_ch(bot), ".")
                    await bot.delete_message(notify)

                notice_message = "***___{}さんが{}に入っています。___***".format(
                    protocol.profile_name,
                    ipport)
                message = await bot.edit_message(message, notice_message)

            if protocol.punched_flag:
                notice_message = "***___{}さんと{}で対戦ができます。___***".format(
                    protocol.profile_name,
                    protocol.client_addr)
                message = await bot.edit_message(message, notice_message)

                # 接続を切って通知を180秒間表示し続ける
                transport.close()
                await asyncio.sleep(180)
        except Exception as e:
            logger.exception(type(e).__name__, exc_info=e)


class ClientMatching(CogMixin):
    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self):
        myip = os.environ["myip"]
        discord.compat.create_task(
            task_func(self.bot, IpPort.create(myip, 38100)))
        discord.compat.create_task(
            task_func(self.bot, IpPort.create(myip, 38101)))
        discord.compat.create_task(
            task_func(self.bot, IpPort.create(myip, 38102)))
        await super().on_ready()
