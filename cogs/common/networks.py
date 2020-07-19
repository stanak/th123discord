from datetime import (datetime, timedelta)
from ipaddress import IPv4Address as ipv4
from typing import Any, Iterable
import unicodedata


class Lifetime:
    def __init__(self, lifetime: timedelta):
        self.lifetime = lifetime
        self.reset()

    def reset(self):
        self.ack_datetime = datetime.now()

    def elapsed_datetime(self):
        return datetime.now() - self.ack_datetime

    def is_expired(self):
        return self.elapsed_datetime() >= self.lifetime


class IpPort:
    __construct_key = object()

    def __init__(self, ip: ipv4, port: int, *, key: object) -> None:
        assert key == self.__construct_key, \
            'PortIp object must be created using PortIp.create methods'

        self._ip = ip
        self._port = port

    @classmethod
    def create(cls, ip: Any, port: Any) -> 'IpPort':
        return IpPort(ipv4(ip), int(port), key=cls.__construct_key)

    @classmethod
    def create_with_str(cls, ip_port: str) -> 'IpPort':
        ip, port = unicodedata.normalize('NFKC', ip_port).split(':', 1)
        ip = ipv4(ip)
        port = int(port)
        if port not in range(0x0000, 0xffff):
            raise ValueError
        return IpPort(ip, port, key=cls.__construct_key)

    @classmethod
    def create_with_bin(cls, port_ip: bytes) -> 'IpPort':
        port, ip = (int.from_bytes(port_ip[:2], 'big'), ipv4(port_ip[2:]))
        return IpPort(ip, port, key=cls.__construct_key)

    def ipaddr(self) -> ipv4:
        return self._ip

    def port(self) -> int:
        return self._port

    def __str__(self) -> str:
        return f'{self._ip.exploded}:{self._port}'

    def __bytes__(self) -> bytes:
        return self.port().to_bytes(2, 'big') + self._ip.packed

    def __iter__(self) -> Iterable:
        yield self._ip.exploded
        yield self._port


class Th123Packet(bytes):
    @staticmethod
    def packet_01(
        first_ipport: IpPort,
        second_ipport: IpPort,
    ) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '01'
            f'0200{bytes(first_ipport).hex()}' '00000000' '00000000'
            f'0200{bytes(second_ipport).hex()}' '00000000' '00000000'
            '00000000'))

    @staticmethod
    def packet_02(ipport: IpPort) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '02'
            f'0200{bytes(ipport).hex()}' '00000000' '00000000'
            '00000000'))

    @staticmethod
    def packet_03() -> 'Th123Packet':
        return Th123Packet(bytes.fromhex('03'))

    @staticmethod
    def packet_04(data: int) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '04'
            f'{data.to_bytes(4, "little").hex()}'))

    @staticmethod
    def packet_05(
        *,
        sokuroll_uses: bool=False,
        should_match: bool=False,
        profile_name: str=str(),
    ) -> 'Th123Packet':
        soku_id_byte = '64' if sokuroll_uses else '6e'
        profile_name_bytes = str.encode(profile_name, 'shift-jis')
        return Th123Packet(bytes.fromhex(
            '05'
            f'{soku_id_byte}7365d9' 'ffc46e48' '8d7ca192' '31347295'
            '00000000' '28000000'
            f'{int(should_match):02}'
            f'{len(profile_name_bytes).to_bytes(1, "big").hex()}'
            f'{profile_name_bytes.hex():0<48}'
            '00000000' '00000000' '00000000' '0000'))

    @staticmethod
    def packet_06(
        *,
        profile_1p_name: str='Shanghai',
        profile_2p_name: str=str()
    ) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '06'
            '00000000' '10000000' '44000000'
            f'{str.encode(profile_1p_name, "shift-jis").hex():0<48}'
            '00000000' '00000000'
            f'{str.encode(profile_2p_name, "shift-jis").hex():0<48}'
            '00000000' '00000000'
            '00000000'))

    @staticmethod
    def packet_07(*, is_watchable: bool=False) -> 'Th123Packet':
        if is_watchable:
            return Th123Packet(bytes.fromhex('07' '01000000'))
        else:
            return Th123Packet(bytes.fromhex('07' '00000000'))

    @staticmethod
    def packet_08(ipport: IpPort) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '08'
            '01000000'
            f'0200{bytes(ipport).hex()}' '00000000' '00000000'
            # This packet might just be garbage, goodness knows that.
            '70000000' '0000060c' '00000000' '00100000' '00000000' '00010e03'
            '97ce0010' '10101010' '10000000' '010d0905' '0e010000' '00100000'))

    @staticmethod
    def packet_0b() -> 'Th123Packet':
        return Th123Packet(bytes.fromhex('0b'))

    @staticmethod
    def packet_0d(ack: int, count: int=2) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '0d'
            f'03{ack.to_bytes(4, "little").hex()}03'
            f'{count.to_bytes(1, "little").hex()}' f'{"0000" * count}'))

    @staticmethod
    def packet_0e(ack: int, count: int=1) -> 'Th123Packet':
        return Th123Packet(bytes.fromhex(
            '0e'
            f'03{ack.to_bytes(4, "little").hex()}03'
            f'{count.to_bytes(1, "little").hex()}' f'{"0000" * count}'))

    @staticmethod
    def packet_0d_sp() -> 'Th123Packet':
        return Th123Packet(bytes.fromhex('0d' '0203'))

    @staticmethod
    def packet_0e_sp() -> 'Th123Packet':
        return Th123Packet(bytes.fromhex('0e' '0103'))

    def get_header(self) -> int:
        if len(self) > 0:
            return self[0]
        return None

    def get_ipport(self) -> IpPort:
        if self.get_header() == 0x01:
            return IpPort.create_with_bin(self[3:9])
        if self.get_header() == 0x02:
            return IpPort.create_with_bin(self[3:9])
        if self.get_header() == 0x08:
            return IpPort.create_with_bin(self[7:13])
        return None

    def get_2p_ipport(self) -> IpPort:
        if self.get_header() == 0x01:
            return IpPort.create_with_bin(self[19:25])

    def get_matching_flag(self) -> bool:
        if self.get_header() == 0x05:
            return bool(self[25])
        return None

    def get_profile_name(self) -> str:
        if self.get_header() == 0x05:
            profile_length = self[26]
            return self[27:27 + profile_length].decode('shift-jis')
        if self.get_header() == 0x06:
            return self[13:37].decode('shift-jis').strip('\x00')
        if self.get_header() == 0x08:
            return self[13:37].decode('shift-jis').strip('\x00')
        return None

    def get_2p_profile_name(self) -> str:
        if self.get_header() == 0x08:
            return self[45:69].decode('shift-jis').strip('\x00')

    def get_ack_count(self) -> int:
        if self.get_header() == 0x0e and len(self) >= 6:
            return int.from_bytes(self[2:6], 'little')
        if self.get_header() == 0x0d and len(self) >= 6:
            return int.from_bytes(self[2:6], 'little')
        return None


if __name__ == '__main__':
    import argparse
    import binascii
    parser = argparse.ArgumentParser()
    parser.add_argument('byte')
    args = parser.parse_args()
    packet = Th123Packet(binascii.unhexlify(args.byte))
    print(packet.get_ipport())
    print(packet.get_2p_ipport())
