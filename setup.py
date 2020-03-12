from setuptools import setup, find_packages
import os
from subprocess import call

script_path = os.path.dirname(os.path.realpath(__file__))
print(script_path)
os.chdir(script_path)

data_files = [
    ('/etc/librescripts',     ['install/conf/conf.json']),
    #('/etc/cron.d',           ['install/cron/update_metadata']),
    ('/etc/cron.d',           [
        'install/cron/tehiku_import',]),
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
    version="0.2",
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
            "tehiku-fetch = tehiku_import.tehiku_fetch:main",
        ]
    },
    data_files=data_files
)

# Update permissions for cron
for file in data_files:
    path = file[0]
    if 'cron.d' in path:
        for name in file[1]:
            file_name = name.split('/')[-1]
            file_path = os.path.join(path, file_name)
            print('Modifying {0}'.format(file_path))
            call(['chmod', '644', file_path])
