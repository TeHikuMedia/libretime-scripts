import os
import mutagen
import magic
import logging
import json
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC
import mutagen
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import HeaderNotFoundError
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


def load_file_tagging(file_path):

    # MIME = 'NONE'
    # with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
    #     MIME = m.id_filename(file_path)

    # # Mp3
    # if MIME in ['audio/mpeg','audio/mp3', 'application/octet-stream']:
    #     try:
    #         audio = EasyID3(file_path)
    #         f = MP3(file_path)
    #     except (ID3NoHeaderError, HeaderNotFoundError) as e:
    #         logging.warning("MP3 without Metadata: {}".format(file_path))
    #         return None, None
    # # Ogg
    # elif MIME in ['audio/ogg', 'audio/vorbis', 'audio/x-vorbis', 'application/ogg', 'application/x-ogg']:
    #     try:
    #         audio = OggVorbis(file_path)
    #         f = audio
    #     except OggVorbisHeaderError:
    #         logging.warning("OGG without Metadata: {}".format(file_path))
    #         return None, None
    # # flac
    # elif MIME in ['audio/flac', 'audio/flac-x']:
    #     try:
    #         audio = FLAC(file_path)
    #         f = audio
    #     except FLACNoHeaderError:
    #         logging.warning("FLAC without Metadata: {}".format(file_path))
    #         return None, None
    # else:
    #     logging.warning("Unsupported mime type: {} -- for audio {}".format(MIME, file_path))
    #     return None, None

    audio = mutagen.File(file_path, easy=True)
    return audio, f
  
def scan_folder(ROOT_FOLDER):
    NUM_FILES = 0
    for root, dirs, files in os.walk(ROOT_FOLDER):
        for name in files:
            NUM_FILES = NUM_FILES + 1
            # print("Checking {0}".format(os.path.join(root,name)))

            if '.' is name[0]:
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
                logging.info('File not properly organized: {0}'.format(name))
                continue

            try:
                language = parts[1]
            except IndexError as e:
                language = None
                logging.info('File not in language folder: {0}'.format(os.path.join(RELATIVE, name)))

            try:
                genre = parts[2]
            except IndexError as e:
                genre = None
                logging.info('File not in genre folder: {0}'.format(os.path.join(RELATIVE, name)))



            # audio, f = load_file_tagging(os.path.join(root, name))
            audio = mutagen.File(os.path.join(root, name), easy=True)

            try:
                logging.debug("UPDATE:  {0}".format(' '.join(audio['title'])))
            except:
                logging.debug("UPDATE:  {0}".format(name))
            logging.debug('TAGS:   {0}'.format(audio))


            SAVE = False
            if audio:

                # TAG: LANGUAGE
                try:
                    l = audio['language']
                except KeyError:
                    l = []
                if language not in l:
                    l.insert(0,language)
                    audio['language'] = language
                    SAVE = True
                logging.debug("LANG:    {0}".format(language))


                # TAG: LABEL (AKA ORGANIZATION)
                try:
                    t = audio['label']
                except KeyError:
                    try:
                        t = audio['organization']
                    except KeyError:
                        t = []
                if label not in t:
                    t.insert(0, label)
                    SAVE = True
                # Remove genre from label
                if genre in t:
                    t.remove(genre)
                    SAVE = True
                logging.debug("LABEL:   {0}".format(t))
                if SAVE:
                    try:
                        audio['label'] = t
                    except KeyError:
                        pass
                    audio['organization'] = t


                # TAG: GENRE
                try:
                    g = audio['genre']
                except KeyError:
                    g = []

                if genre:
                    if genre not in g:
                        SAVE = True
                        g.insert(0, genre)
                        logging.debug("GENRE:   {0}".format(t))
                        audio['genre'] = g

                if SAVE:
                    logging.info("Updating {0}\n\tTAGS:\t{1}\n\tLANG:\t{2}\n\tGENRE\t{3}\n\tLABEL\t{4}".format(name, audio, l, g, t))
                    audio.save()


    logging.info("Scanned {0} files in {1}".format(NUM_FILES, ROOT_FOLDER))


def main():
    for folder in ROOT_FOLDERS:
        logging.info('Scanning {0}'.format(folder))
        scan_folder(folder)


if __name__ == "__main__":
    main()
