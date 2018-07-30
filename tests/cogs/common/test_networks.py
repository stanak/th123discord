import unittest
from unittest.mock import (patch, MagicMock)

from datetime import (datetime, timedelta)
import time

from cogs.common import networks


class testLifetime(unittest.TestCase):
    def test_dunder_init(self):
        mock = MagicMock()
        with patch('cogs.common.networks.Lifetime.reset', mock):
            arg = timedelta(seconds=1)
            lifetime = networks.Lifetime(arg)

        self.assertEqual(lifetime.lifetime, arg)
        mock.assert_called_once()

    def test_reset(self):
        arg = timedelta(seconds=1)
        lifetime = networks.Lifetime(arg)

        time.sleep(.1)
        self.assertNotEqual(lifetime.ack_datetime, datetime.now())

        ack_datetime = lifetime.ack_datetime
        lifetime.reset()
        self.assertNotEqual(lifetime.ack_datetime, ack_datetime)

    def test_elapsed_datetime(self):
        for arg in (timedelta(seconds=1), timedelta(seconds=2)):
            with self.subTest(arg=arg):
                lifetime = networks.Lifetime(arg)

                time.sleep(.1)
                self.assertAlmostEqual(
                    .1,
                    lifetime.elapsed_datetime().total_seconds(),
                    places=1)

                time.sleep(arg.total_seconds())
                self.assertAlmostEqual(
                    arg.total_seconds() + .1,
                    lifetime.elapsed_datetime().total_seconds(),
                    places=1)

    def test_is_expired(self):
        for arg in (timedelta(seconds=1), timedelta(seconds=2)):
            with self.subTest(arg=arg):
                lifetime = networks.Lifetime(arg)

                self.assertFalse(lifetime.is_expired())

                time.sleep(arg.total_seconds() - .1)
                self.assertFalse(lifetime.is_expired())

                time.sleep(.1)
                self.assertTrue(lifetime.is_expired())


class TestIpPort(unittest.TestCase):
    def test_dunder_init(self):
        with self.assertRaises(AssertionError):
            networks.IpPort(None, None, key=None)

        with self.assertRaises(AssertionError):
            networks.IpPort(None, None, key=object())

    def test_create(self):
        self.assertIsInstance(
            networks.IpPort.create('192.0.2.0', 7500),
            networks.IpPort)

        self.assertIsInstance(
            networks.IpPort.create('127.0.0.1', 38100),
            networks.IpPort)

        self.assertIsInstance(
            networks.IpPort.create('192.168.1.1', 10800),
            networks.IpPort)

    def test_create_with_str(self):
        self.assertIsInstance(
            networks.IpPort.create_with_str('192.0.2.0:7500'),
            networks.IpPort)

        self.assertIsInstance(
            networks.IpPort.create_with_str('127.0.0.1:38100'),
            networks.IpPort)

        self.assertIsInstance(
            networks.IpPort.create_with_str('192.168.1.1:10800'),
            networks.IpPort)

    def test_create_with_bin(self):
        self.assertIsInstance(
            networks.IpPort.create_with_bin(b'\x1dL\xc0\x00\x02\x00'),
            networks.IpPort)

        self.assertIsInstance(
            networks.IpPort.create_with_bin(b'\x94\xd4\x7f\x00\x00\x01'),
            networks.IpPort)

        self.assertIsInstance(
            networks.IpPort.create_with_bin(b'*0\xc0\xa8\x01\x01'),
            networks.IpPort)

    def test_dunder_str(self):
        ipport = networks.IpPort.create('192.0.2.0', 7500)
        self.assertEqual(str(ipport), '192.0.2.0:7500')

        ipport = networks.IpPort.create_with_str('127.0.0.1:38100')
        self.assertEqual(str(ipport), '127.0.0.1:38100')

        ipport = networks.IpPort.create_with_bin(b'*0\xc0\xa8\x01\x01')
        self.assertEqual(str(ipport), '192.168.1.1:10800')

    def test_dunder_bin(self):
        ipport = networks.IpPort.create('192.0.2.0', 7500)
        self.assertEqual(bytes(ipport), b'\x1dL\xc0\x00\x02\x00')

        ipport = networks.IpPort.create_with_str('127.0.0.1:38100')
        self.assertEqual(bytes(ipport), b'\x94\xd4\x7f\x00\x00\x01')

        ipport = networks.IpPort.create_with_bin(b'*0\xc0\xa8\x01\x01')
        self.assertEqual(bytes(ipport), b'*0\xc0\xa8\x01\x01')

    def test_dunder_iter(self):
        ipport = networks.IpPort.create('192.0.2.0', 7500)
        self.assertEqual(tuple(ipport), ('192.0.2.0', 7500))

        ipport = networks.IpPort.create_with_str('127.0.0.1:38100')
        self.assertEqual(tuple(ipport), ('127.0.0.1', 38100))

        ipport = networks.IpPort.create_with_bin(b'*0\xc0\xa8\x01\x01')
        self.assertEqual(tuple(ipport), ('192.168.1.1', 10800))


class TestTh123Packet(unittest.TestCase):
    def test_packet_01(self):
        ipport_a = networks.IpPort.create_with_str('192.0.2.0:7500')
        ipport_b = networks.IpPort.create_with_str('127.0.0.1:38100')
        ipport_c = networks.IpPort.create_with_str('192.168.1.1:10800')

        for first, second in (
            (ipport_a, ipport_b),
            (ipport_b, ipport_c),
            (ipport_c, ipport_a),
        ):
            with self.subTest(first=str(first), second=str(second)):
                packet = networks.Th123Packet.packet_01(first, second)
                self.assertEqual(packet[0], 0x01)
                self.assertEqual(packet[1:3], bytes.fromhex('0200'))
                self.assertEqual(packet[3:9], bytes(first))
                self.assertEqual(packet[9:17], bytes.fromhex('00' * 8))
                self.assertEqual(packet[17:19], bytes.fromhex('0200'))
                self.assertEqual(packet[19:25], bytes(second))
                self.assertEqual(packet[25:], bytes.fromhex('00' * 12))
                self.assertEqual(tuple(packet.get_ipport()), tuple(first))

    def test_packet_02(self):
        ipport_a = networks.IpPort.create_with_str('192.0.2.0:7500')
        ipport_b = networks.IpPort.create_with_str('127.0.0.1:38100')

        for ipport in (ipport_a, ipport_b):
            with self.subTest(ipport=str(ipport)):
                packet = networks.Th123Packet.packet_02(ipport)
                self.assertEqual(packet[0], 0x02)
                self.assertEqual(packet[1:3], bytes.fromhex('0200'))
                self.assertEqual(packet[3:9], bytes(ipport))
                self.assertEqual(packet[9:], bytes.fromhex('00' * 12))
                self.assertEqual(tuple(packet.get_ipport()), tuple(ipport))

    def test_packet_03(self):
        packet = networks.Th123Packet.packet_03()
        self.assertEqual(packet, bytes.fromhex('03'))

    def test_packet_04(self):
        for (data, hexdata) in (
            (0x00, '00000000'),
            (0x01, '01000000'),
            (0x10, '10000000'),
            (0x100, '00010000'),
            (0xa5b4c3d2, 'd2c3b4a5'),
            (0xffffffff, 'ffffffff'),
        ):
            with self.subTest(data=data):
                packet = networks.Th123Packet.packet_04(data)
                self.assertEqual(packet, bytes.fromhex(f'04{hexdata}'))

    def test_packet_05(self):
        normal_packet = networks.Th123Packet.packet_05(sokuroll_uses=False)
        sokuroll_packet = networks.Th123Packet.packet_05(sokuroll_uses=True)
        self.assertEqual(normal_packet[:2], bytes.fromhex('056e'))
        self.assertEqual(sokuroll_packet[:2], bytes.fromhex('0564'))
        self.assertEqual(normal_packet[2:], sokuroll_packet[2:])

        packet_a = networks.Th123Packet.packet_05(should_match=False)
        packet_b = networks.Th123Packet.packet_05(should_match=True)
        self.assertEqual(packet_a[:25], packet_b[:25])
        self.assertEqual(packet_a[26:], packet_b[26:])
        self.assertEqual(packet_a[25], 0x00)
        self.assertEqual(packet_b[25], 0x01)
        self.assertFalse(packet_a.get_matching_flag())
        self.assertTrue(packet_b.get_matching_flag())

        packet_a = networks.Th123Packet.packet_05(profile_name='Test')
        packet_b = networks.Th123Packet.packet_05(profile_name='テスト')
        self.assertEqual(packet_a[:26], packet_b[:26])
        self.assertNotEqual(packet_a[27:], packet_b[27:])
        self.assertEqual(packet_a[77:], packet_b[77:])
        self.assertEqual(packet_a.get_profile_name(), 'Test')
        self.assertEqual(packet_b.get_profile_name(), 'テスト')

    def test_packet_06(self):
        packet= networks.Th123Packet.packet_06()
        self.assertEqual(packet[0], 0x06)
        self.assertEqual(
            packet[13:37].decode('shift-jis').strip('\x00'),
            'Shanghai')
        self.assertEqual(packet[37:45], bytes.fromhex('00' * 8))
        self.assertEqual(packet[45:69], bytes.fromhex('00' * 24))
        self.assertEqual(packet[69:], bytes.fromhex('00' * 12))
        self.assertEqual(packet.get_profile_name(), 'Shanghai')

        packet= networks.Th123Packet.packet_06(
            profile_1p_name='テスト',
            profile_2p_name='Test')
        self.assertEqual(packet[0], 0x06)
        self.assertEqual(
            packet[13:37].decode('shift-jis').strip('\x00'),
            'テスト')
        self.assertEqual(packet[37:45], bytes.fromhex('00' * 8))
        self.assertEqual(
            packet[45:69].decode('shift-jis').strip('\x00'),
            'Test')
        self.assertEqual(packet[69:], bytes.fromhex('00' * 12))
        self.assertEqual(packet.get_profile_name(), 'テスト')

    def test_packet_07(self):
        packet_default = networks.Th123Packet.packet_07()
        packet_false = networks.Th123Packet.packet_07(is_watchable=False)
        packet_true = networks.Th123Packet.packet_07(is_watchable=True)
        self.assertEqual(packet_default, packet_false)
        self.assertNotEqual(packet_false, packet_true)

    def test_packet_08(self):
        ipport_a = networks.IpPort.create_with_str('192.0.2.0:7500')
        ipport_b = networks.IpPort.create_with_str('127.0.0.1:38100')

        for ipport in (ipport_a, ipport_b):
            with self.subTest(ipport=str(ipport)):
                packet = networks.Th123Packet.packet_08(ipport)
                self.assertEqual(packet[0], 0x08)
                self.assertEqual(packet[1:5], bytes.fromhex('01000000'))
                self.assertEqual(packet[5:7], bytes.fromhex('0200'))
                self.assertEqual(packet[7:13], bytes(ipport))
                self.assertEqual(len(packet[13:]), 56)
                self.assertEqual(tuple(packet.get_ipport()), tuple(ipport))

    def test_packet_0b(self):
        packet = networks.Th123Packet.packet_0b()
        self.assertEqual(packet, bytes.fromhex('0b'))

    def test_packet_0d(self):
        packet = networks.Th123Packet.packet_0d(0x00)
        for ack, ack_hex, count in (
            (0x01, "01000000", 1),
            (0x10, "10000000", 2),
            (0x100, "00010000", 5),
            (0x5a4b3c2d, "2d3c4b5a", 10),
            (0xffffffff, "ffffffff", 100),
        ):
            with self.subTest(ack=ack, count=count):
                packet = networks.Th123Packet.packet_0d(ack, count)
                self.assertEqual(packet[0], 0x0d)
                self.assertEqual(packet[1:7], bytes.fromhex(f'03{ack_hex}03'))
                self.assertEqual(packet[7], count)
                self.assertEqual(packet[8:], bytes.fromhex('0000' * count))
                self.assertEqual(packet.get_ack_count(), ack)

    def test_packet_0e(self):
        packet = networks.Th123Packet.packet_0e(0x00)
        for ack, ack_hex, count in (
            (0x01, "01000000", 1),
            (0x10, "10000000", 2),
            (0x100, "00010000", 5),
            (0x5a4b3c2d, "2d3c4b5a", 10),
            (0xffffffff, "ffffffff", 100),
        ):
            with self.subTest(ack=ack, count=count):
                packet = networks.Th123Packet.packet_0e(ack, count)
                self.assertEqual(packet[0], 0x0e)
                self.assertEqual(packet[1:7], bytes.fromhex(f'03{ack_hex}03'))
                self.assertEqual(packet[7], count)
                self.assertEqual(packet[8:], bytes.fromhex('0000' * count))
                self.assertEqual(packet.get_ack_count(), ack)

    def test_packet_0d_sp(self):
        packet = networks.Th123Packet.packet_0d_sp()
        self.assertEqual(packet, bytes.fromhex('0d0203'))

    def test_packet_0e_sp(self):
        packet = networks.Th123Packet.packet_0e_sp()
        self.assertEqual(packet, bytes.fromhex('0e0103'))
