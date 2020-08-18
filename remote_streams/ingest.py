from multiprocessing import Process, Queue
from multiprocessing import TimeoutError
import pexpect
from pexpect import popen_spawn
import sys
import datetime
import urllib
import json
import time
import signal
import requests
import yaml
import os

from remote_streams.settings import CONF_FILE

from subprocess import Popen, PIPE


STREAM_LINK = \
    'streamlink https://www.youtube.com/watch?v={watch_id} 720p,best -O'

FFMPEG_STREAM = \
    'ffmpeg -y -loglevel warning -i pipe:0 -c:v copy -c:a copy -bsf:a aac_adtstoasc -f flv rtmp://rtmp.tehiku.live:1935/rtmp/youtube_ingest'

GOOGLE_API = \
    "https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&eventType=live&type=video&key={google_api_key}"


CHANNELS = (
    # ('Ministry of Health', 'UCPuGpQo9IX49SGn2iYCoqOQ'),
    # ('RNZ', 'UCRUisv_fP2DKSoR2pywxY9w'),
    # ('Te Hiku TV', 'UCBxnxeNnW-xE8MTnTSVNO2A'),
    ('Le Chilled Cow', 'UCSJ4gkVC6NrvII8umztf0Ow'),
    # ('Random', 'UCuWuAvEnKWez5BUr29VpwqA'),
)

# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    GOOGLE_API_KEY = d['google_api_key']
    ICECAST_CREDS = d['icecast_credentials']
    LOGDIR = d['log_path']
    LOG_FILE = os.path.join(LOGDIR, 'face_detect.log')
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'a').close()
        os.chmod(LOG_FILE, stat.S_IRUSR | stat.S_IWUSR |
                 stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)

except KeyError as e:
    print('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    print('Could not read configuration file {0}.'.format(CONF_FILE))
    raise


def get_watch_id(channels, queue):
    watch_id = None
    for channel in channels:
        channel_id = channel[1]

        url = GOOGLE_API.format(channel_id=channel_id,
                                google_api_key=GOOGLE_API_KEY)
        r = requests.get(url)
        result = r.json()
        try:
            video_id = result['items'][0]['id']['videoId'], result['items'][0]['id']['videoId']
            if type(video_id) == tuple or type(video_id) == list:
                watch_id = video_id[0]
            else:
                watch_id = video_id
            break
        except:
            print("Error getting watch id for {0}".format(channel_id))
            print(result)
    queue.put({'watch_id': watch_id})


def ingest_video(watch_id, queue):
    queue.put({'status': 'Starting stream...'})
    CMD = '{0} | {1}'.format(
        STREAM_LINK.format(watch_id=watch_id),
        FFMPEG_STREAM.format(ice_creds=ICECAST_CREDS)
    )
    print(CMD)
    process = Popen(CMD, shell=True, stderr=PIPE, stdout=PIPE)
    
    for line in process.stdout:
        sys.stdout.write(line)
    e = process.stderr.read()
    e = e.decode().replace('\n', ' ')
    if 'error' in e.lower():
        queue.put({'status': 'error', 'error': e})
    else:
        queue.put({'status': 'done'})



def run():

    NUM_PROC = 1
    # killer = GracefulKiller()
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)

    # pool = Pool(processes=NUM_PROC)
    # m = Manager()
    # q = m.Queue()


    q = Queue()

    ingest = Process(target=ingest_video, args=(None, q))
    watch_id = None
    fetch_watch_id = Process(target=get_watch_id, args=(CHANNELS, q))
    fetch_watch_id.start()

    messages = {}

    loop = True
    watching = False

    while loop:
        try:
            # if not watching:
            #     print("Checkign channels...")
            #     for channel in CHANNELS:
            #         watch_id = get_watch_id(channel[1], q)
            #         if watch_id is not None:
            #             break
            #         time.sleep(2)

            if watch_id and not watching:
                print("Ingesting {0}".format(watch_id))
                watching = True
                ingest = Process(target=ingest_video, args=(watch_id, q))
                ingest.start()
                # res = pool.apply_async(ingest_video, (watch_id, q))

            try:
                message = q.get_nowait()
                if message:
                    for k in message:
                        messages[k] = message[k]
            except Exception as e:
                pass


            if 'status' in messages:
                status = messages['status']
                del messages['status']
                print(status)
                if status == 'done':
                    print('Stream done.')
                    raise
                elif status == 'error':
                    print(messages['error'])
                    raise

            if 'watch_id' in messages:
                print("Found Watch ID")
                watch_id = messages['watch_id']
                del messages['watch_id']

            time.sleep(1)
            continue

        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, terminating workers")
            # .terminate()
            loop = False
        # except Exception as e:
        #     print("All detectors died")
        #     print(e)
        #     # pool.close()
        #     loop = False
        else:
            print("Normal termination")
            # pool.close()
            loop = False


def main():
    run()


if __name__ == "__main__":
    main()
