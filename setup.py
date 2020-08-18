from setuptools import setup, find_packages
from setuptools.config import read_configuration
import stat
import os
import pwd
import grp
from subprocess import call

script_path = os.path.dirname(os.path.realpath(__file__))
print(script_path)
os.chdir(script_path)

data_files = [
    ('/etc/librescripts',     ['install/conf/conf.json']),
    #('/etc/cron.d',           ['install/cron/update_metadata']),
    ('/etc/init.d', [
        'install/sysvinit/schedule_stream_target',
    ]),
    ('/etc/init',[
        'install/upstart/schedule_stream_target.conf'
    ]),
    ('/etc/cron.d', [
        'install/cron/tehiku_import',
        'install/cron/update_metadata'
    ]),
]

LOG_DIR  = '/var/log/librescripts'
LOG_FILE = os.path.join(LOG_DIR, 'update_metadata.log')
# Make sure log directory exists
if not os.path.exists(LOG_DIR):
    os.mkdir(LOG_DIR)
    os.chmod(LOG_DIR, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    uid = pwd.getpwnam("www-data").pw_uid
    gid = grp.getgrnam("www-data").gr_gid
    os.chown(LOG_DIR, uid, gid)

if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'a').close()
    os.chmod(LOG_FILE, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)

conf_dict = read_configuration("setup.cfg")

setup(
    name="libretime_scripts",
    version="0.2.2",
    author="@kmahelona",
    description="A collection of scripts to help with automated ingesting of media to LibreTime",
    packages=find_packages(),
    install_requires=[
        "mutagen",
        "Pillow",
        "pilkit",
        'colorthief',
        's3cmd',
        'pexpect',
        'boto3',
        'pyyaml',
        'requests',
        'pytz',
    ],
    entry_points={
        "console_scripts": [
            "radio-db-metadata-sync = radio_database_sync.update_metadata:main",
            "waatea-fetch = tehiku_import.waatea_import:main",
            "tehiku-fetch = tehiku_import.tehiku_fetch:main",
            "radio-db-actions = radio_database_sync.db_management:main",
            "schedule-stream-target = remote_streams.schedule_stream_target:main",
            "ingest-youtube = remote_streams.ingest:main"
        ]
    },
    data_files=conf_dict['options']['data_files']
)

# Update permissions for cron
for file in conf_dict['options']['data_files']:
    path = file[0]
    if 'cron.d' in path:
        for name in file[1]:
            file_name = name.split('/')[-1]
            file_path = os.path.join(path, file_name)
            print('Modifying {0}'.format(file_path))
            # call(['chmod', '644', file_path])
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
