import argparse
import multiprocessing
import queue
import time

from maho.camera import IPCamera
from maho.adsb import Dump1090
from maho.util import AzimuthAltitudeDistance

import numpy as np
import cv2


def camera_control(camera_host, camera_port, camera_user, camera_pass, q):
    """Control a maho.Camera based on inputs from a multiprocessing queue"

        On startup this function will place the stream_url in the queue if camera
        communication works.
        If it fails the exception for why will be placed in the queue before exiting
    """

    try:
        camera = IPCamera(camera_host, camera_port, camera_user, camera_pass)
        q.put(camera.get_rtsp_url())
    except RuntimeError as exc:
        q.put(exc)

    try:
        while True:
            camera.move_to(*q.get())
    except KeyboardInterrupt:
        pass


def track_closest_aircraft(latitude, longitude, elevation, host, port, q):
    """Forward adsb messages to a Queue

    Args:
        host (str): The dump1090 host
        port (int): The dump1090 port
        q (queue): Messages will be placed in this queue

        On startup this function will place True in the queue if dump1090 starts properly
        If it fails the exception will be placed in the queue before exiting
    """
    try:
        d = Dump1090(host, port)
        q.put(True)
    except IOError as exc:
        q.put(exc)
        return

    target = None
    target_distance = None
    aad = AzimuthAltitudeDistance(latitude, longitude, elevation)

    try:
        for aircraft in d.updates():
            lat, lng = aircraft.position
            azimuth, altitude, distance = aad.calculate(
                lat,
                lng,
                aircraft.altitude
            )

            # if we don't have a target we do now
            # or target is old, then use this new aircraft
            # or new aircraft isn't the target, but it is closer, so we switch!
            if (target is None or target.age > 60 or
                    (target.icao != aircraft.icao and distance < target_distance)):
                target = aircraft

            # if we aren't the target at this point then bail
            if target.icao != aircraft.icao:
                continue

            target = aircraft
            target_distance = distance
            q.put((target, azimuth, altitude, distance))
    except KeyboardInterrupt:
        pass


def go_maho(
    latitude,
    longitude,
    elevation,
    camera_host,
    camera_port,
    camera_user,
    camera_pass,
    adsb_host,
    adsb_port,
):

    # fork a process to communicate with dump1090
    targets = multiprocessing.Queue()
    tracker = multiprocessing.Process(
        target=track_closest_aircraft,
        args=(latitude, longitude, elevation, adsb_host, adsb_port, targets,)
    )
    tracker.start()

    # fist thing in the queue will be startup status
    # True if good
    # an Exception if bad
    status = targets.get()
    if isinstance(status, Exception):
        raise RuntimeError("Unable to connect to dump1090 on {}:{}: {}".format(
            adsb_host,
            adsb_port,
            status
        ))

    # run camera control in own process as moving the camera can block for seconds
    camera_queue = multiprocessing.Queue()
    camera = multiprocessing.Process(
        target=camera_control,
        args=(camera_host, camera_port, camera_user, camera_pass, camera_queue,)
    )
    camera.start()

    # fist thing in the queue will be startup status
    # Stream URL if good
    # an Exception if bad
    stream_url = camera_queue.get()
    if isinstance(stream_url, Exception):
        raise RuntimeError("Unable to connect to camera on {}:{}: {}".format(
            camera_host,
            camera_port,
            stream_url
        ))

    cap = cv2.VideoCapture(stream_url)
    ret, frame = cap.read()

    cv2.namedWindow("maho")

    orb = cv2.ORB_create()

    # build a mask that's the center of the frame
    # we'll focus searching for aircraft in this region
    search_mask = np.zeros((frame.shape[0], frame.shape[1], 1), dtype=np.uint8)
    cx = frame.shape[1] / 2
    cy = frame.shape[0] / 2

    size = 0.33

    search_rect = (
        (int(cy - (cy * size)), int(cx - (cx * size))),
        (int(cy + (cy * size)), int(cx + (cx * size)))
    )

    # openCV UI main loops
    start = None
    end = None
    fps = 0
    elapsed = 0

    target = None
    last_target = None
    try:
        while True:
            start = time.time()

            # fill our mask back to full, we may have chopped it smaller on the last frame
            search_mask[
                search_rect[0][0]:search_rect[0][1],
                search_rect[1][0]:search_rect[1][1]
            ] = 255

            # grab a frame from the camera
            ret, frame = cap.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # check for new / updated target info
            try:
                target, azimuth, altitude, distance = targets.get(False)
                if last_target is None or target.icao != last_target.icao:
                    last_target = target

                    print("Now tracking {} / {} - Distance: {}m".format(
                        target.icao,
                        target.callsign,
                        int(distance)
                    ))

                print("{} | azi: {:.3f}, alt: {:.3f}, dist: {}m.".format(
                    target,
                    azimuth,
                    altitude,
                    int(distance)
                ))

                camera_queue.put((azimuth, altitude))
            except queue.Empty:
                pass

            # annotate the frame
            if target:
                cv2.putText(
                    frame,
                    target.callsign or target.icao,
                    (0, 50),
                    cv2.FONT_HERSHEY_DUPLEX,
                    2,
                    (255, 255, 255),
                    4,
                    cv2.LINE_AA
                )

                txt = "{0:.3f}, {1:.3f} @ {2:.0f}m (dist: {3:.0f}m)".format(
                    target.position[0],
                    target.position[1],
                    target.altitude,
                    distance
                )
                cv2.putText(
                    frame,
                    txt,
                    (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    .5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )

                cv2.rectangle(frame, search_rect[0][::-1], search_rect[1][::-1], (0, 0, 255), 2)

                kp = orb.detect(gray, search_mask)
                kp, des = orb.compute(gray, kp)
                cv2.drawKeypoints(frame, kp, frame, color=(0, 255, 0), flags=0)

                cv2.putText(
                    frame,
                    "fps: {0:02d} ({1:03d} ms)".format(fps, elapsed),
                    (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    .5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )
                cv2.putText(
                    frame,
                    "Camera Position: Az: {:.0f}, Alt: {:.0f}".format(azimuth, altitude),
                    (10, 125),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    .5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )

            # display it
            cv2.imshow('maho', frame)

            # handle input
            keypress = cv2.waitKey(1) & 0xFF

            end = time.time()
            elapsed = int((end - start) * 1000)
            fps = int(1000 / elapsed)

            if keypress == ord('q'):
                raise KeyboardInterrupt

    except KeyboardInterrupt:
        tracker.terminate()
        tracker.join()

        camera.terminate()
        camera.join()

        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        prog='maho',
        description='ADS-B asdisted aircraft spotting',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--latitude', type=float, required=True, help='Latitude of the camera')
    parser.add_argument('--longitude', type=float, required=True, help='Longitude of the camera')
    parser.add_argument('--elevation', type=float, required=True, help='Elevation of the camera')

    parser.add_argument('--camera-host', type=str, required=True, help='Camera hostname/ip')
    parser.add_argument('--camera-port', type=int, default=80, help='Camera port')

    parser.add_argument('--camera-user', type=str, required=True, help='Camera username')
    parser.add_argument('--camera-pass', type=str, required=True, help='Camera password')

    parser.add_argument('--adsb-host', type=str, default='localhost', help='dump1090 hostname/ip')
    parser.add_argument('--adsb-port', type=int, default=30002, help='dump1090 TCP raw output port')

    args = parser.parse_args()

    try:
        go_maho(
            args.latitude,
            args.longitude,
            args.elevation,
            args.camera_host,
            args.camera_port,
            args.camera_user,
            args.camera_pass,
            args.adsb_host,
            args.adsb_port
        )
    except KeyboardInterrupt:
        pass
    except RuntimeError as exc:
        parser.error(exc)
        raise SystemExit


if __name__ == "__main__":
    main()
