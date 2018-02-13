import unittest

from unittest.mock import Mock, patch

from onvif import ONVIFError

from maho.camera import IPCamera


@patch('maho.camera.ONVIFCamera')
class TestIPCamera(unittest.TestCase):

    def test_init_bad(self, onvifmock):
        """When failing to connect or auth with the camera, RuntimeError is raised."""

        onvifmock.side_effect = ONVIFError('Yolo')

        with self.assertRaises(RuntimeError):
            IPCamera('192.0.2.123', 9160, 'root', 'hunter2')

    def test_move_bad(self, onvifmock):
        """If the camera fails to respond to a move command, RuntimeError is raised."""
        camera = IPCamera('192.0.2.123', 9160, 'root', 'hunter2')

        ptzmock = Mock()
        ptzmock.AbsoluteMove.side_effect = ONVIFError('Simulated PTZ Error')
        camera.ptz_service = ptzmock

        with self.assertRaises(RuntimeError):
            camera.move_to(180, 45)

    def test_move_good(self, onvifmock):
        """Camera handles good and oob coordinates when moving"""
        camera = IPCamera('192.0.2.123', 9160, 'root', 'hunter2')

        ptzmock = Mock()
        camera.ptz_service = ptzmock

        self.assertEqual((180, 45), camera.move_to(180, 45))

        # if offsets are provided, the camera returns the actual location moved to
        # altitude is capped at 0-9, but azimuth with loop around
        camera.azimuth_offset = 10.0
        camera.altitude_offset = 10.0

        self.assertEqual((10, 90), camera.move_to(360, 81))

        # negative offsets work too
        camera.azimuth_offset = -10.0
        camera.altitude_offset = -10.0

        self.assertEqual((355, 35), camera.move_to(5, 45))

        self.assertEqual((80, 0), camera.move_to(90, 5))

    def test_geturl_bad(self, onvifmock):
        """If the camera fails to respond to a URI query, RuntimeError is raised."""
        camera = IPCamera('192.0.2.123', 9160, 'root', 'hunter2')

        mediamock = Mock()
        mediamock.GetStreamUri.side_effect = ONVIFError('Simulated PTZ Error')
        camera.media_service = mediamock

        with self.assertRaises(RuntimeError):
            camera.get_rtsp_url()

    def test_geturl_good_auth_inject(self, onvifmock):
        """Credentials are inserted into the returned URL if not provided by the camera."""
        camera = IPCamera('192.0.2.123', 9160, 'root', 'hunter2')

        mediamock = Mock()
        mediamock.GetStreamUri.return_value = {'Uri': 'rtsp://192.0.2.123/some/video/endpoint'}
        camera.media_service = mediamock

        self.assertEqual(
            camera.get_rtsp_url(),
            'rtsp://root:hunter2@192.0.2.123/some/video/endpoint'
        )

    def test_geturl_good_auth_provided(self, onvifmock):
        """Credentials are not overwritten if providfed by camera."""
        camera = IPCamera('192.0.2.123', 9160, 'root', 'hunter2')

        mediamock = Mock()
        mediamock.GetStreamUri.return_value = {
            'Uri': 'rtsp://camera:creds@192.0.2.123/some/video/endpoint'
        }
        camera.media_service = mediamock

        self.assertEqual(
            camera.get_rtsp_url(),
            'rtsp://camera:creds@192.0.2.123/some/video/endpoint'
        )
