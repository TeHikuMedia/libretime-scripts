import argparse
import datetime
import hashlib
import itertools
import json
import logging
import mimetypes
import os
import re
import sys
from logging.handlers import TimedRotatingFileHandler
from subprocess import PIPE, Popen
from time import sleep
from unicodedata import normalize

import mutagen
import pytz
import requests
from mutagen.id3 import ID3, TIT2
from playwright.sync_api import expect, sync_playwright
from requests.auth import HTTPBasicAuth
from watchdog.events import RegexMatchingEventHandler
from watchdog.observers import Observer

CONF_FILE = "/etc/librescripts/conf.json"
LABEL_KEYS = ['genre', 'language', 'label', 'library']
REQUIRED = ['mime', 'accessed', 'name', 'size']

TRACKS = {
    'stings': {"id": None, "name": 'STING'},
    'station id': {"id": None, "name": 'ID'},
    'news': {"id": None, "name": 'NEWS'},
    'pānui': {"id": None, "name": 'PANUI'},
    'ads': {"id": None, "name": 'AD'},
}

try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()

    LOG_PATH = d.get('log_path', '/var/log/librescripts/')
    LOGFILE = os.path.join(LOG_PATH, "sync_radio_db.log")
    ROOT_FOLDERS = d['search_folders']
    LIBRETIME_TITLE = d['libretime']['url']
    LIBRETIME_URL = d['libretime']['url']
    LIBRETIME_USER = d['libretime']['user']
    LIBRETIME_PASSWORD = d['libretime']['password']
    API_TOKEN = d['libretime']['api_token']
    LIBRETIME_BASIC_AUTH = HTTPBasicAuth(LIBRETIME_USER, LIBRETIME_PASSWORD)
except KeyError:
    logging.error(
        'Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception:
    logging.error('Could not read configuration file {0}.'.format(CONF_FILE))
    raise

handler = TimedRotatingFileHandler(
    filename=LOGFILE, when='D', interval=30, backupCount=3, encoding='utf-8',
    delay=False
)
logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO,
    # filename=LOGFILE,
    handlers=(handler,)
)

parser = argparse.ArgumentParser()
parser.add_argument(
    "-w", "--watch",
    help="Watch the folder.", action="store_true"
)
parser.add_argument(
    "-s", "--sync", help="Sync the folder", action="store_true"
)
parser.add_argument(
    "-v", "--verbose", action="store_true"
)
parser.add_argument(
    "-d", "--show-duplicates", action="store_true"
)
parser.add_argument(
    "-D", "--delete", action="store_true"
)
args = parser.parse_args()


def calculate_md5(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def get_key(md5, data):
    '''
    md5s can be duplicated in libretime so not sure how best to handle
    this situation. problem with unique on md5 and label keys is that
    if a file is moved from one folder to another how will we be able
    to just update the same file in the db with that md5? If we write
    the metadata to the file, then the md5 will change based only on
    the file structure metadata (except for some reason that md5 is always
    different when we save it with the same exact metadata).
    '''
    return md5
    return '-'.join(
        [md5] +
        [str(data[i]) for i in LABEL_KEYS if data[i]]
    )


def scan_folder(ROOT_FOLDER, db={}):
    NUM_FILES = 0
    spinner = itertools.cycle(['-', '/', '|', '\\'])
    exclude = set(['.sync', '#recycle'])
    for root, dirs, files in os.walk(ROOT_FOLDER):
        dirs[:] = [d for d in dirs if d not in exclude]

        for name in files:
            NUM_FILES = NUM_FILES + 1

            path = os.path.join(root, name)

            data = process_path(path, ROOT_FOLDER)

            if data:
                key = get_key(data['md5'], data)
                db[key] = data
                update_metadata(path, ROOT_FOLDER)
                # new_md5 = calculate_md5(os.path.join(root, name))
                # key = get_key(new_md5, data)
                # db[key] = data

                print(
                    f"\r\033[K{next(spinner)} Scanning {ROOT_FOLDER}: {NUM_FILES}",
                    flush=True, end=''
                )

    logging.info("Scanned {0} files in {1}".format(NUM_FILES, ROOT_FOLDER))
    return db


def load_radio_db(keep_duplicates=False):
    print("Loading Libretime DB")
    API_URL = f"{LIBRETIME_URL}/api/v2/files"
    response = requests.get(
        API_URL, auth=LIBRETIME_BASIC_AUTH
    )
    files = response.json()
    data = {}
    session_id = login_playwright()

    if keep_duplicates:
        return {file['id']: file for file in files}

    for file in files:
        key = get_key(file['md5'], file)
        if file['md5'] in data.keys():
            logging.warning(f"Duplicated: {file['name']}")
            if any(
                [
                    file[key].find('#') > -1
                    for key in LABEL_KEYS[:3] if file[key]
                ] +
                [any([
                    file[key] == ''
                    for key in LABEL_KEYS[:3] if file[key]
                ])]
            ):
                print(
                    "Delete duplicated stale file",
                    file['id'],
                    file['name'],
                    [file[key] for key in LABEL_KEYS],
                )
                delete_file(file['id'], session_id)

            elif all([
                file[key] == data[file['md5']][key] for key in LABEL_KEYS
            ]):
                print(
                    "Delete duplicated file",
                    file['id'],
                    file['name'],
                    [file[key] for key in LABEL_KEYS],
                )
                delete_file(file['id'], session_id)
            else:
                # Need to give a new md5 name for the dict key?
                print(file['uploaded'])
                if file['uploaded'] > data[key]['uploaded']:
                    data[key] = file
        else:
            data[key] = file

    return data


def get_track_type_id(track_type_name):
    API_URL = f"{LIBRETIME_URL}/api/v2/libraries"
    response = requests.get(
        API_URL, auth=LIBRETIME_BASIC_AUTH,
    )
    try:
        response.raise_for_status()
    except Exception as e:
        print(e)
        logging.error(response.text)
        return None
    results = response.json()
    for track in results:
        if (
            track_type_name.lower() == track['name'].lower()
            or track_type_name.lower() == track['code'].lower()
        ):
            return track['id']
    return None


def update_file(file_id, kwargs):
    API_URL = f"{LIBRETIME_URL}/api/v2/files/{file_id}"
    response = requests.put(
        API_URL, auth=LIBRETIME_BASIC_AUTH,
        json={**kwargs},
    )
    try:
        response.raise_for_status()
    except Exception:
        logging.error(response.text)
    finally:
        return response.status_code


def delete_file(file_id, SESSION_ID):
    API_URL = f"{LIBRETIME_URL}/library/delete"
    raw_data = \
        f"format=json&media%5B0%5D%5Bid%5D={file_id}&media%5B0%5D%5Btype%5D=audioclip"
    session = requests.Session()
    session.headers.update({
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referrer": '{LIBRETIME_URL}/showbuilder',
        "Accept": "*/*",
        'Origin': '{LIBRETIME_URL}',
        'Cookie': f"PHPSESSID={SESSION_ID}"
    })

    response = session.post(
        API_URL,
        data=raw_data,
    )
    try:
        response.raise_for_status()
        response.json()
    except Exception as e:
        logging.error(e)
        logging.error("Failed to delete.")
        return response.status_code

    API_URL = f"{LIBRETIME_URL}/api/v2/files/{file_id}"
    response = requests.delete(
        API_URL, auth=LIBRETIME_BASIC_AUTH
    )
    try:
        response.raise_for_status()
    except Exception:
        return response.status_code
    if response.status_code != 204:
        logging.error("Could not delete")
    return response.status_code


def upload_file(file_path):
    API_URL = f"{LIBRETIME_URL}/rest/media"
    filename = file_path.split('/')[-1]
    try:
        with open(file_path, 'rb') as file:
            response = requests.post(
                API_URL, auth=(API_TOKEN, ''),
                files=[
                    ('file', (filename, file))
                ],
                timeout=30,
            )
    except Exception as e:
        logging.error(e)
        return 500
    try:
        response.raise_for_status()
    except Exception:
        logging.error(response.text)
    finally:
        return response.status_code


def sync_entire_folder(delete=args.delete):
    db = {}
    session_id = login_playwright()
    libretime_db = load_radio_db()
    print(f"Loaded {len(libretime_db)} files from libretime")

    # Check files in libretime and delete
    deleted = []
    for md5 in libretime_db.keys():
        if any([
            libretime_db[md5][key].find('#') > -1
            for key in LABEL_KEYS[:3] if libretime_db[md5][key]
        ]):
            print(
                "Delete stale file",
                libretime_db[md5]['id'],
                libretime_db[md5]['name'],
                [libretime_db[md5][key] for key in LABEL_KEYS],

            )
            delete_file(libretime_db[md5]['id'], session_id)
            deleted.append(md5)
    for i in deleted:
        del libretime_db[i]

    for folder in ROOT_FOLDERS:
        logging.info('Scanning {0}'.format(folder))
        db = {**db, **scan_folder(folder)}
    print(f"\nLoaded {len(db)} files from {folder}\n")

    exists = (db.keys() & libretime_db.keys())
    for md5 in exists:
        payload = {
            **{key: db[md5][key] for key in LABEL_KEYS},
            **{key: libretime_db[md5][key] for key in REQUIRED},
        }

        # Outdated metadata, update
        if any(
            libretime_db[md5][i] != db[md5][i]
            for i in LABEL_KEYS
        ):
            print('Data outdated')
            payload = {
                **{key: db[md5][key] for key in LABEL_KEYS},
                **{key: libretime_db[md5][key] for key in REQUIRED}
            }
            payload['name'] = (
                libretime_db[md5]['name'] if libretime_db[md5]['name'] != ''
                else db[md5]['name']
            )
            payload['accessed'] = 0
            payload['updated_at'] = datetime.datetime.now(
                tz=pytz.timezone("Pacific/Auckland")
            ).isoformat()
            if not payload['mime']:
                payload['mime'] = mimetypes.guess_type(db[md5]['path'])[0]
            print(payload)
            update_file(
                libretime_db[md5]['id'],
                payload
            )

        # Delete files with # in our tags
        elif any([
            db[md5][key].find('#') > -1 for key in LABEL_KEYS[:3] if db[md5][key]
        ]):
            print(
                "Delete file, it has a # in its name",
                libretime_db[md5]['name']
            )
            delete_file(libretime_db[md5]['id'], session_id)

    # New files not in db.
    should_resync = False
    new = (set(db.keys()) - set(libretime_db.keys()))
    for md5 in new:
        payload = {
            **{key: db[md5][key] for key in LABEL_KEYS},
        }
        if any([
            db[md5][key].find('#') > -1 for key in LABEL_KEYS[:3] if db[md5][key]
        ]):
            continue
        else:
            logging.info(f"Upload new file: {db[md5]['name']}")
            print(f"Upload new file: {db[md5]['name']}")
            status = upload_file(db[md5]['path'])
            if status == 201:
                # Now update the file
                should_resync = True

    # Delete files in libretime that aren't in our radio folder!
    if delete:
        labels = {}
        for _, value in db.items():
            if value['label'] not in labels.keys():
                labels[value['label']] = True

        print("Only delete these labels: ")
        for label in labels:
            print(label)

        to_delete = {}
        for key, value in libretime_db.items():
            if value['label'] in labels:
                to_delete[key] = value

        deleted = (set(to_delete.keys()) - set(db.keys()))
        print(deleted)
        print(f'{len(deleted)} files to delete?')
        for md5 in deleted:

            print(
                "Delete file ",
                md5,
                [to_delete[md5][i] for i in ['track_title']+LABEL_KEYS]
            )
            try:
                delete_file(to_delete[md5]['id'], session_id)
            except Exception as e:
                print("Could not delete file")
                print(e)

    if should_resync:
        return sync_entire_folder(delete=False)


def show_all_duplicates():
    db = load_radio_db(keep_duplicates=True)
    data = {}
    _keys = {}
    for _, file in db.items():

        if file['md5'] in _keys.keys():
            # Duplicate
            if file['md5'] not in db.keys():
                data[file['md5']] = [
                    db[_keys[file['md5']]],
                    file
                ]
            else:
                data[file['md5']].append(file)
        else:
            _keys[file['md5']] = file['id']

    for key in data.keys():
        print(f"Duplicated: {key}")
        # print(db[key])
        # print(file)
        for file in data[key]:
            print(file)
            # print('\t'.join(file[i] for i in file))
    return data


def delete_duplicates(data):
    print("\n")
    session_id = login_playwright()
    db = load_radio_db(keep_duplicates=True)
    for file in db:
        file = db[file]
        if file['md5'] in data.keys():
            # print(file['filepath'])
            # print(file['md5'])
            for duplicate in data[file['md5']]:
                # print(duplicate)
                if duplicate['id'] != file['id']:
                    print(f"Delete {duplicate['filepath']}")
                    delete_file(duplicate['id'], session_id)


def login_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f'{LIBRETIME_URL}/login')
        # Perform login
        page.fill('input[name="username"]', LIBRETIME_USER)
        page.fill('input[name="password"]', LIBRETIME_PASSWORD)
        page.click('input[name="submit"]')
        expect(page).to_have_url(re.compile('.*showbuilder.*'))
        # to_have_title(re.compile(
        #     LIBRETIME_TITLE
        # ))
        # Saving the session state for future use
        context.storage_state(path='session.json')
        SESSION_ID = page.context.cookies()[0]['value']
        # Closing browser
        browser.close()
    return SESSION_ID


def process_path(path, root_folder):
    '''
    Takes a folder path with our radio database and generates the
    GENRE, LABEL, and LANGUAGE based on the folder structure.
    Returns that metadata.
    '''
    name = os.path.basename(path)
    if any([
        name[0] in "~!#.?",
        '.rslsa' == name[-6:],
        name.split('.')[-1].lower() not in 'mp3 mp4 m4a flac wav ogg'
    ]):
        return

    RELATIVE = path.split(root_folder)[1]
    parts = RELATIVE.split('/')
    if parts[0] == '':
        parts.pop(0)

    SKIP_DIR = False
    for part in parts:
        if part:
            if part[0] == '.':
                logging.debug(
                    "Skipping folder {0}:{1}".format(part, name))
                SKIP_DIR = True
    if SKIP_DIR:

        return

    try:
        label = normalize('NFC', parts[0])
    except IndexError:
        logging.warning(
            'File not properly organized: {0}'.format(name))
        return

    try:
        language = normalize('NFC', parts[1])
    except IndexError:
        language = None
        logging.warning('File not in language folder: {0}'.format(
            os.path.join(RELATIVE, name)))

    try:
        genre = normalize('NFC', parts[2])
    except IndexError:
        genre = None
        logging.debug('File not in genre folder: {0}'.format(
            os.path.join(RELATIVE, name)))

    if '#' in path:
        try:
            m = re.findall(r'\/(#[^\/]*)', path)
            exclude = m[-1]
            label = label + ' :: ' + exclude
        except Exception as e:
            logging.error(e)
            raise e

    try:
        orig_md5 = calculate_md5(path)
    except Exception:
        orig_md5 = None

    if label.lower() in TRACKS.keys():
        track_id = TRACKS[label.lower()]['id']
    else:
        track_id = None

    data = {
        'path': path,
        'md5': orig_md5,
        'label': label,
        'language': language,
        'genre': genre,
        'name': name.split('.')[0],
        'fullname': name,
        'library': track_id
    }

    return data


def update_metadata(path, root):
    data = process_path(path, root)
    name = data['fullname']
    language = data['language']
    label = data['label']
    genre = data['genre']
    data['track_title'] = data['name']

    try:
        audio = mutagen.File(os.path.join(root, name), easy=True)
    except Exception:
        logging.warning(
            'Could not load file with mutagen: {0}'.format(name))
        audio = None

    if not audio:
        file_path = os.path.join(root, name)
        if os.path.exists(file_path):
            extension = name.split('.')[-1]
            if extension.lower() in 'wave':
                logging.warning('Cannot update .wav metadata')
                return data
            logging.warning("Audio is none")
            outfile = '/tmp/tmp.' + extension
            cmd = [
                'ffmpeg', '-y', '-v', 'quiet',
                '-i', file_path,
                '-c:a', 'copy', outfile
            ]
            p = Popen(cmd, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate()
            Popen(['mv', outfile, file_path])

            try:
                audio = mutagen.File(file_path, easy=True)
            except Exception:
                logging.warning(
                    'Could not load file with mutagen after conversion: {0}'
                    .format(name)
                )
                return data

            if not audio:
                logging.warning(
                    'Attempting to add tags so we can use "easy": {0}'
                    .format(name)
                )

                if extension.lower() in 'mp3':
                    audio = ID3(file_path, translate=False)
                    audio.add(TIT2(encoding=3, text=name))
                    audio.save()
                    audio = mutagen.File(file_path, easy=True)

        else:
            logging.warning(f"File doesn't exist, {file_path}")

    try:
        logging.debug("UPDATE:  {0}".format(
            ' '.join(audio['title'].encode('utf-8'))
        ))
    except (KeyError, TypeError):
        logging.debug("UPDATE:  {0}".format(name.encode('utf-8')))
    logging.debug('TAGS:    {0}'.format(audio))

    SAVE = False
    if audio:

        # TAG: TITLE - keep source file
        try:
            track_title = audio['title']
            data['track_title'] = track_title
        except KeyError:
            pass

        # TAG: LANGUAGE
        try:
            lang = audio['language']
        except KeyError:
            lang = []
        if language:
            if [language] != lang:
                lang = [language]
                try:
                    audio.tags['language'] = lang
                except Exception:
                    try:
                        audio.tags['language'] = language
                    except Exception:
                        logging.warning(
                            "Could now write 'language' to {0}".format(
                                name)
                        )
                        return data
                SAVE = True
            logging.debug("LANG:    {0}".format(lang))

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

        # Let's not do this. Let's just post this data to the database
        # rather than editing the metadata of the file!
        if SAVE:
            logging.info(
                (
                    u"Updating {0}\n\tTAGS:\t{1}\n\tLANG:\t{2}\n\tGENRE\t{3}\n\tLABEL\t{4}"
                    .format(name, audio, lang, g, t)
                )
            )
            audio.save()
        logging.debug(audio)
        return data
    return data


class MyRegexMatchingEventHandler(RegexMatchingEventHandler):

    def __init__(self, root_folder, *args, **kwargs):
        super(MyRegexMatchingEventHandler, self).__init__(*args, **kwargs)

        self.session_id = login_playwright()
        self.db = self.load_radio_db()
        self.root_folder = root_folder

    def refresh_db(self):
        print('refresh db')
        self.db = self.load_radio_db()

    def load_radio_db(self):
        API_URL = f"{LIBRETIME_URL}/api/v2/files"
        response = requests.get(
            API_URL, auth=LIBRETIME_BASIC_AUTH
        )
        files = response.json()
        data = {}
        for file in files:
            if file['md5'] in data.keys():
                continue
            else:
                data[file['md5']] = file
        return data

    def _match_file(self, data):
        for key in self.db:
            item = self.db[key]
            if all([
                (
                    data['fullname'] in item['filepath'] or
                    data['name'] in item['name']
                ),
                data['genre'] == item['genre'],
                data['label'] == item['label'],
                data['language'] == item['language'],
            ]):
                print('matched')
                return item
        return None

    def process_file(
            self, new_data, deleted=False, created=False, updated=False
    ):
        status = 200
        md5 = new_data['md5']
        if md5 in self.db.keys():
            md5_changed = False
            original = self.db[md5]
        else:
            md5_changed = True
            original = self._match_file(new_data)

        if deleted and original:
            status = delete_file(
                original['id'],
                self.session_id
            )
        elif deleted:
            logging.info("File deleted that wasn't found in db.")
        elif original and updated and not deleted:
            # Modify existing
            payload = {
                **{key: new_data[key] for key in LABEL_KEYS},
                **{key: original[key] for key in REQUIRED}
            }
            payload['name'] = (
                original['name'] if original['name'] != ''
                else new_data['name']
            )
            payload['accessed'] = 0
            payload['updated_at'] = datetime.datetime.now(
                tz=pytz.timezone("Pacific/Auckland")
            ).isoformat()
            if not payload['mime']:
                payload['mime'] = mimetypes.guess_type(new_data['path'])[0]
            print('update file', new_data)
            status = update_file(
                original['id'],
                payload
            )
            if md5_changed:
                # We need to reupload the new file to the database!
                print("we need to replace the old file!")
                return

        elif created:
            logging.info("Uploading new file")
            status = upload_file(new_data['path'])
            if status == 201:
                # Now update the file
                sleep(5)
                self.refresh_db()
                self.process_file(new_data, updated=True)

        if status >= 401:
            self.session_id = login_playwright()
            print(f'error with {new_data}')
            print(status)

        if deleted or created:
            self.refresh_db()

    def _get_path(self, event):
        path = event.dest_path
        if not path:
            path = event.src_path
        return path

    def on_moved(self, event):
        """
        We should just update the metadata here!
        """
        print("file moved, update metadata")

        # data = process_path(self._get_path(event), self.root_folder)
        # if data:
        # self.process_file(data, updated=True)
        print(self._get_path(event))
        try:
            data = update_metadata(self._get_path(event), self.root_folder)
        except Exception as e:
            print(self._get_path(event), self.root_folder)
            print(e)
            raise Exception(e)
        if data:
            print(data)
            self.process_file(data, updated=True)
        else:
            print("no data returned")

    def on_created(self, event):
        """

        """
        data = process_path(self._get_path(event), self.root_folder)
        if data:
            self.process_file(data, created=True)

    def on_deleted(self, event):
        '''
        Delete the file IF it's in the libretime database.
        '''
        data = process_path(self._get_path(event), self.root_folder)
        if data:
            self.process_file(data, deleted=True)

    def on_modified(self, event):
        """
        Since we update metadata on the file when it's moved, the modified
        will be triggered so we can up date metadata in the database.
        """
        data = process_path(self._get_path(event), self.root_folder)
        if data:
            self.process_file(data, updated=True)


def main():

    if args.show_duplicates:
        data = show_all_duplicates()
        if args.delete:
            delete_duplicates(data)
        return data

    if args.verbose:
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        logging.getLogger().setLevel(logging.DEBUG)

    if args.sync:
        print("Sync entire folder.")
        sync_entire_folder()

    if not args.watch:
        return

    observer = Observer()
    for folder in ROOT_FOLDERS:
        event_handler = MyRegexMatchingEventHandler(
            root_folder=folder,
            regexes=None,
            ignore_regexes=[
                r'[\#\!\.]',
                r'.*DS_Store',
                r'.*rsls[zadc]',
                r'.*!sync',
                r'\.fsprobe'
            ],
            ignore_directories=True
        )
        observer.schedule(event_handler, folder, recursive=True)
    observer.start()

    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    for track in TRACKS:
        TRACKS[track]['id'] = get_track_type_id(TRACKS[track]['name'])
    data = main()
