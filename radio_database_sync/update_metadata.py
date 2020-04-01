import os
import re
import mutagen
import logging
import json
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC
import mutagen
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import HeaderNotFoundError
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbisHeaderError
from mutagen.flac import FLACNoHeaderError


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
    for root, dirs, files in os.walk(ROOT_FOLDER):
        # if '#' in root:
        #     continue
        # print(root, dirs, files)
        for name in files:
            NUM_FILES = NUM_FILES + 1
            # print("Checking {0} :: {1}".format(root,name))

            # folders = root.split('/')
            # for folder in folders:
            #     if folder:
            #         if folder[0] in "~!#.?":
            #             # print(folder)
            #             logging.info('Skipping {0}/{1}'.format(root,name))
            #             continue

            if '.' is name[0]:
                logging.debug('Skipping {0}'.format(name))
                continue
            elif name[0] in "~!#.?":
                logging.debug('Skipping {0}'.format(name))
                continue
            elif name.split('.')[-1].lower() not in 'mp3 mp4 m4a flac wav ogg':
                logging.debug('Skipping {0}'.format(name))
                continue

            parts = root.split('/')

            RELATIVE = root.split(ROOT_FOLDER)[1]
            
            parts = RELATIVE.split('/')
            parts.pop(0)

            SKIP_DIR = False
            for part in parts:
                if part:
                    if part[0] == '.':
                        logging.debug("Skipping folder {0}:{1}".format(part, name))
                        SKIP_DIR = True
            if SKIP_DIR:
                continue

            try:
                label = parts[0]
            except IndexError as e:
                logging.warning('File not properly organized: {0}'.format(name))
                continue

            try:
                language = parts[1]
            except IndexError as e:
                language = None
                logging.warning('File not in language folder: {0}'.format(os.path.join(RELATIVE, name)))
                continue

            try:
                genre = parts[2]
            except IndexError as e:
                genre = None
                logging.debug('File not in genre folder: {0}'.format(os.path.join(RELATIVE, name)))

            if '#' in root:
                try:
                    m = re.findall(r'\/(#[^\/]*)', root)
                # print(m)
                    exclude = m[-1]
                    label = label + ' :: ' + exclude
                except:
                    print(root)

                    raise error
                # print(label)
                # raise error

            try:
                audio = mutagen.File(os.path.join(root, name), easy=True)
            except Exception as e:
                logging.warning('Could not load file with mutagen: {0}'.format(name))
                continue

            try:
                logging.debug("UPDATE:  {0}".format(' '.join(audio['title'].encode('utf-8'))))
            except:
                logging.debug("UPDATE:  {0}".format(name.encode('utf-8')))
            logging.debug('TAGS:    {0}'.format(audio))


            SAVE = False
            if audio:

                # TAG: LANGUAGE
                try:
                    l = audio['language']
                except KeyError:
                    l = []
                if language:
                    vowels = (
                        ('ā', 'ē', 'ī', 'ō', 'ū', 'Ā', 'Ē', 'Ī', 'Ō', 'Ū'),
                        ('ā', 'ē', 'ī', 'ō', 'ū', 'Ā', 'Ē', 'Ī', 'Ō', 'Ū')
                    )
                    for i in range(len(vowels[0])):
                        if vowels[0][i] in language:
                            language = language.replace(vowels[0][i], vowels[1][i])

                    if [language] != l:
                        l = [language]
                        try:
                            audio.tags['language'] = l
                        except:
                            try:
                                audio.tags['language'] = language
                            except Exception as e:
                                logging.warning("Could now write 'langauge' to {0}".format(name))
                                continue
                        SAVE = True
                    logging.debug("LANG:    {0}".format(l))

                # TAG: LABEL (AKA ORGANIZATION)
                try:
                    t = audio['label']
                except KeyError:
                    try:
                        t = audio['organization']
                    except KeyError:
                        t = []
                # Overwrite label field
                if [label] != t:
                    t = [label]
                    SAVE = True
                logging.debug("LABEL:   {0}".format(t))
                if SAVE:
                    try:
                        audio.tags['label'] = t
                    except KeyError:
                        pass
                    audio.tags['organization'] = t

                # TAG: GENRE
                try:
                    g = audio['genre']
                except KeyError:
                    g = []

                if genre:
                    if [genre] != g:
                        SAVE = True
                        g = [genre]
                        logging.debug("GENRE:   {0}".format(t))
                        audio.tags['genre'] = g

                if SAVE:
                    logging.info(
                        (u"Updating {0}\n\tTAGS:\t{1}\n\tLANG:\t{2}\n\tGENRE\t{3}\n\tLABEL\t{4}"\
                            .format(name, audio, l, g, t)))
                    audio.save()

                logging.debug(audio)


    logging.info("Scanned {0} files in {1}".format(NUM_FILES, ROOT_FOLDER))


def main():
    for folder in ROOT_FOLDERS:
        logging.info('Scanning {0}'.format(folder))
        scan_folder(folder)


if __name__ == "__main__":
    main()
