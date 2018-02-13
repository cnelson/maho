import unittest

import math
from maho.util import AzimuthAltitudeDistance


class TestAAD(unittest.TestCase):
    def test_aad(self):
        """My math works"""

        a = AzimuthAltitudeDistance(41.422650, -122.386127, 10)

        # a point 10 meters up should be at 0/90 degrees and 10 meters away
        result = a.calculate(41.422650, -122.386127, 20)

        self.assertEqual(result[0], 0)
        self.assertEqual(result[1], 90)
        self.assertEqual(math.ceil(result[2]), 10)
