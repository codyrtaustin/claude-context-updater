"""
Setup script for building TranscriptSync.app
Run: python3 setup_app.py py2app
"""

from setuptools import setup

APP = ['TranscriptSync.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'TranscriptSync',
        'CFBundleDisplayName': 'TranscriptSync',
        'CFBundleIdentifier': 'com.claude.transcriptsync',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': False,  # Set to True if you want menu-bar only (no dock icon)
        'NSHighResolutionCapable': True,
    },
    'packages': ['rumps'],
    'includes': ['rumps'],
}

setup(
    app=APP,
    name='TranscriptSync',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
