from multiprocessing import Process, Pool, Queue, Manager
import requests
from requests.auth import HTTPDigestAuth
import os
from datetime import datetime
import time
import json
from subprocess import Popen, PIPE
import sys
from time import sleep
from remote_streams.settings import CONF_FILE
import pytz
import tempfile as tf
timezone = pytz.timezone("Pacific/Auckland")

from remote_streams.face_detection import face_in_binary_image

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


BASEURL = "https://rtmp.tehiku.live:8087/v2/servers/_defaultServer_/vhosts/_defaultVHost_/"
RESOURCE = "applications/rtmp/adv"

HEADERS ={
    'Accept': 'application/json; charset=utf-8' ,
    'Content-Type': 'application/json; charset=utf-8'
}

START_TIME = timezone.localize(datetime.strptime('2020/03/02 12:00:00', '%Y/%m/%d %H:%M:%S'))
END_TIME = timezone.localize(datetime.strptime('2020/03/02 23:30:00', '%Y/%m/%d %H:%M:%S'))
ENTRIES = ['Face Test'] #, 'Push to tehiku.radio', 'Sunshine Radio']
SOURCE_STREAM_NAME = 'face_test'
DEFAULT_STREAM_TAKE = 'teaonews'
DEST_STREAM_NAME = 'teaonews_auto'

# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    USER = d['wowza']['user']
    PASSWORD = d['wowza']['password']
    AWS_KEY = d['aws']['access_key_face']
    AWS_ID = d['aws']['secret_key_face']
except KeyError as e:
    print('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    print('Could not read configuration file {0}.'.format(CONF_FILE))
    raise


def wowza_put_data(resource, data):
    r = requests.put(os.path.join(BASEURL, resource), auth=HTTPDigestAuth(USER, PASSWORD), headers=HEADERS, data=json.dumps(data))
    res = r.json()
    print("Result: {0}".format(res))
    # if not res['success']:
        # print(data)

def wowza_get_targets():
    success = False
    indi = '-/|\\-'
    count = 0
    while not success:
        if count >= 3:
            count = 0
        else:
            count = count + 1

        RESOURCE = "applications/rtmp/pushpublish/mapentries"
        try:
            r = requests.get(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS)
            data = r.json()
            success = data['success']
        except KeyError:
            success = True
        except Exception as e:
            print(f"\rError querying wowza server... {indi[count]}", end='')
            success = False
        
        if not success:
            sleep(1)

    return data


def toggle_stream_targets(queue, wowza_data, state, entries=ENTRIES, default_stream_source=None):
    for target in entries:
        for entry in wowza_data['mapEntries']:
            if target in entry['entryName']:
                RESOURCE = "applications/rtmp/pushpublish/mapentries/" + target
                entry['enabled'] = state
                if default_stream_source:
                    entry['sourceStreamName'] = default_stream_source
                wowza_put_data(RESOURCE, entry)
                queue.put({'targets_enabled': state})

def stream_should_start(queue, start_time=START_TIME, end_time=END_TIME):

    # TODO
    '''
    Get the start and stop from an API
    Check the API every 5 minutes for schedule change?
    - webhook better! -
    '''
    wowza_data = wowza_get_targets()

    start = start_time.hour*60*60 + start_time.minute*60 + start_time.second
    end   = end_time.hour*60*60   + end_time.minute*60   + end_time.second

    state = [False, False]
    while True:
        NOW = datetime.utcnow().replace(tzinfo=pytz.utc)
        NOW = NOW.astimezone(timezone)
        now = NOW.hour*60*60 + NOW.minute*60 + NOW.second

        if start > now:
            if not state[0]:
                print("Stop Stream")
                state[0] = True
                queue.put({'start_stream': False})
                toggle_stream_targets(queue, wowza_data, False)

        elif start <= now and end >= now:
            if not state[1]:
                print("Start Stream")
                queue.put({'start_stream': True})
                state[1] = True
                toggle_stream_targets(queue, wowza_data, False)

        elif end <= now:
            if state[1] and state[0]:
                print("Stop Stream")
                queue.put({'start_stream': False})
                state = [False, False]
                toggle_stream_targets(queue, wowza_data, False, default_stream_source=DEFAULT_STREAM_TAKE)

        time.sleep(1)


def get_face(queue):
    src = "rtmp://rtmp.tehiku.live:1935/rtmp/" + SOURCE_STREAM_NAME
    tmp_file = tf.NamedTemporaryFile(delete=True, suffix='.jpg')
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'panic', '-i', src,
        '-vframes', '1',
        '-f', 'image2', tmp_file.name
    ]
    # print(' '.join(cmd))

    if os.path.exists(tmp_file.name):
        Popen(['rm', tmp_file.name])

    while True:
        # print('face')
        queue.put({'face_state': 'running',})
        process = Popen(cmd, stderr=PIPE, stdout=PIPE)
        o,e = process.communicate()
        try:
            with open(tmp_file.name, 'rb') as f:
                data = f.read()
                result = face_in_binary_image(data)
                if result:
                    face_count = round(result[1]/100 - 50)/50
                    queue.put({
                        'has_face': result[0],
                        'face_conf_msg': f'Face found {round(result[1])}% confidence',
                        'face_count': face_count,
                        'face_state': 'running',
                    })

                else:
                    queue.put({'has_face': False, })
            Popen(['rm', tmp_file.name])
        except Exception as e:
            queue.put({'face_state': 'stopped','has_face': False, 'face_error': e})
            return
            # print("ERROR:",e)
        # sleep(1)


def rtmp_stereo_to_mono(queue, src=None, dst=None):
    if not src:
        src = "rtmp://rtmp.tehiku.live:1935/rtmp/" + SOURCE_STREAM_NAME
    if not dst:
        dst = "rtmp://rtmp.tehiku.live:1935/rtmp/" + DEST_STREAM_NAME

    cmd = [
        'ffmpeg', '-re', '-loglevel', 'warning', '-i', src,
        '-c:v', 'copy',
        '-c:a', 'aac', '-ac', '1', '-ar', '44100',
        '-f', 'flv', dst,
    ]

    process = Popen(cmd, stderr=PIPE, stdout=PIPE)
    queue.put({"streaming": True, "ffmpeg_starting": False})
    for line in process.stdout:
        sys.stdout.write(line)
    e = process.stderr.read()
    queue.put({
        "streaming": False,
        "ffmpeg_error": True,
        "error_message": e.decode().replace('\n', ' ')})

def main():

    q = Queue()

    # enable_targets = Process(target=enable_stream_targets, args=(q,data))
    stream_toggle = Process(target=stream_should_start, args=(q,))
    ffmpeg_stream = Process(target=rtmp_stereo_to_mono, args=(q,))
    # has_face = Process(target=get_face, args=(q,))

    messages = {
        'streaming': False,
        'start_stream': False,
        'terminate': False,
        'ffmpeg_error': False,
        'ffmpeg_starting': False,
        'error_message': '',
        'has_face': False,
        'face_conf_msg': '',
        'face_state': 'stopped',
        'ffmpeg_state': 'stopped',
        'targets_enabled': False,
    }

    stream_toggle.start()

    loop = True
    indi = '-/|\\-'
    count = 0
    is_streaming_count = 0
    wowza_data = None

    while loop:
        sleep(0.1)
        if count >= 3:
            count = 0
        else:
            count = count + 1

        try:
            try:
                message = q.get_nowait()
                for k in message.keys():
                    messages[k] = message[k]
            except:
                # No messages
                pass


            if not messages['start_stream'] and messages['streaming']:
                # Scheduled stop
                print("Streaming schedule stop")

                if ffmpeg_stream:
                    ffmpeg_stream.terminate()
                messages['terminate'] = False
                messages['streaming'] = False
                is_streaming_count = 0
                ffmpeg_stream = Process(target=rtmp_stereo_to_mono, args=(q,))

            elif messages['terminate']:
                loop = False
                raise

            elif messages['ffmpeg_error']:
                if ffmpeg_stream:
                    ffmpeg_stream.terminate()
                
                try:
                    has_face.terminate()
                except:
                    pass
                    
                messages['has_face'] = False
                messages['face_state'] = 'stopped'
                messages['ffmpeg_error'] = False
                messages['streaming'] = False
                messages['ffmpeg_starting'] = False
                

                is_streaming_count = 0

                ffmpeg_stream = Process(target=rtmp_stereo_to_mono, args=(q,))

                if not wowza_data:
                    wowza_data = wowza_get_targets()
                if messages['targets_enabled']:
                    toggle_stream_targets(q, wowza_data, False, default_stream_source=DEST_STREAM_NAME)

            elif messages['start_stream'] and not messages['streaming'] and not messages['ffmpeg_starting']:
                # Scheduled start
                # print("\rStart FFMPEG Encoding")
                messages['ffmpeg_starting'] = True
                if ffmpeg_stream:
                    ffmpeg_stream.start()
                wowza_data = wowza_get_targets()


            elif messages['start_stream'] and messages['streaming'] and messages['has_face'] and messages['face_state'] != 'done':
                print("\r\nEnable stream target")
                if messages['has_face']:
                    messages['face_state'] = 'done'
                    has_face.terminate()
                if not wowza_data:
                    wowza_data = wowza_get_targets()

                toggle_stream_targets(q, wowza_data, True, default_stream_source=DEST_STREAM_NAME)
                messages['face_starting'] = False

            else:
                pass


            if is_streaming_count > 5 and not messages['has_face'] and messages['face_state'] != 'running':
                # Start face detection
                has_face = Process(target=get_face, args=(q,))

                print("Start Face Detection")
                try:
                    has_face.start()
                    messages['face_state'] = 'starting'
                except:
                    print('face already started')

            sleep(.1)

            try:
                message = q.get_nowait()
                for k in message.keys():
                    messages[k] = message[k]
            except:
                # No messages
                pass


            STREAM_MSG = ''
            if messages['streaming'] and not messages['ffmpeg_error']:                
                if is_streaming_count > 10:
                    STREAM_MSG = f'{bcolors.OKGREEN}FFMPEG Streaming {indi[count]}{bcolors.ENDC}'

                elif is_streaming_count == 10:
                    print(flush=True)
                    is_streaming_count = is_streaming_count + 1
                else:
                    is_streaming_count = is_streaming_count + 1

            if is_streaming_count < 10 and messages['start_stream']:
                STREAM_MSG = f'{bcolors.WARNING}FFMPEG Starting  {indi[count]}{bcolors.ENDC}'


            emsg = messages['error_message']
            if emsg:
                messages['error_message'] = ''

            fmsg = messages['face_conf_msg']
            if fmsg:
                messages['face_conf_msg'] = ''

            sys.stdout.flush()
            print(
                f"\r{STREAM_MSG}\
{bcolors.FAIL}{emsg}{bcolors.ENDC}\
{bcolors.OKBLUE}{bcolors.BOLD}{fmsg}{bcolors.ENDC}{bcolors.ENDC}", end='', flush=True)
                

        except KeyboardInterrupt as e:
            print("\nCaught KeyboardInterrupt, terminating workers")
            stream_toggle.terminate()
            try:
                ffmpeg_stream.terminate()
            except:
                pass
            q.close()
            loop = False

        except Exception as e:
            print("\nCaught Exception, terminating workers")
            print(e)
            stream_toggle.terminate()
            try:
                ffmpeg_stream.terminate()
            except:
                pass
            q.close()
            loop = False


if __name__ == '__main__':
    main()
