'''
Sometimes audio with VBR encoding have the issue of incorrectly reporting their duration. This
code attempts to identify these files and fix them.
'''

from subprocess import Popen, PIPE
from mutagen.easyid3 import EasyID3
import mutagen
import glob
import os
import json
from pathlib import Path
import logging


CONF_FILE = "/etc/librescripts/conf.json"
ROOT_FOLDER = "/usr/ubuntu/sync/TeHikuRadioDB"
ROOT_FOLDER = "/Volumes/Sunshine_Radio_Database/"
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


def main():
    for folder in ['Station ID/', 'Ads/', 'Kupu Hou/']:
        ROOT_FOLDER = "/Users/livestream/Resilio Sync/SunshineDB/"
        scan_folder(ROOT_FOLDER, folder)


def scan_folder(ROOT_FOLDER, folder):

    SEARCH_DIR = os.path.join(ROOT_FOLDER,  folder)
    DESTINATION_DIR = os.path.join(ROOT_FOLDER, '~WORKING/')

    print('Scanning {0}'.format(SEARCH_DIR))


    all_files_count = 0
    files_to_check_count = 0
    files_to_fix_count = 0
    replaced = 0
    for root, dirs, files in os.walk(SEARCH_DIR):

        for file in files:
            all_files_count = all_files_count + 1

            if file[0] == '.':
                continue
            elif file.split('.')[-1].lower() not in 'mp3 m4a mp4 wav flac':
                continue

            # print(file)

            source = os.path.join(root, file)
            BASE_OUT = root.replace(ROOT_FOLDER, DESTINATION_DIR)
            output = os.path.join(BASE_OUT, file)

            Path(BASE_OUT).mkdir(parents=True, exist_ok=True)

            # print(source)
            # print(output)

            cmd = [
                 'ffprobe',
                 '-i', source,
                 '-show_entries',
                 'format=size,duration:stream=codec_name,bit_rate',
                 '-v', 'quiet',
                 '-of', 'json']
             
            p = Popen(cmd, stdout=PIPE, stderr=PIPE)
            data, error = p.communicate()

            # print('Error: \t', error)

            data = json.loads(data)
            # print('Data:\t', data)


            if data['streams'][0]['codec_name'] != 'mp3':
                continue

            files_to_check_count = files_to_check_count + 1

            duration = float(data['format']['duration'])
            size = float(data['format']['size'])
            try:
                bit_rate = data['streams'][0]['bit_rate']
            except:
                bit_rate = '999999'
            
            try:
                if bit_rate[3:6] == '000':
                    continue
                else:
                    VBR = True
            except:
                pass

            
            files_to_fix_count = files_to_fix_count + 1
            print("{1:06d}bps :: {0}".format(file, int(bit_rate)))

            run = [
                'ffmpeg', '-y', 
                '-i', source,
                '-codec:a',
                'copy', 
                output]
            p = Popen(run, stdout=PIPE, stderr=PIPE)
            data, error = p.communicate()
            data = str(error)
            if data.find('Estimating duration from bitrate, this may be inaccurate') > 0:
                print("VBR!")
                # cmd = ['mv', output, source]
                # p = Popen(cmd, stdout=PIPE, stderr=PIPE)
                # data, error = p.communicate()
                # print("Moving {0} => {1}".format(output, source))
                # print(data, error)
                # replaced = replaced + 1


    print("Scanned:  {0}".format(all_files_count))
    print("Checked:  {0}".format(files_to_check_count))
    print("Fixed:    {0}".format(files_to_fix_count))
    print("Replaced: {0}".format(replaced))

if __name__ == "__main__":
    main()