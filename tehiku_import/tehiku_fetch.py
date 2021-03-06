import mutagen
from mutagen.id3 import ID3, APIC
import requests
from datetime import datetime, timedelta
import time
import pytz
from math import floor
import json
import re
from subprocess import Popen, PIPE
import argparse
import os
import sys
from tempfile import NamedTemporaryFile

from tehiku_import.import_functions import scale_media
from tehiku_import.settings import BASE_MEDIA_DIR, MD5_CMD
from tehiku_import.add_artwork import add_artwork

timezone = pytz.timezone("Pacific/Auckland")
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--collection", help="Collection slug name, separated by comma.")
parser.add_argument("-a", "--am-pm", help="Whether to write file with AM/PM", action="store_true")
parser.add_argument("-d", "--daily", help="Whether to overwrite file with latest", action="store_true")
parser.add_argument("-r", "--remove-after-days", help="Remove file if it's older than X days.")
parser.add_argument("-n", "--get-n-items", help="Download n latests items")
parser.add_argument("-l", "--label", help="Label to apply to the file.")
parser.add_argument("-t", "--target-length", help="Duration in seconds that the file should be")
parser.add_argument("-x", "--delete", help="Delete files that match.", action="store_true")

args = parser.parse_args()

timezone = pytz.timezone("Pacific/Auckland")
STORE = os.path.join(BASE_MEDIA_DIR,'tehiku_fetch_data.json')

def convert_audio(file_path):
    outfile = '.'.join( file_path.split('.')[:-1] )+'.mp3'
    cmd = ['ffmpeg', '-y', '-i', file_path, '-c:a', 'libmp3lame', '-b:a', '192k', outfile]
    print(cmd)
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    Popen(['rm', file_path])
    return outfile

def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset

def store_hash(md5):
    data = {}
    if os.path.exists(STORE):
        with open(STORE, 'r') as file:
            data = json.loads(file.read())

    data[md5] = True
    with open(STORE, 'w') as file:
        file.write(json.dumps(data))


def hash_exists(md5):
    if os.path.exists(STORE):
        with open(STORE, 'r') as file:
            data = json.loads(file.read())
            if md5 in data:
                return True
    return False


def get_root_dir():
    ROOT_DIR = os.path.join(BASE_MEDIA_DIR, 'whare_korero')
    if not os.path.exists(ROOT_DIR):
        os.mkdir(ROOT_DIR)
        p = Popen(['chown', 'www-data', ROOT_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['chgrp', 'www-data', ROOT_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate() 
    return ROOT_DIR


def get_item_from_collection(
        collection, num_items=40, expire=7, ampm=False, daily=False,
        label='', duration=None, delete=False):
    
    ROOT_DIR = get_root_dir()

    collection_url = 'https://tehiku.nz/api/?collection={0}'.format(collection)

    r = requests.get(collection_url)
    collection = r.json()
    pub_ids = collection['publications'][0:num_items]

    # Use watch for files with metadata. Use store to keep original file hashes
    
    count = 0
    while count < num_items:
        count = count + 1
        try:
            pub_id = pub_ids.pop(0)
        except:
            break
        DOWNLOAD = False
        pub_url = 'https://tehiku.nz/api/?publication_id={0}'.format(pub_id)
        r = requests.get(pub_url)
        publication = r.json()

        publish_date = datetime.fromisoformat(publication['publish_date'].replace('Z','.000000+00:00'))
        # publish_date = pytz.utc.localize(publish_date)
        # Different file name strategy
        if daily:
            file_name = "tehiku_{0}".format(collection['id'])
        elif ampm:
            local_time = publish_date.astimezone(timezone)
            file_name = "tehiku_{0}_{1}".format(collection['id'], local_time.strftime('%p'))
            publication['headline'] = ' '.join([
                collection['name'].title(),
                local_time.strftime('%p'),
                local_time.strftime('%A')])
        else:
            file_name = "tehiku_{0}_{1}".format(collection['id'], pub_id)
        print(file_name)

        extension = 'None'
        try:
            file_url = publication['media'][0]['media_file']
            extension = file_url.split('.')[-1]
            if extension not in 'mp4 m4a mp3 wav ogg aiff':
                # What about video files?
                print('Not an audio file.')
                continue
        except:
            print('No media file, skipping.')
            continue
        file_extension = file_url.split('.')[-1]

        file_path = os.path.join(ROOT_DIR, "{0}.{1}".format(file_name, file_extension))

        now = pytz.utc.localize(datetime.utcnow())
        # Check if file exists

        if not os.path.isfile(file_path):
            converted_file = '.'.join(file_path.split('.')[0:-1])+'.mp3'
            if os.path.isfile(converted_file):
                file_path = converted_file

        if os.path.isfile(file_path):
            # Check if we should delete it
            if now - publish_date > timedelta(days=expire) or delete:
                # Remove old item
                p = Popen(['rm',file_path], stdin=PIPE, stdout=PIPE)
                output, error = p.communicate()
                if error:
                    print("Error removing old file.")
                continue
            elif now - publish_date <= timedelta(days=expire):
                # Check file hasn't changed
                p = Popen(['curl', '-s','-I',file_url], stdin=PIPE, stdout=PIPE)
                output, error = p.communicate()

                m = re.search(r'last-modified: ([\w|,| |:]+)', str(output))
                last_modifed = pytz.utc.localize(
                    datetime.strptime(m.groups()[0], '%a, %d %b %Y %H:%M:%S %Z'))

                file_timestamp = pytz.utc.localize(
                    datetime.utcfromtimestamp(os.path.getmtime(file_path)))
  
                if last_modifed > file_timestamp:
                    print('File needs updating.')
                    DOWNLOAD = True
                else:
                    print('File exists')
                    continue
            else:
                print('Strange edge case')
                continue
        else:
            if now - publish_date < timedelta(days=expire) and not delete:
                DOWNLOAD = True

        if DOWNLOAD:
            ntf = NamedTemporaryFile(delete=False, suffix=f'.{extension}')
            tmp_file = ntf.name

            cmd = ['curl', '-s', '-L', file_url, '-o', tmp_file]
            p = Popen(cmd, stdin=PIPE, stdout=PIPE)
            output, error = p.communicate()
            if error:
                print("Could not download file")

            if extension not in 'flac mp3':
                # Convert to mp3
                tmp_file = convert_audio(tmp_file)

            if duration:
                scale_media(tmp_file, duration)

            p = Popen(['chown', 'www-data', tmp_file], stdin=PIPE, stdout=PIPE)
            p.communicate()
            p = Popen(['chgrp', 'www-data', tmp_file], stdin=PIPE, stdout=PIPE)
            p.communicate()

            fd = mutagen.File(tmp_file, easy=True)

            try:
                fd.tags['DATE'] = publish_date.strftime('%Y')
            except:
                pass
            try:
                fd.tags['Title'] =  publication['headline']
            except:
                pass
            try:
                fd.tags['Language'] =  publication['media'][0]['primary_language']
            except:
                pass
            fd.tags['Album'] = collection['name']
            fd.tags['Artist'] = "Te Hiku Media"
            if label:
                fd.tags['Organization'] = label
            fd.tags['Genre'] = "Whare Kōrero"
            fd.save()

            # Try to embed picture
            # https://stackoverflow.com/questions/37897801/embedding-album-cover-in-mp4-file-using-mutagen
            add_artwork(publication['image_thumb_small'], tmp_file)

            # Finally move the file to where it needs to be
            Popen(['mv', tmp_file, file_path])
            

def main():
    prepare_folders()
    if args.get_n_items:
        NUM_GET = int(args.get_n_items)
    else:
        NUM_GET = 40

    if args.remove_after_days:
        EXPIRE = int(args.remove_after_days)
    else:
        EXPIRE = 7

    if args.am_pm:
        NUM_GET = 1

    if args.daily:
        NUM_GET = 1

    if args.target_length:
        DURATION = int(args.target_length)
    else:
        DURATION = None

    if args.label:
        label = args.label
    else:
        label = ''

    if args.collection:
        slugs = args.collection.split(',')
        for slug in slugs:
            get_item_from_collection(
                slug, num_items=NUM_GET,
                expire=EXPIRE,
                ampm=args.am_pm,
                daily=args.daily,
                duration=DURATION,
                label=label,
                delete=args.delete)
    else:
        print("Must specify collection name.")

    sys.exit(0)

def prepare_folders():
    # setup_folders
    if not os.path.exists(BASE_MEDIA_DIR):
        os.mkdir(BASE_MEDIA_DIR)
        p = Popen(['chown', 'www-data', BASE_MEDIA_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['chgrp', 'www-data', BASE_MEDIA_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()   


if __name__ == "__main__":    
    main()
