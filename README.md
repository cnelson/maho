# maho: ADS-B assisted aircraft spotting

A proof of concept application for aircraft spotting using positional data from ADS-B
 and a PTZ IP camera.
 
 ![asa311](https://user-images.githubusercontent.com/604163/36133796-76b08af6-1035-11e8-912a-9106d85e6927.jpg)


This application receives aircraft position updates via ADS-B, calculates the azimuth
and altitude to the aircraft from the camera's position and instructs the camera to
point at that location.

Very basic image analysis is then performed on the video stream from the camera
to highlight the aircraft.

# How to use

In order to use this application you need the following:

## PTZ IP Camera

* The camera must support the ONVIF protocol and ptz.AbsoluteMove.
* The camera must be positioned level and facing north.
* The camera should have a full view of the sky.
* You must know the latitude, longitude, and elevation of the camera.

## ADS-B receiver

This application depends on [dump1090](https://github.com/mutability/dump1090) to decode ADS-B.
Install it and run with `--net` to enable networking.

## This software
Install it with:

```bash
pip install https://github.com/cnelson/maho/archive/master.zip
```

Run it:

```bash
maho \
--latitude :camera-latitude: \
--longitude :camera-longitude: \
--elevation :camera-elevation-in-meters: \
--camera-host :camera-host-or-ip \
--camera-port :camera-onvif-port: \
--camera-user :camera-username: \
--camera-pass :camera-password: \
--adsb-host :host-running-dump1090: \
--adsb-port :dump1090-raw-tcp-port:
```

# Caveats

* This application was written in an afternoon, it is not suitable for any production use.
* Some tests exist but code coverage is poor.
* Expect false positives from image analysis especially if the aircraft is near the horizon, or
the sky is very cloudy.

