from urllib import parse

from onvif import ONVIFCamera, ONVIFError

# hax :( https://github.com/mvantellingen/python-zeep/issues/418
from zeep.xsd.types.simple import AnySimpleType


def _pythonvalue(self, xmlvalue):
    return xmlvalue


AnySimpleType.pythonvalue = _pythonvalue


class Camera(object):
    """Abstraction for camera control and video stream information"""

    def move_to(self, azimuth, altitude):
        """Move the camera to look at a given azimuth and altitude

        This method should block until the movement is complete.

        Args:
            azimuth (float): 0.0-360.0
            altitude (float): 0.0-90.0

        Returns:
            tuple: (azimuth, altitude) where the camera was actually moved to

        Raises:
            RuntimeError: Error when moving camera

        """

        raise NotImplementedError

    def get_rtsp_url(self):
        """Return an URL to an RTSP stream for the camera

        Returns:
            str: The URL to the RTSP stream

        Raises:
            RuntimeError: Unable to retrieve URL from the camera

        """
        raise NotImplementedError


class IPCamera(object):
    """Control cameras via ONVIF.

    Using this protocol sucks, because it's SOAP based wheich means we need a bunch of
    lxml dependencies to talk to it, but it allows us to talk to a wide variety of cameras
    and move them in a defined absolute coordinate space so :shrug:...

    """
    def __init__(self, hostname, port, username, password, azimuth_offset=0.0, altitude_offset=0.0):
        """Connect to an IP Camera that supports the ONVIF protocol

        Args:
            hostname (str): The hostname or ip of the camera
            port (int): The port to connect to
            username (str): authentication
            password (str): authentication

            azimuth_offset (float, optional): If provided, will offset all move requests.
            altitude_offset (float, optional): If provided, will offset all move requests.

            These values can be positive or negative and are in degrees.

            The above offsets are useful if your camera is not mounted with "0" pointing exactly
            at north or not exactly level.

            For example if your camera's "0" location is pointing at 345 degress
            you could set azimuth_offset to  to '15.0'

        Raises:
            RuntimeError: Unable to connect to camera with the provided details

        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

        self.azimuth_offset = azimuth_offset
        self.altitude_offset = altitude_offset

        try:
            self.camera = ONVIFCamera(hostname, port, username, password)
            self.media_service = self.camera.create_media_service()
            self.ptz_service = self.camera.create_ptz_service()

            # TODO: Is it safe to assume the first profile is always the one we want?
            self.media_profile = self.media_service.GetProfiles()[0]
        except ONVIFError as exc:
            raise RuntimeError("Unable to connect to camera: {}".format(exc))

    def move_to(self, azimuth, altitude):
        """Move the camera to look at a given azimuth and altitude

        Note: On the cameras I had available to test with , they supported 360 degree freedom
        but could only do that by turning 180 degress either way.  So you you need to transition
        from 170-190 degress, the camera will move from 170 0, and then 0 to 190.

        They cannot move from 170-190 directly crossing the 180 degree line. AbsoluteMove will
        handle this for you, but it may be unexpected, that the camera swivels almost 360 deg
        when tracking to/from south east / south west.

        See https://www.onvif.org/specs/srv/ptz/ONVIF-PTZ-Service-Spec-v221.pdf Section 5.2

        TLDR:

        -1.0 = 180 dregress
        -.5 = 270 dregress
        0 = 0 degrees
        .5 = 90 degress
        1.0 = 180 degress


        Args:
            azimuth (float): 0.0-360.0
            altitude (float): 0.0-90.0

        Returns:
            tuple: (azimuth, altitude) where the camera was actually moved to

        Raises:
            RuntimeError: Error when moving camera

        """

        azimuth = azimuth + self.azimuth_offset
        altitude = altitude + self.altitude_offset

        if azimuth > 360:
            azimuth = azimuth - 360
        elif azimuth < 0:
            azimuth = 360 + azimuth

        if altitude > 90:
            altitude = 90
        elif altitude < 0:
            altitude = 0

        # convert azimuth / altitude to ONVF 0.0-1.0 coordinates
        if azimuth <= 180:
            x_target = azimuth / 180.0
        else:
            x_target = ((360 - azimuth) / 180.0) * -1

        if altitude <= 45:
            y_target = (45 - altitude) / 45.0
        else:
            y_target = ((altitude - 45) / 45.0) * -1

        try:
            self.ptz_service.AbsoluteMove(
                {
                    "ProfileToken": self.media_profile.token,
                    "Position": {"PanTilt": {"x": x_target, "y": y_target}},
                    "Speed": {"PanTilt": {"x": 1, "y": 1}}
                }
            )
            return (azimuth, altitude)
        except ONVIFError as exc:
            raise RuntimeError("Unable to move camera: {}".format(exc))

    def get_rtsp_url(self):
        """Interrogate the camera to get the RTSP URL of the video stream

        According to https://www.onvif.org/specs/stream/ONVIF-Streaming-Spec-v210.pdf all cameras
        that support this spec _should_ return an RTSP URL.

        """
        try:
            info = self.media_service.GetStreamUri(
                {
                    "StreamSetup": {
                        "Stream": "RTP_unicast",
                        "Transport": "RTSP"
                    },
                    "ProfileToken": self.media_profile.token
                }
            )

            # inject the auth info into the returned URL so OpenCV(ffmpeg) can deal with it
            uri = parse.urlparse(info['Uri'])
            if '@' not in uri.netloc:
                uri = uri._replace(
                    netloc="{}:{}@{}".format(self.username, self.password, uri.netloc)
                )

            return parse.urlunparse(uri)

        except (ONVIFError, KeyError) as exc:
            raise RuntimeError("Unable to retrieve RTSP URL from camera: {}".format(exc))
