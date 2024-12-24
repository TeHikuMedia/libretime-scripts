import datetime
import itertools
import mimetypes
import os
import re
import mutagen
import logging
import json
import hashlib
import pytz
import requests
from requests.auth import HTTPBasicAuth
from mutagen.id3 import ID3, TIT2
from unicodedata import normalize
from subprocess import Popen, PIPE
from watchdog.observers import Observer
from watchdog.events import RegexMatchingEventHandler
from playwright.sync_api import sync_playwright, expect


CONF_FILE = "/etc/librescripts/conf.json"
LABEL_KEYS = ['genre', 'language', 'label']
REQUIRED = ['mime', 'accessed', 'name', 'size']

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

logging.basicConfig(
    format='%(asctime)s [%(levelname)s]: %(message)s',
    level=logging.INFO,
    filename=LOGFILE,
)


def calculate_md5(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def scan_folder(ROOT_FOLDER, db={}):
    NUM_FILES = 0
    spinner = itertools.cycle(['-', '/', '|', '\\'])
    for root, dirs, files in os.walk(ROOT_FOLDER):
        for name in files:
            NUM_FILES = NUM_FILES + 1

            if any([
                name[0] in "~!#.?",
                '.rslsa' == name[-6:],
                name.split('.')[-1].lower() not in 'mp3 mp4 m4a flac wav ogg'
            ]):
                logging.debug('Skipping {0}'.format(name))
                continue
            print(
                f"\r\033[K{next(spinner)} Scanning {ROOT_FOLDER}: {NUM_FILES}",
                flush=True, end=''
            )
            parts = root.split('/')

            RELATIVE = root.split(ROOT_FOLDER)[1]

            parts = RELATIVE.split('/')
            parts.pop(0)

            SKIP_DIR = False
            for part in parts:
                if part:
                    if part[0] == '.':
                        logging.debug(
                            "Skipping folder {0}:{1}".format(part, name))
                        SKIP_DIR = True
            if SKIP_DIR:
                continue

            try:
                label = normalize('NFC', parts[0])
            except IndexError:
                logging.warning(
                    'File not properly organized: {0}'.format(name))
                continue

            try:
                language = normalize('NFC', parts[1])
            except IndexError:
                language = None
                logging.warning('File not in language folder: {0}'.format(
                    os.path.join(RELATIVE, name)))
                continue

            try:
                genre = normalize('NFC', parts[2])
            except IndexError:
                genre = None
                logging.debug('File not in genre folder: {0}'.format(
                    os.path.join(RELATIVE, name)))

            if '#' in root:
                try:
                    m = re.findall(r'\/(#[^\/]*)', root)
                    exclude = m[-1]
                    label = label + ' :: ' + exclude
                except Exception as e:
                    logging.error(e)
                    raise e

            orig_md5 = calculate_md5(os.path.join(root, name))
            db[orig_md5] = {
                'path': os.path.join(root, name),
                'new_md5': None,
                'label': label,
                'language': language,
                'genre': genre,
                'name': name.split('.')[0]
            }

            try:
                audio = mutagen.File(os.path.join(root, name), easy=True)
            except Exception:
                logging.warning(
                    'Could not load file with mutagen: {0}'.format(name))
                continue

            if not audio:
                file_path = os.path.join(root, name)
                if os.path.exists(file_path):

                    extension = name.split('.')[-1]
                    if extension.lower() in 'wave':
                        logging.warning('Cannot update .wav metadata')
                        continue
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
                            'Could not load file with mutagen after conversion: {0}'.format(name))
                        continue

                    if not audio:
                        logging.warning(
                            'Attempting to add tags so we can use "easy": {0}'.format(name))

                        if extension.lower() in 'mp3':
                            audio = ID3(file_path, translate=False)
                            audio.add(TIT2(encoding=3, text=name))
                            audio.save()
                            audio = mutagen.File(file_path, easy=True)

                else:
                    print("NO exists!")

            try:
                logging.debug("UPDATE:  {0}".format(
                    ' '.join(audio['title'].encode('utf-8'))))
            except Exception:
                logging.debug("UPDATE:  {0}".format(name.encode('utf-8')))
            logging.debug('TAGS:    {0}'.format(audio))

            SAVE = False
            if audio:

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
                                continue
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

                if SAVE:
                    logging.info(
                        (u"Updating {0}\n\tTAGS:\t{1}\n\tLANG:\t{2}\n\tGENRE\t{3}\n\tLABEL\t{4}"
                            .format(name, audio, lang, g, t))
                    )
                    audio.save()
                    new_md5 = calculate_md5(os.path.join(root, name))
                    db[orig_md5]['new_md5'] = new_md5
                logging.debug(audio)

    logging.info("Scanned {0} files in {1}".format(NUM_FILES, ROOT_FOLDER))
    return db


def load_radio_db():
    print("Loading Libretime DB")
    API_URL = f"{LIBRETIME_URL}/api/v2/files"
    response = requests.get(
        API_URL, auth=LIBRETIME_BASIC_AUTH
    )
    files = response.json()
    data = {}
    session_id = login_playwright()
    for file in files:
        if file['md5'] in data.keys():
            logging.warning(f"Duplicated: {file['name']}")
            if any(
                [
                    file[key].find('#') > -1
                    for key in LABEL_KEYS if file[key]
                ] +
                [any([
                    file[key] == ''
                    for key in LABEL_KEYS if file[key]
                ])]
            ):
                print(
                    "Delete duplicated stale file",
                    file['id'],
                    file['name'],
                    [file[key] for key in LABEL_KEYS],
                )
                delete_file(file['id'], session_id)
                del file['md5']

        else:
            data[file['md5']] = file

    return data


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


def sync_entire_folder():
    db = {}
    session_id = login_playwright()
    KEYS = ['genre', 'language', 'label']
    REQUIRED = ['mime', 'accessed', 'name', 'size']

    libretime_db = load_radio_db()
    print(f"Loaded {len(libretime_db)} files from libretime")

    # Check files in libretime and delete
    for md5 in libretime_db.keys():
        if any([
            libretime_db[md5][key].find('#') > -1
            for key in KEYS if libretime_db[md5][key]
        ]):
            print(
                "Delete stale file",
                libretime_db[md5]['id'],
                libretime_db[md5]['name'],
                [libretime_db[md5][key] for key in KEYS],

            )
            delete_file(libretime_db[md5]['id'], session_id)

    for folder in ROOT_FOLDERS:
        logging.info('Scanning {0}'.format(folder))
        db = {**db, **scan_folder(folder)}
    print(f"\nLoaded {len(db)} files from {folder}\n")

    exists = (db.keys() & libretime_db.keys())
    for md5 in exists:

        payload = {
            **{key: db[md5][key] for key in KEYS},
            **{key: libretime_db[md5][key] for key in REQUIRED}
        }

        # The file changed, delete the old item and upload the new one
        if db[md5]['new_md5']:
            if md5 in libretime_db.keys():
                try:
                    print("Upload new & delete old files", db[md5]['name'])
                    upload_file(db[md5]['path'])
                    delete_file(libretime_db[md5]['id'], session_id)
                except Exception:
                    pass
            else:
                print("Upload new file", db[md5]['name'])
                try:
                    upload_file(db[md5]['path'])
                except Exception:
                    pass

        # Outdated metadata, update
        elif any(
            libretime_db[md5][i] != db[md5][i]
            for i in KEYS
        ):
            print('Data outdated')
            payload = {
                **{key: db[md5][key] for key in KEYS},
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
            db[md5][key].find('#') > -1 for key in KEYS[:3] if db[md5][key]
        ]):
            print(
                "Delete file, it has a # in its name",
                libretime_db[md5]['name']
            )
            delete_file(libretime_db[md5]['id'], session_id)

    # New files not in db.
    new = (set(db.keys()) - set(libretime_db.keys()))
    for md5 in new:
        if any([
            db[md5][key].find('#') > -1 for key in KEYS[:3] if db[md5][key]
        ]):
            continue
        else:
            print("Upload new file", db[md5]['name'])
            upload_file(db[md5]['path'])


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


def process_path(path):
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

    RELATIVE = path.split(ROOT_FOLDER)[1]

    parts = RELATIVE.split('/')
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
        return

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
    return {
        'path': path,
        'md5': orig_md5,
        'label': label,
        'language': language,
        'genre': genre,
        'name': name.split('.')[0],
        'fullname': name,
    }


class MyRegexMatchingEventHandler(RegexMatchingEventHandler):

    def __init__(self, *args, **kwargs):
        super(MyRegexMatchingEventHandler, self).__init__(*args, **kwargs)

        self.session_id = login_playwright()
        self.db = self.load_radio_db()

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
            original = self.db[md5]
        else:
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
        elif not deleted:
            print("Uploading new file")
            status = upload_file(new_data['path'])

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
        """Called when a file or a directory is moved or renamed.

        :param event:
            Event representing file/directory movement.
        :type event:
            :class:`DirMovedEvent` or :class:`FileMovedEvent`
        """
        data = process_path(self._get_path(event))
        if data:
            self.process_file(data, updated=True)

    def on_created(self, event):
        """Called when a file or directory is created.

            :param event:
                Event representing file/directory creation.
            :type event:
                :class:`DirCreatedEvent` or :class:`FileCreatedEvent`
            """
        print("created")
        data = process_path(self._get_path(event))
        if data:
            self.process_file(data, updated=True)

    def on_deleted(self, event):
        """Called when a file or directory is deleted.

            :param event:
                Event representing file/directory deletion.
            :type event:
                :class:`DirDeletedEvent` or :class:`FileDeletedEvent`
            """
        print("deleted")
        data = process_path(self._get_path(event))
        if data:
            self.process_file(data, deleted=True)

    def on_modified(self, event):
        """Called when a file or directory is modified.

            :param event:
                Event representing file/directory modification.
            :type event:
                :class:`DirModifiedEvent` or :class:`FileModifiedEvent`
            """
        print("modified")
        data = process_path(self._get_path(event))
        if data:
            self.process_file(data, updated=True)


def main():
    print("Startup, sync entire folder.")
    sync_entire_folder()
    print("Watching")
    event_handler = MyRegexMatchingEventHandler(
        regexes=None,
        ignore_regexes=[
            r'[\#\!\.]',
            r'.*DS_Store',
            r'.*rsls[zadc]',
            r'.*!sync',
        ],
        ignore_directories=True
    )
    observer = Observer()
    observer.schedule(event_handler, ROOT_FOLDERS[0], recursive=True)
    observer.start()
    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
