from cogs.common.networks import Th123Packet, Lifetime, IpPort
import asyncio
from datetime import (datetime, timedelta)
import socket


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


class Th123Watcher2HostProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.initialize()

    def initialize(self):
        self.ack_datetime = Lifetime(timedelta(seconds=20))
        self.host_status = HostStatus()
        self.client_ipport = None
        self.counter = 0

    def try_echo(self):
        self.transport.sendto(Th123Packet.packet_05())

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def datagram_received(self, data, addr):
        self.ack_datetime.reset()
        packet = Th123Packet(data)
        header = packet.get_header()
        self.host_status(data)
        addr = IpPort.create(*addr)
        print(packet)
        if header == 0x07:
            pass
        elif header == 0x08:
            self.p1 = packet.get_profile_name
            self.p2 = packet.get_2p_profile_name
            self.client_ipport = packet.get_ipport()
            self.transport.sendto(Th123Packet.packet_01(addr, self.client_ipport), addr=tuple(addr))
            self.transport.sendto(Th123Packet.packet_01(self.client_ipport, self.client_ipport), addr=tuple(self.client_ipport))
        elif header == 0x03:
            self.transport.sendto(Th123Packet.packet_05(), addr=tuple(addr))
        elif header == 0x06:
            pass
            #self.transport.sendto(Th123Packet.packet_04(4), addr=tuple(addr))
        elif header == 0x04:
            self.counter += 1
            if self.counter >= 3:
                self.transport.sendto(Th123Packet.packet_0e_watch(), addr=tuple(addr))
            else:
                self.transport.sendto(Th123Packet.packet_04(4), addr=tuple(addr))
        elif header == 0x0d:
            print(addr)
            print('--------0d-------')
        else:
            print(addr)
            print('--------unknown-------')


async def main(loop, ipport):
    host_connect = loop.create_datagram_endpoint(Th123Watcher2HostProtocol, local_addr=('0.0.0.0', 10801))
    host_transport, host_protocol = await host_connect
    while True:
        await asyncio.sleep(5)
        host_transport.sendto(Th123Packet.packet_05(), addr=tuple(ipport))
        status = host_protocol.host_status
        if status is None:
            continue
        if host_protocol.ack_datetime.is_expired():
            print('時間切れ')
            break
        if not status.hosting:
            print('not hosting')
            continue
        elif status.hosting and not status.matching:
            print('not matching')
            continue


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('ipport')
    args = parser.parse_args()
    ipport = IpPort.create_with_str(args.ipport)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop, ipport))
