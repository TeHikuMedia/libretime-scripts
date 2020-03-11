from setuptools import setup, find_packages
import os
from subprocess import call

script_path = os.path.dirname(os.path.realpath(__file__))
print(script_path)
os.chdir(script_path)

data_files = [
    ('/etc/librescripts',     ['install/conf/conf.json']),
    #('/etc/cron.d',           ['install/cron/update_metadata']),
]

LOG_DIR  = '/var/log/librescripts'
LOG_FILE = os.path.join(LOG_DIR, 'update_metadata.log')
# Make sure log directory exists
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'a').close()

setup(
    name="libretime_scripts",
    version="0.1",
    author="@kmahelona",
    description="A collection of scripts to help with automated ingesting of media to LibreTime",
    packages=find_packages(),
    install_requires=[
        "mutagen",
        "pytaglib",
    ],
    entry_points={
        "console_scripts": [
            "radio-db-metadata-sync = radio_database_sync.update_metadata:main",
            "waatea-fetch = tehiku_import.waatea_import:main",
            # "waatea-fetch-all = tehiku_import.waatea_import_all:main",
            # "tehiku-fetch = tehiku_import.tehiku_fetch:main",
        ]
    },
    data_files=data_files
)

# Update permissions for cron
call(['chmod', '644', '/etc/cron.d/update_metadata'])
