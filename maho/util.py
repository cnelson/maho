import math


class Location(object):
    """Translate between latitude/longitude/elevation to x/y/z coords"""
    def __init__(self, lat, lng, ele):
        self.lat = lat
        self.lng = lng
        self.ele = ele

        lat = lat * math.pi / 180.0
        lng = lng * math.pi / 180.0

        clat = self._geocentric_latitude(lat)
        lng_cos = math.cos(lng)
        lng_sin = math.sin(lng)
        lat_cos = math.cos(lat)
        lat_sin = math.sin(lat)
        clat_cos = math.cos(clat)
        clat_sin = math.sin(clat)

        self.radius = self._earth_radius_in_meters(lat)

        x = self.radius * lng_cos * clat_cos
        y = self.radius * lng_sin * clat_cos
        z = self.radius * clat_sin

        self.nx = lat_cos * lng_cos
        self.ny = lat_cos * lng_sin
        self.nz = lat_sin

        self.x = x + (ele * self.nx)
        self.y = y + (ele * self.ny)
        self.z = z + (ele * self.nz)

    def _earth_radius_in_meters(self, lat):
        a = 6378137.0
        b = 6356752.3

        cos = math.cos(lat)
        sin = math.sin(lat)

        t1 = a * a * cos
        t2 = b * b * sin
        t3 = a * cos
        t4 = b * sin

        return math.sqrt((t1 * t1 + t2 * t2) / (t3 * t3 + t4 * t4))

    def _geocentric_latitude(self, lat):
        return math.atan((1.0 - 0.00669437999014) * math.tan(lat))


class AzimuthAltitudeDistance(object):
    """Compute azimuth altitude and distance between two sets of latitude, longitude, and elevation

    Example:
        aad = AzimuthAltitudeDistance(
            origin_latitude,
            origin_longitude,
            origin_altitude_in_meters
        )
        azimuth, altitude, distance = aad.calcuate(
            target_latitude,
            target_longitude,
            target_altitude_in_meters
        )
    """

    def __init__(self, lat, lng, ele):
        """Set the origin point for calculations

        Args:
            lat (float): Origin latitude
            lng (float): Origin longitude
            ele (float): Origin altitude in meters

        Returns:
            tuple (azimuth, altitude, distance)
                azimuth (float): 0-360.0
                altitude (float): 0-90.0
                distance (float): meters away
        """
        self.origin = Location(lat, lng, ele)

    def calculate(self, lat, lng, ele):
        destination = Location(lat, lng, ele)

        distance = self._distance(destination)

        azimuth, altitude = self._azimuth(destination)

        return azimuth, altitude, distance

    def _azimuth(self, destination):
        rotated_dest = Location(
            destination.lat,
            (destination.lng - self.origin.lng),
            destination.ele
        )

        olat = -self.origin.lat * math.pi / 180.0
        olat = self.origin._geocentric_latitude(olat)

        olat_cos = math.cos(olat)
        olat_sin = math.sin(olat)

        # bx = (rotated_dest.x * olat_cos) - (rotated_dest.z * olat_sin)
        by = rotated_dest.y
        bz = (rotated_dest.x * olat_sin) + (rotated_dest.z * olat_cos)

        azimuth = None
        if (bz * bz + by * by > 1.0e-6):
            theta = math.atan2(bz, by) * 180.0 / math.pi

            azimuth = 90.0 - theta

            if azimuth < 0.0:
                azimuth += 360.0

            if azimuth > 360.0:
                azimuth -= 360.0

        altitude = None

        dx = destination.x - self.origin.x
        dy = destination.y - self.origin.y
        dz = destination.z - self.origin.z

        dist = dx * dx + dy * dy + dz * dz

        if dist:
            dist = math.sqrt(dist)

            dx = dx / dist
            dy = dy / dist
            dz = dz / dist

            altitude = 90.0 - (180.0 / math.pi) * math.acos(
                dx * self.origin.nx + dy * self.origin.ny + dz * self.origin.nz
            )

        return azimuth, altitude

    def _distance(self, destination):

        dx = self.origin.x - destination.x
        dy = self.origin.y - destination.y
        dz = self.origin.z - destination.z

        return math.sqrt(dx * dx + dy * dy + dz * dz)
