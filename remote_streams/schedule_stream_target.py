from multiprocessing import Process, Pool, Queue, Manager
import requests
from requests.auth import HTTPDigestAuth
import os
import stat
import ast
from datetime import datetime
import time
import json
from subprocess import Popen, PIPE
import sys
from time import sleep
from remote_streams.settings import CONF_FILE
from random import randrange
import argparse
from remote_streams.face_detection import face_in_binary_image
from remote_streams.notify import call_webhooks
import pytz
import tempfile as tf
import logging
import signal


timezone = pytz.timezone("Pacific/Auckland")

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--daemon", help="Daemonize. Don't print.", action="store_true")
args = parser.parse_args()


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

CHECK_STREAM_AVAILABLE = 'applications/{app_name}/instances/_definst_/incomingstreams/{stream_name}/monitoring/current'

HEADERS ={
    'Accept': 'application/json; charset=utf-8' ,
    'Content-Type': 'application/json; charset=utf-8'
}

START_TIME = timezone.localize(datetime.strptime('2020/08/14 12:57:00', '%Y/%m/%d %H:%M:%S'))
END_TIME = timezone.localize(datetime.strptime('2020/08/14 13:50:00', '%Y/%m/%d %H:%M:%S'))
ENTRIES = ['Push to tehiku.radio', 'Sunshine Radio', ]
# ENTRIES = ['Face Test']
WOWZA_APP_NAME = 'rtmp'
SOURCE_STREAM_NAME = 'youtube_ingest'
DEFAULT_STREAM_TAKE = 'youtube_ingest_off'
DEST_STREAM_NAME = 'youtube_ingest'

# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    USER = d['wowza']['user']
    PASSWORD = d['wowza']['password']
    AWS_KEY = d['aws']['access_key_face']
    AWS_ID = d['aws']['secret_key_face']

    LOGDIR = d['log_path']
    LOG_FILE = os.path.join(LOGDIR, 'face_detect.log')
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'a').close()
        os.chmod(LOG_FILE, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)

except KeyError as e:
    print('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    print('Could not read configuration file {0}.'.format(CONF_FILE))
    raise


try:
    logging.basicConfig(format='%(asctime)s: %(message)s',filename=LOG_FILE,level=logging.DEBUG)
except:
    pass


def log(message, level=logging.DEBUG):
    try:
        logging.debug(message)
    except:
        pass


def stream_exists(app_name, stream_name):
    try:
        url = os.path.join(BASEURL, CHECK_STREAM_AVAILABLE.format(app_name=app_name, stream_name=stream_name))
        r = requests.get(url, auth=HTTPDigestAuth(USER, PASSWORD), headers=HEADERS,)
        res = r.json()
        return (res['uptime'] > 1)
    except:
        return False

def wowza_put_data(resource, data):
    try:
        r = requests.put(os.path.join(BASEURL, resource), auth=HTTPDigestAuth(USER, PASSWORD), headers=HEADERS, data=json.dumps(data))
        res = r.json()
        print("Result: {0}".format(res))
    except:
        print("Error putting data...")

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
            sleep(15)

    call_webhooks(None,"Wowza Server running")
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
                state[0] = [True, False]
                queue.put({'start_stream': False})
                toggle_stream_targets(queue, wowza_data, False)

        elif start <= now and end >= now:
            if not state[1]:
                print("Start Stream")
                queue.put({'start_stream': True})
                state = [True, True]
                toggle_stream_targets(queue, wowza_data, False)

        elif end <= now:
            if state[1] and state[0]:
                print("Stop Stream")
                queue.put({'start_stream': False})
                state = [False, False]
                toggle_stream_targets(queue, wowza_data, False, default_stream_source=DEFAULT_STREAM_TAKE)

        time.sleep(1)

def get_thumb_url():
    # Generate random size so we don't cache.
    width = 400.0 + randrange(0,500,1)
    height = width * 9 / 16
    image_size = f'{(width):0.0f}x{(height):0.0f}'
    return \
        f'http://rtmp.tehiku.live:8086/thumbnail?application=rtmp&streamname={SOURCE_STREAM_NAME}&size={image_size}'

def get_face(queue):
    src = "rtmp://rtmp.tehiku.live:1935/rtmp/" + SOURCE_STREAM_NAME
    tmp_file = tf.NamedTemporaryFile(delete=True, suffix='.jpg')

    if os.path.exists(tmp_file.name):
        Popen(['rm', tmp_file.name])

    while True:
        queue.put({'face_state': 'running',})
        cmd = ['curl', '-o', tmp_file.name, get_thumb_url()]
        process = Popen(cmd, stderr=PIPE, stdout=PIPE)
        o,e = process.communicate()
        try:
            with open(tmp_file.name, 'rb') as f:
                data = f.read()
                try:
                    result = face_in_binary_image(data)
                except:
                    result = [False, 0, 0]

                if result:
                    if result[0]:
                        face_count = 1
                        logging.debug(f'Face {result[1]}% conf {result[2]}% bright')
                    else:
                        face_count = 0
                    queue.put({
                        'has_face': result[0],
                        'face_conf_msg': f'Face found {result[1]:0.2f}% confidence {result[2]:0.2f}% brightness.',
                        'face_count': face_count,
                        'face_state': 'running',
                    })

                    if result[1] < 10:
                        sleep(0.1)
                else:
                    sleep(.2)
                    queue.put({'has_face': False, })
            Popen(['rm', tmp_file.name])
            
        except Exception as e:
            logging.error(e)
            queue.put({'face_state': 'stopped','has_face': False, 'face_error': e})
            return


def run_youtube(queue):
    queue.put({
        "ffmpeg_starting": True,
        "face_conf_msg": "Fetching YouTube targets"
    })
    process = Popen(['ingest-youtube', '-g'], stderr=PIPE, stdout=PIPE)
    out, e = process.communicate()
    result = out.decode().strip()
    if result != 'None':
        cmd = ["ingest-youtube", "-w", result]
        process = Popen(cmd, stderr=PIPE, stdout=PIPE)
        queue.put({
            "streaming": True,
            "ffmpeg_starting": False,
            "face_conf_msg": " YouTube ingestion started "
            })
        out, e = process.communicate()
        out = out.decode()
        e = e.decode().replace('\n', ' ')
        queue.put({
            "streaming": False,
            "ffmpeg_error": True,
            "error_message": e})
    else:
        time.sleep(5)
        queue.put({
            "streaming": False,
            "ffmpeg_starting": True,
            "face_conf_msg": " YouTube targets not live "
        })
        time.sleep(40)
        queue.put({
            "streaming": False,
            "ffmpeg_starting": False,
            "face_conf_msg": " YouTube targets not live "
        })
        
def rtmp_stereo_to_mono(queue, src=None, dst=None):
    if not src:
        src = "rtmp://rtmp.tehiku.live:1935/rtmp/" + SOURCE_STREAM_NAME
    if not dst:
        dst = "rtmp://rtmp.tehiku.live:1935/rtmp/" + DEST_STREAM_NAME

    cmd = [
        'ffmpeg', '-re', '-loglevel', 'warning', '-i', src,
        '-c:v', 'copy',
        '-c:a', 'aac', '-ac', '1', '-ar', '44100', '-af', 'loudnorm=I=-16:TP=-1',
        '-f', 'flv', dst,
    ]

    # Check the stream exists:
    print("Waiting for stream")
    while not stream_exists(WOWZA_APP_NAME, SOURCE_STREAM_NAME):
        sleep(10)
    print("Stream exists")

    process = Popen(cmd, stderr=PIPE, stdout=PIPE)
    queue.put({"streaming": True, "ffmpeg_starting": False})
    print("Streaming")
    for line in process.stdout:
        sys.stdout.write(line)
    e = process.stderr.read()
    queue.put({
        "streaming": False,
        "ffmpeg_error": True,
        "error_message": e.decode().replace('\n', ' ')})

def main():
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)
    
    q = Queue()

    stream_toggle = Process(target=stream_should_start, args=(q,))
    ffmpeg_stream = Process(target=run_youtube, args=(q,))

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
    notify = Process(target=call_webhooks, args=(q,"Scheduled Stream Start process running"))
    notify.start()

    loop = True
    indi = '-/|\\-'
    count = 0
    is_streaming_count = 0
    wowza_data = None
    face_count = 0
    face_count_threshold = 2
    stream_count_threshold = 10
    while loop:
        sleep(.1)
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
                ffmpeg_stream = Process(target=run_youtube, args=(q,))

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

                sleep(2)
                ffmpeg_stream = Process(target=run_youtube, args=(q,))

                if not wowza_data:
                    wowza_data = wowza_get_targets()
                if messages['targets_enabled']:
                    toggle_stream_targets(q, wowza_data, False, default_stream_source=DEST_STREAM_NAME)
                
            elif messages['start_stream'] and not messages['streaming'] and not messages['ffmpeg_starting']:
                if ffmpeg_stream:
                    try:
                        ffmpeg_stream.start()
                        notify = Process(target=call_webhooks, args=(q,"FFMPEG process started"))
                        notify.start()
                    except Exception as e:
                        pass
                        ffmpeg_stream.terminate()
                        ffmpeg_stream = Process(target=run_youtube, args=(q,))
                        ffmpeg_stream.start()
                        messages['ffmpeg_starting'] = True

                if not wowza_data:
                    wowza_data = wowza_get_targets()


            elif messages['start_stream'] and messages['streaming'] and messages['has_face'] and 'done' not in messages['face_state']:
                
                if face_count > face_count_threshold:
                    print("Enable stream target")
                    # print(messages['has_face'])
                    # print(messages['face_state'])
                    if messages['has_face']:
                        messages['face_state'] = 'done'
                        try:
                            has_face.terminate()
                        except:
                            pass
                    if not wowza_data:
                        wowza_data = wowza_get_targets()

                    toggle_stream_targets(q, wowza_data, True, default_stream_source=DEST_STREAM_NAME)
                    messages['face_starting'] = False

                    notify = Process(target=call_webhooks, args=(q,"Face Threshold Met", ['Slack Automation Channel']))
                    notify.start()

                    notify = Process(target=call_webhooks, args=(q,"Stream Targets LIVE"))
                    notify.start()

                    # print(messages['face_state'])

            else:
                pass


            if is_streaming_count > stream_count_threshold and not messages['has_face'] and messages['face_state'] not in ['running', 'starting']:
                # Start face detection
                has_face = Process(target=get_face, args=(q,))
                face_count = 0
                
                if messages['face_state'] != 'starting':
                    try:
                        has_face.start()
                        # print("Start Face Detection")
                        messages['face_state'] = 'starting'
                    except:
                        pass

                notify = Process(target=call_webhooks, args=(q,"Start Face Detection", ['Slack Automation Channel']))
                notify.start()

            if 'face_count' in messages.keys():
                new_face_count = face_count + messages['face_count']
                del messages['face_count']
                if new_face_count != face_count:
                    face_count = new_face_count
                    messages['face_conf_msg'] = messages['face_conf_msg'] + f" found a face {face_count} times"
                

            STREAM_MSG = ''
            if messages['streaming'] and not messages['ffmpeg_error']:                
                if is_streaming_count > stream_count_threshold:
                    STREAM_MSG = f'{bcolors.OKGREEN}FFMPEG Streaming {indi[count]}{bcolors.ENDC}'

                elif is_streaming_count == stream_count_threshold:
                    is_streaming_count = is_streaming_count + 1
                else:
                    is_streaming_count = is_streaming_count + 1

            if is_streaming_count < stream_count_threshold and messages['start_stream']:
                STREAM_MSG = f'{bcolors.WARNING}FFMPEG Starting  {indi[count]}{bcolors.ENDC}'


            emsg = messages['error_message']
            if emsg:
                messages['error_message'] = ''

            fmsg = messages['face_conf_msg']
            if fmsg:
                messages['face_conf_msg'] = ''

            if not args.daemon:
                sys.stdout.flush()
                print(
                    f"\r{STREAM_MSG}\
{bcolors.FAIL}{emsg}{bcolors.ENDC}\
{bcolors.OKBLUE}{bcolors.BOLD}{fmsg}{bcolors.ENDC}{bcolors.ENDC}", end='', flush=True)


            if not stream_toggle.is_alive():
                notify = Process(target=call_webhooks, args=(q,"Stream Toggle process died"))
                notify.start()
                stream_toggle = Process(target=stream_should_start, args=(q,))
                stream_toggle.start()
                notify = Process(target=call_webhooks, args=(q,"Scheduled Stream Start process running"))
                notify.start()

            if not ffmpeg_stream.is_alive() and messages['ffmpeg_error']:
                notify = Process(target=call_webhooks, args=(q,"FFMPEG process died"))
                notify.start()

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
