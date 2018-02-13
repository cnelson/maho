import socket
import time
import unittest

from unittest.mock import patch

from maho.adsb import Aircraft, Dump1090

from io import BytesIO as StringIO


class FakeSocket():
    """Use StringIO to pretend to be a socket like object that supports makefile()"""
    def __init__(self, data):
        self._str = StringIO(data)

    def makefile(self, *args, **kwargs):
        """Returns the StringIO object.  Ignores all arguments"""
        return self._str


class TestFakeSocket(unittest.TestCase):
    def test_socket(self):
        """When using the FakeSocket we get the same data out that we put in"""

        f = FakeSocket(b"foo")

        assert f.makefile().read() == b"foo"


class TestAircraft(unittest.TestCase):

    def test_age(self):
        """Updating an aircraft property resets it's age"""
        a = Aircraft('foo')
        time.sleep(1)

        self.assertEqual(int(a.age), 1)

    def test_readonly_age(self):
        a = Aircraft('foo')

        with self.assertRaises(ValueError):
            a.age = 'bar'


class TestDump1090(unittest.TestCase):

    @patch('maho.adsb.socket.socket', side_effect=socket.error)
    def test_bad_connection(self, mocksock):
        """When dump1090 cannot be reached, IOError is raised"""
        with self.assertRaises(IOError):
            Dump1090('192.0.2.123')

    @patch('maho.adsb.socket.socket')
    def test_max_aircraft(self, mocksock):
        """Do not cache more than the specified number of aircraft"""

        adsb = Dump1090(max_aircraft=2)

        self.assertEqual(len(adsb._cache.keys()), 0)

        adsb._cache['foo'] = Aircraft('foo')
        adsb._cache['bar'] = Aircraft('bar')

        self.assertEqual(len(adsb._cache.keys()), 2)

        adsb._cache['baz'] = Aircraft('baz')

        self.assertEqual(len(adsb._cache.keys()), 2)

    @patch('maho.adsb.socket.socket')
    def test_max_aircraft_age(self, mocksock):
        """Do not keep aircraft older than the specified age"""

        adsb = Dump1090(max_aircraft_age=1)

        adsb._cache['foo'] = Aircraft('foo')

        self.assertEqual(adsb._cache['foo'].icao, 'foo')

        time.sleep(1)

        with self.assertRaises(KeyError):
            adsb._cache['foo']

    @patch('maho.adsb.socket.socket')
    def test_updates(self, mocksock):
        """Aircraft info is yielded when position updates are provided"""

        # sample ADS-B packets:
        # [A777BF / AAL517] (37.74632, -122.15961) @ 7275 ft. 302 mph, heading 56.
        fs = FakeSocket(
            b"*8DA777BF23041335C7782074EF6;\n" +
            b"*8DA777BF9908DE1230A48B2BBA5;\n" +
            b"*8DA777BF5829A4BEA0C802BFE85;\n" +
            b"*8DA777BF5829B12A0A1A4FCECA4;\n"
        )

        adsb = Dump1090()
        adsb._adsbsock = fs

        aircraft = list(adsb.updates())

        self.assertTrue(len(aircraft), 1)

        aircraft = aircraft[0]

        self.assertEqual(aircraft.icao, 'A777BF')
        self.assertEqual(aircraft.callsign, 'AAL517')
        self.assertEqual(aircraft.position, (37.74632, -122.15961))
        self.assertEqual(aircraft.altitude, 2217.42)
        self.assertEqual(aircraft.speed, 302)
        self.assertEqual(aircraft.heading, 56)
