from ipaddress import IPv4Address as ipv4
from typing import Any, Iterable
import unicodedata


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


if __name__ == "__main__":
    import doctest
    doctest.testmod()
