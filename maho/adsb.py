import datetime
import socket
import time

import pyModeS as modes

from expiringdict import ExpiringDict


class Aircraft(object):
    """A representation of an aircraft's reported information

    This object gets populated by ADS-B decoders
    """
    def __init__(self, icao):
        """Create a new instance given an icao address"""
        self.icao = icao

        self.callsign = None
        self.altitude = None
        self.position = None
        self.speed = None
        self.heading = None

    def __str__(self):
        return "[{} / {}] {} @ {}m. {} mph, heading {}.".format(
            self.icao,
            self.callsign,
            self.position,
            int(self.altitude),
            self.speed,
            self.heading
        )

    @property
    def icao(self):
        return self._icao

    @icao.setter
    def icao(self, value):
        self._icao = value
        self._last_update = datetime.datetime.utcnow()

    @property
    def callsign(self):
        return self._callsign

    @callsign.setter
    def callsign(self, value):
        self._callsign = value
        self._last_update = datetime.datetime.utcnow()

    @property
    def altitude(self):
        return self._altitude * 0.3048  # ft to meters

    @altitude.setter
    def altitude(self, value):
        self._altitude = value
        self._last_update = datetime.datetime.utcnow()

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, value):
        self._speed = value
        self._last_update = datetime.datetime.utcnow()

    @property
    def heading(self):
        return self._heading

    @heading.setter
    def heading(self, value):
        self._heading = value
        self._last_update = datetime.datetime.utcnow()

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self._position_even = None
        self._position_odd = None

    @property
    def position_even(self):
        return self._position_even

    @position_even.setter
    def position_even(self, value):
        self._position_even = (value, time.time())

    @property
    def position_odd(self):
        return self._position_odd

    @position_odd.setter
    def position_odd(self, value):
        self._position_odd = (value, time.time())

    @property
    def age(self):
        return (datetime.datetime.utcnow() - self._last_update).total_seconds()

    @age.setter
    def age(self, value):
        raise ValueError("This property cannot be set.")


class ADSBReciver(object):
    """Provides a generator that yields ADS-B updates"""

    def updates(self):
        """A generator that yields Aircraft instances when updates are received

        Yields:
            Aircraft: The aircraft we received a position update for

        """
        raise NotImplementedError


class Dump1090(ADSBReciver):
    """Reads ADS-B packets from a copy of dump1090's "TCP raw output"""

    def __init__(
        self,
        adsb_host='localhost',
        adsb_port=30002,
        max_aircraft=1000,
        max_aircraft_age=60
    ):
        """Connect to dump1090 TCP raw output

        Args:
            adsb_host (str): The hostname running dump1090
            adsb_port (int): The "TCP raw output" port

            max_aircraft (int, optional): The maxinum number of aircraft to cache in memory
            max_aircraft_age (int, optional): The maxinum number of seconds to cache
            an aircraft after receiving an ADS-B update

        Raises:
            IOError: Unable to connect to dump1090

        """

        self._adsbsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._adsbsock.connect((adsb_host, adsb_port))

        # TODO: Expose these settiongs
        self._cache = ExpiringDict(max_len=max_aircraft, max_age_seconds=max_aircraft_age)

    def updates(self):
        """A generator that blocks forever yielding new Aircraft position info

        Yields:
            Aircraft: The aircraft we received a position update for
        """

        for packet in self._adsbsock.makefile('rb'):
            packet = packet.rstrip().decode()

            if len(packet) < 15 or packet[0] != '*' or packet[-1] != ';':
                continue

            aircraft = self.decode(packet[1:-2])
            if aircraft is not None:
                yield(aircraft)

    def decode(self, msg):
        """Decode an ADS-B message in hex-string format

        Args:
            msg (str): The ADS-B message

        Returns:
            None: The packet was decoded but did not provide a position update
            Aircraft: An aircraft with updated position information

        """

        icao = modes.adsb.icao(msg)

        aircraft = self._cache.get(icao, Aircraft(icao))

        rv = None

        if modes.adsb.df(msg) == 17:
            if modes.adsb.typecode(msg) < 5:
                aircraft.callsign = modes.adsb.callsign(msg).rstrip('_')

            if modes.adsb.typecode(msg) == 19:

                aircraft.speed = int(modes.adsb.speed_heading(msg)[0] * 1.15078)  # knots to mph

                aircraft.heading = int(modes.adsb.speed_heading(msg)[1])

            if modes.adsb.typecode(msg) > 8 and modes.adsb.typecode(msg) < 19:
                aircraft.altitude = modes.adsb.altitude(msg)

                if modes.adsb.oe_flag(msg) == 0:
                    aircraft.position_even = msg
                else:
                    aircraft.position_odd = msg

                if aircraft.position_odd is not None and aircraft.position_even is not None:
                    aircraft.position = modes.adsb.position(
                        aircraft.position_even[0],
                        aircraft.position_odd[0],
                        aircraft.position_even[1],
                        aircraft.position_odd[1]
                    )

                    # only return flights with full position information
                    if aircraft.altitude is not None and aircraft.position is not None:
                        rv = aircraft

            self._cache[icao] = aircraft

            return rv
