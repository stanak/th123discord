from cogs.common.networks import Th123Packet, Th123ReplayPacket, Lifetime, IpPort
from cogs.common.th123 import Th123ReplayBuilder, Th123ReplayMeta, id2character
import asyncio
from datetime import timedelta, datetime
import zlib


def hexdump(binary):
    res = [hex(x).replace('0x', '').zfill(2) for x in binary]
    return ' '.join([''.join(res[i:i+2]) for i in range(0, len(res), 2)])


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
        self.match_id = 1
        self.replay_wrote_match_id = 0
        self.now_frame = 0
        self.watch_flag = False
        self.meta = Th123ReplayMeta()


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
        print(hexdump(packet))
        if header == 0x07:
            pass
        elif header == 0x08:
            self.client_ipport = packet.get_ipport()
            self.transport.sendto(Th123Packet.packet_01(addr, self.client_ipport), addr=tuple(addr))
            self.transport.sendto(Th123Packet.packet_01(self.client_ipport, self.client_ipport), addr=tuple(self.client_ipport))
        elif header == 0x03:
            self.transport.sendto(Th123Packet.packet_05(), addr=tuple(addr))
        elif header == 0x06:
            self.p1 = packet.get_profile_name()
            self.p2 = packet.get_2p_profile_name()
        elif header == 0x04:
            self.counter += 1
            if self.counter >= 3:
                self.transport.sendto(Th123Packet.packet_0e_watch(), addr=tuple(addr))
            else:
                self.transport.sendto(Th123Packet.packet_04(4), addr=tuple(addr))
        elif header == 0x0d:
            detail_header = packet.get_detail_header()
            if detail_header == 0x0d04:
                self.watch_flag = True
                self.match_id = packet.get_matching_count()
                self.meta.match_id = self.match_id
                self.meta.characters = packet.get_characters()
                self.meta.colors = packet.get_colors()
                self.meta.deck_sizes = packet.get_deck_sizes()
                self.meta.decks = (packet.get_1p_decks(), packet.get_2p_decks())
                self.meta.simultaneous_buttons = packet.get_simultaneous_buttons()
                self.meta.stage = packet.get_stage()
                self.meta.bgm = packet.get_bgm()
                self.meta.seed = packet.get_seed()
                self.transport.sendto(Th123Packet.packet_0e_replay_request(self.now_frame, self.match_id), addr=tuple(addr))
            elif detail_header == 0x0d09:
                if self.match_id == self.replay_wrote_match_id:
                    print('replay wroted')
                    return
                decompressed = zlib.decompress(packet[3:])
                replay_packet = Th123ReplayPacket(decompressed)
                print('zlibdump:', hexdump(replay_packet))

                if replay_packet.get_inputs_count() != 0:
                    self.now_frame = replay_packet.get_frame_id()
                    self.meta.game_inputs += replay_packet.get_game_inputs()
                    end_frame = replay_packet.get_end_frame_id()
                    print('now_frame:', self.now_frame)
                    print('end_frame:', end_frame)
                    print('game_input_length:', len(self.meta.game_inputs) / 2)

                    if end_frame== len(self.meta.game_inputs) / 2:
                        print('frame_end:', replay_packet.get_end_frame_id())
                        print(len(self.meta.game_inputs))
                        self.meta.input_size = end_frame
                        now = datetime.now()
                        self.meta.date = now
                        replay_builder = Th123ReplayBuilder()
                        replay = replay_builder.build_replay(self.meta)
                        p1c = id2character(self.meta.characters[0])
                        p2c = id2character(self.meta.characters[1])
                        replay_name = now.strftime('%Y-%m-%d_%H-%M-%S') + f'_{self.p1}({p1c})_vs_{self.p2}({p2c}).rep'
                        replay_name = now.strftime('%Y-%m-%d_%H-%M-%S') + f'_{self.p1}({p1c})_vs_{self.p2}({p2c}).rep'
                        print(self.p1)
                        print(self.p2)
                        print(replay_name)
                        with open(replay_name, 'wb') as f:
                            f.write(replay)
                            print('replay writed')
                        self.replay_wrote_match_id = self.match_id
        elif header == 0x0b:
            self.watch_flag = False
        else:
            print('--------unknown-------')


async def main(loop, ipport):
    host_connect = loop.create_datagram_endpoint(Th123Watcher2HostProtocol, local_addr=('0.0.0.0', 10801))
    host_transport, host_protocol = await host_connect
    while True:
        await asyncio.sleep(5)
        if not host_protocol.watch_flag:
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
