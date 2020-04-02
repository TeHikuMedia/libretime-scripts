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

timezone = pytz.timezone("Pacific/Auckland")

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

START_TIME = datetime.strptime('2020/04/02 13:00:00', '%Y/%m/%d %H:%M:%S').astimezone(timezone)
END_TIME = datetime.strptime('2020/04/02 17:00:00', '%Y/%m/%d %H:%M:%S').astimezone(timezone)

# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    
    LOGFILE = os.path.join(d['log_path'], 'db.mgmt.log')
    if not os.path.exists(LOGFILE):
        Popen(['touch', LOGFILE])
    TMP_DIR = d['tmp_dir']
    SLUG = d['project_slug']
    USER = d['wowza']['user']
    PASSWORD = d['wowza']['password']
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
    while not success:
        RESOURCE = "applications/rtmp/pushpublish/mapentries"
        r = requests.get(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS)
        data = r.json()
        try:
            success = data['success']
        except KeyError:
            success = True

    return data


def toggle_stream_targets(queue, start_time=START_TIME, end_time=END_TIME):

    data = wowza_get_targets()

    # TODO
    '''
    Get the start and stop from an API
    Check the API every 5 minutes for schedule change?
    - webhook better! -
    '''

    entries = ['Push to tehiku.radio', 'Sunshine Radio']
    ENABLED = False
    while not ENABLED:
        # Get list of stream targets

        NOW = datetime.utcnow().replace(tzinfo=pytz.utc)
        NOW = timezone.localize(NOW)
        try:
            for target in entries:
                # print(target)
                for entry in data['mapEntries']:
                    if target in entry['entryName']:
                        st = entry

                        if start_time > NOW:
                            # Stream shoudl be disabled
                            if st['enabled']:
                                print('\nDisabling stream targets')
                                st['enabled'] = False
                                RESOURCE = "applications/rtmp/pushpublish/mapentries/" + entry['entryName']
                                wowza_put_data(RESOURCE, st)
                        elif start_time <= NOW and end_time >= NOW:
                            if not st['enabled']:
                                print("\nEnabling stream targets")
                                st['enabled'] = True
                                RESOURCE = "applications/rtmp/pushpublish/mapentries/" + entry['entryName']
                                wowza_put_data(RESOURCE, st)

                            queue.put({'start_stream': True})

                        elif end_time <= NOW:
                            if  st['enabled']:
                                print("\nDisabling stream targets")
                                st['enabled'] = False
                                RESOURCE = "applications/rtmp/pushpublish/mapentries/" + entry['entryName']
                                wowza_put_data(RESOURCE, st)

                            queue.put({'start_stream': False})

            time.sleep(1)

        except Exception as e:
            print(e)
            queue.put({'terminate': True})
            return

        except KeyboardInterrupt as e:
            ENABLED = True
            queue.put({'terminate': True})
            return



def rtmp_stereo_to_mono(queue, src=None, dst=None):
    if not src:
        src = "rtmp://rtmp.tehiku.live:1935/rtmp/test"
    if not dst:
        dst = "rtmp://rtmp.tehiku.live:1935/rtmp/teaonews_mono"

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

    stream_toggle = Process(target=toggle_stream_targets, args=(q,))
    ffmpeg_stream = Process(target=rtmp_stereo_to_mono, args=(q,))

    messages = {
        'streaming': False,
        'start_stream': False,
        'terminate': False,
        'ffmpeg_error': False,
        'ffmpeg_starting': False,
        'error_message': ''
    }

    stream_toggle.start()

    loop = True
    indi = '-/|\\-'
    count = 0
    is_streaming_count = 0

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
                messages['ffmpeg_error'] = False
                messages['streaming'] = False
                messages['ffmpeg_starting'] = False
                is_streaming_count = 0
                ffmpeg_stream = Process(target=rtmp_stereo_to_mono, args=(q,))

            elif messages['start_stream'] and not messages['streaming'] and not messages['ffmpeg_starting']:
                # Scheduled start

                messages['ffmpeg_starting'] = True
                if ffmpeg_stream:
                    ffmpeg_stream.start()

            else:
                pass

            sleep(.1)

            try:
                message = q.get_nowait()
                for k in message.keys():
                    messages[k] = message[k]
            except:
                # No messages
                pass

            if messages['streaming'] and not messages['ffmpeg_error']:                
                if is_streaming_count > 10:
                    sys.stdout.flush()
                    print(f'{bcolors.OKGREEN}\rFFMPEG Streaming {indi[count]}{bcolors.ENDC}', end='', flush=True)
                elif is_streaming_count == 10:
                    print(flush=True)
                    is_streaming_count = is_streaming_count + 1
                else:
                    is_streaming_count = is_streaming_count + 1

            if is_streaming_count < 10 and messages['start_stream']:
                print(
                    f"{bcolors.WARNING}\rFFMPEG Starting {indi[count]}{bcolors.ENDC}{bcolors.FAIL} {messages['error_message']}{bcolors.ENDC}", end='', flush=True)
                messages['error_message'] = ''

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
