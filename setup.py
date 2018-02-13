from setuptools import setup, find_packages

setup(
    name='maho',

    version='0.0.1',

    description='Spot aircraft with ADS-B and a PTZ IP camera',

    url='https://github.com/cnelson/maho',

    author='Chris Nelson',
    author_email='cnelson@cnelson.org',

    license='Public Domain',

    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',

        'License :: Public Domain',

        'Programming Language :: Python :: 3',
    ],

    keywords='dump1090 rtlsdr adsb ads-b onvif webcam camera aircraft',

    packages=find_packages(),

    install_requires=[
        'onvif-zeep',
        'pyModeS',
        'expiringdict',
        'opencv-python'
    ],

    # tests_require=[
    #     'mock'
    # ],

    test_suite='maho.tests',

    entry_points={
        'console_scripts': [
            'maho = maho.cli:main'
        ]
    }
)
