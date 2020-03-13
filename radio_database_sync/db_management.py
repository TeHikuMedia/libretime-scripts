import json
import logging
import argparse
import sys
from datetime import datetime
import pytz
from subprocess import Popen, PIPE, check_output
from pwd import getpwnam  
from grp import getgrnam
import os

from radio_database_sync.settings import CONF_FILE


parser = argparse.ArgumentParser()
parser.add_argument("-b", "--backup", help="Collection slug name, separated by comma.", action="store_true")
parser.add_argument("-X", "--DELETE", help="Delete the current db.", action="store_true")
args = parser.parse_args()


# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    ROOT_FOLDERS = d['search_folders']
    LOGFILE = os.path.join(d['log_path'], 'db.mgmt.log')
    TMP_DIR = d['tmp_dir']
    S3_BUCKET = d['aws']['s3_bucket']
    AWS_ACCESS_KEY = d['aws']['access_key']
    AWS_SECRET_KEY = d['aws']['secret_key']
    SLUG = d['project_slug']
except KeyError as e:
    print('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    print('Could not read configuration file {0}.'.format(CONF_FILE))
    raise

logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO,
    filename=LOGFILE,
)

timezone = pytz.timezone("Pacific/Auckland")

def prepare_dir(path):
    if not os.path.exists(path):
        os.mkdir(path)

def change_user(user='postgres'):
    UID = getpwnam("postgres").pw_uid
    GID = getgrnam("postgres").gr_gid
    os.setgid(GID)
    os.setuid(UID)


def backup():
    change_user('postgres')
    time = datetime.now()
    time = time.astimezone(timezone)
    prepare_dir(TMP_DIR)
    file_name = 'libretime-backup-{0}.gz'.format(time.strftime('%a').upper())
    tmp_file = os.path.join(TMP_DIR, file_name)
    p1 = Popen(['pg_dumpall'], stdout=PIPE)
    p2 = Popen(['gzip', '-c'], stdin=p1.stdout, stdout=PIPE)
    p1.stdout.close()
    p3 = Popen(['tee', tmp_file], stdin=p2.stdout, stdout=PIPE)
    p2.stdout.close()
    output, error = p3.communicate()
    output = check_output([
        's3cmd', 'sync', tmp_file, os.path.join(S3_BUCKET, SLUG, file_name),
        '--region', 'ap-southeast-2',
        '--access_key', AWS_ACCESS_KEY, '--secret_key', AWS_SECRET_KEY
    ])
    print(output)


def main():
    if args.backup:
        backup()
    elif args.DELETE:
        delete()

    sys.exit(0)

'''
FILENAME="$(date +%a)"
sudo -u postgres pg_dumpall | gzip -c > libretime-backup-$FILENAME.gz
s3cmd sync libretime-backup-$FILENAME.gz s3://tehiku-airtime-bucket/tehiku_fm/tehiku_db_backup_$FILENAME.gz
'''



if __name__ == "__main__":
    main()
