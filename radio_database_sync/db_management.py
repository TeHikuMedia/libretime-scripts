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


def change_user(user='postgres'):
    UID = getpwnam("postgres").pw_uid
    GID = getgrnam("postgres").gr_gid
    os.setgid(GID)
    os.setuid(UID)


def backup():
    change_user('postgres')
    time = datetime.now()
    time = time.astimezone(timezone)
    tmp_file = os.path.join(TMP_DIR, 'libretime-backup-{0}.gz'.format(time.strftime('%a').upper()))
    p1 = Popen(['pg_dumpall'], stdout=PIPE)
    p2 = Popen(['gzip', '-c'], stdin=p1.stdout, stdout=PIPE)
    p1.stdout.close()
    p3 = Popen(['tee', tmp_file], stdin=p2.stdout)
    p2.stdout.close()
    output, error = p3.communicate()
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
