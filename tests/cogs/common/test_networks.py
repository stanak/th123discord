import unittest

from cogs.common import networks


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
