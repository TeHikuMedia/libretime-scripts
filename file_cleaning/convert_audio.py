'''
Converts audio from bad formats to better ones. That's subject btw.

'''

import os
import logging
import json
from subprocess import Popen, PIPE, call

# m4a doesn't allow a language tag.
BAD_FORMATS = 'wav mpg wave aiff m4a'

CONF_FILE = "/etc/librescripts/conf.json"
ROOT_FOLDER = "/usr/ubuntu/sync/TeHikuRadioDB"
ROOT_FOLDER = "/Users/livestream/Desktop/DESKTOP 2/desktop/Te Hiku Radio Database"
LOGFILE= "/var/log/librescripts/update_metadata.log"

logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO,
    filename=LOGFILE,
)


# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    ROOT_FOLDERS = d['search_folders']
except KeyError as e:
    logging.error('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    logging.error('Could not read configuration file {0}.'.format(CONF_FILE))
    raise


def scan_folder(ROOT_FOLDER):
    NUM_FILES = 0
    CON_FILES = 0
    for root, dirs, files in os.walk(ROOT_FOLDER):
        for name in files:
            extension = name.split('.')[-1].lower()
            FILE_PATH = os.path.join(root, name)

            if '.' is name[0]:
                logging.debug('Skipping {0}'.format(name))
                continue
            elif '#Trash' in root:
                continue
            elif extension not in 'mp3 mp4 m4a flac wav ogg mpg':
                logging.debug('Skipping {0}'.format(name))
                continue
            
            NUM_FILES = NUM_FILES + 1

            if extension in BAD_FORMATS:
                logging.info("Converting {0} to flac".format(FILE_PATH.encode('utf-8')))
                out_file = name.split('.')
                out_file[-1] = 'flac'
                out_file = '.'.join(out_file)
                cmd = [
                    'ffmpeg', '-y', '-v', 'quiet',
                    '-i', FILE_PATH,
                    '-c:a', 'flac', os.path.join(root, out_file)
                ]

                p = Popen(cmd, stdout=PIPE, stderr=PIPE)
                out, err = p.communicate()
                
                if os.path.exists(FILE_PATH):
                    logging.info("Converted {0} -> {1}".format(name.encode('utf-8'), out_file.encode('utf-8')))
                    CON_FILES = CON_FILES + 1
                    # Move old file to #Trash
                    trash = os.path.join(ROOT_FOLDER, '#Trash', root)
                    if not os.path.exists(trash):
                        os.mkdir(trash)
                    call(['mv', FILE_PATH, os.path.join(trash, name)])
                else:
                    logging.warning("Did not convert {0}".format(name.encode('utf-8')))

            
        

    logging.info("Converted {0}/{1} files in {2}".format(CON_FILES, NUM_FILES, ROOT_FOLDER))


def main():
    for folder in ROOT_FOLDERS:
        logging.info('Scanning {0}'.format(folder))
        scan_folder(folder)


if __name__ == "__main__":
    main()
