from multiprocessing import Pool, Manager
from multiprocessing import TimeoutError
import pexpect
from pexpect import popen_spawn
import sys
import datetime
import urllib
import json
from send_email import Emailer, SlackPost
import time
import signal
import requests
import yaml

from subprocess import Popen, PIPE

filename = 'silence.log'
command = '/usr/local/bin/ffmpeg -i "http://radio.tehiku.live:8040/stream;1" -af silencedetect=d=3 -f null -'
# command = '/usr/local/bin/ffmpeg -i "output.aac" -af silencedetect -f null -'

STATIONS = [
    'Te Hiku',
    'Sunshine',
    #"Tai FM"
    ]
COMMANDS = [
    'ffmpeg -f dshow -i audio="Livewire In 01 (AXIA IP-Driver (WDM))" -af silencedetect=d=3 -f null -',
    'ffmpeg -f dshow -i audio="Livewire In 02 (AXIA IP-Driver (WDM))" -af silencedetect=d=3 -f null -',
    #'ffmpeg -f dshow -i audio="Livewire In 03 (AXIA IP-Driver (WDM))" -af silencedetect=d=3 -f null -'
    ]

# COMMANDS = [
#     '/usr/local/bin/ffmpeg -i "http://radio.tehiku.live:8030/stream;1" -af silencedetect=d=1 -f null -',
#     '/usr/local/bin/ffmpeg -i "http://radio.tehiku.live:8010/stream;1',
#     '/usr/local/bin/ffmpeg -i "http://radio.tehiku.live:8020/stream;1" -af silencedetect=d=1 -f null -']

API_URL = 'http://airtime.tehiku.live/api/live-info'





STREAM_CMD = \
    'streamlink https://www.youtube.com/watch?v={watch_id} best --stdout | ffmpeg -y -re -i pipe: -vn -ab 128k -acodec libvorbis -content_type audio/ogg -f ogg icecast://{ice_creds}@icecast.tehiku.radio:8000/youtube_ingest.ogg'


STREAM_CMD = \
    'streamlink "https://www.youtube.com/watch?v={watch_id}" best -O | ffmpeg -y -re -i pipe:0 -c:v copy -c:a copy -f flv "rtmp://rtmp.tehiku.live:1935/rtmp/youtube_ingest"'


STREAM_LINK = \
    'streamlink https://www.youtube.com/watch?v={watch_id} best -O'

FFMPEG_STREAM = \
    'ffmpeg -y -re -loglevel warning -i pipe:0 -c:v copy -c:a copy -f flv rtmp://rtmp.tehiku.live:1935/rtmp/youtube_ingest'

FFMPEG_STREAM = \
    'ffmpeg -y -re -loglevel warning -i pipe:0 -vn -ab 128k -acodec libvorbis -content_type audio/ogg -f ogg -legacy_icecast 1 icecast://{ice_creds}@libreice.sunshine.tehiku.radio:8002/show'


FFMPEG_STREAM = \
    'ffmpeg -y -re -loglevel warning -i pipe:0 -vn -ab 128k -acodec libvorbis -content_type audio/ogg -f ogg -legacy_icecast 1 icecast://source:password@3.24.134.152:8001/master'



GOOGLE_API = \
    "https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&eventType=live&type=video&key={google_api_key}"


CHANNELS = (
    ('Ministry of Health', 'UCPuGpQo9IX49SGn2iYCoqOQ'),
    # ('DOC', 'UCNXXjM3fkppSxEQIwBloIvA'),
    ('Le Chilled Cow', 'UCSJ4gkVC6NrvII8umztf0Ow')
)

with open("vault.yml", 'r') as file:
    CREDENTIALS = yaml.safe_load(file)

def get_watch_id(channel_id):
    url = GOOGLE_API.format(channel_id=channel_id, google_api_key=CREDENTIALS['google_api_key'])
    r = requests.get(url)
    result = r.json()
    try:
        video_id = result['items'][0]['id']['videoId'], result['items'][0]['id']['videoId']
        if type(video_id) == tuple:
            return video_id[0]
        return video_id
    except:
        print("Error getting watch id for {0}".format(channel_id))
        print(result)
        return None


def notify(station, silence_start, silence_end, **kwargs):
    # print 'sending email about silence!'
    now = datetime.datetime.now()

    msg =''
    if 'priority' in kwargs.keys():
        if 'ALERT' in kwargs['priority']:
            email = Emailer()
            msg = '{0} {1} DEAD AIR for longer than 1 MINUTE!!!'.format(
                    station,
                    'AXIA'
                )
            email.text = msg
            email.subject = msg
            email.html = '<html><body><p>{0}</p></body></html>'.format(msg)
            for e in ['keoni@tehiku.nz', 'jamason@tehiku.nz', 'maria@tehiku.nz', 'riki@tehiku.co.nz']:
                email.to = e
                email.send()

            try:
                s = SlackPost()
                s.data = {"text": msg}
                s.send()
            except:
                pass

        elif 'STARTUP' in kwargs['priority']:
            email = Emailer()
            msg = '{0} {1} SILENCE DETECTOR STARTED'.format(
                    station,
                    'AXIA'
                )
            email.text = msg
            email.subject = msg
            email.html = '<html><body><p>{0}</p></body></html>'.format(msg)
            for e in ['keoni@tehiku.nz']:#], 'rahu@tehiku.nz', 'maria@tehiku.nz']:
                email.to = e
                email.send()

            try:
                s = SlackPost()
                s.data = {"text": msg}
                s.send()
            except:
                pass

        else:
            pass

        print(msg)

    else:

        try:
            silence_end = float(silence_end.strip())
        except:
            silence_end = 0
        try:
            silence_start = float(silence_start.strip())
        except:
            silence_start = 0

        started = now - datetime.timedelta(seconds=silence_end-silence_start)

        if 'hiku' in station.lower():
            response = urllib.urlopen(API_URL)
            data = json.loads(response.read())
            current_song = data['current']['name']
        else:
            data = None
            current_song = 'Not Available'

        msg = '{4} - AXIA - silence\t{0}\t{1}\t{2}\t\t{3}'.format(
            started.strftime('%Y-%d-%m %H:%M:%S'),
            now.strftime('%Y-%d-%m %H:%M:%S'),
            silence_end-silence_start,
            current_song,
            station)

        print(msg)

        email = Emailer()
        email.text = msg

        if data is not None:
            email.html = """<html><body>
            <code>{0}</code>
            <h4>Song Info</h4>
            <p>Name: {1}</p>
            <p>Starts: {2}</p>
            <p>End: {3}</p>
            <p>Type: {4}</p>
            </body></html>""".format(
                msg,
                data['current']['name'],
                data['current']['starts'],
                data['current']['ends'],
                data['current']['type'],)
        else:
            email.html = """<html><body>
            <code>{0}</code>
            </body></html>""".format(
                msg)

        email.to = 'keoni@tehiku.nz'
        email.subject = '{2} - Silence Detected - {0} - {1}'.format(
            started.strftime('%Y-%d-%m %H:%M:%S'),
            current_song,
            station)
        email.send()

        if 'hiku' in station.lower():
            email.to = 'rahu@tehiku.nz'
            email.send()
            email.to = 'riki@tehiku.nz'
            email.send()
        else:
            email.to = 'rahu@tehiku.nz'
            email.send()
            email.to = 'maria@tehiku.nz'
            email.send()

        s = SlackPost()
        s.data = {"text": msg}
        s.send()


def run_silence_detection(station, command, q):
    silence_start = 0
    silence_end = 0
    thread = pexpect.popen_spawn.PopenSpawn(command)
    cpl = thread.compile_pattern_list(
        [pexpect.EOF, '\[silencedetect .*] (.*)'])

    silence_started = None
    timer = datetime.timedelta(seconds=0)

    notify(station, 0, 0, priority='STARTUP')

    print('Listening to {0}'.format(station))

    while True:
        if silence_started is not None:
            timer = datetime.datetime.now() - silence_started

        i = thread.expect_list(cpl, timeout=None)
        if i == 0:  # EOF
            if silence_started is not None:
                print("ffmpeg exited AFTER silence detected!")
                notify(station, silence_start, 0, priority='ALERT')
            print("the sub process exited")
            break
        elif i == 1:
            out = thread.match.group(1).strip()

            if 'silence_start' in out:
                silence_start = out.split(': ')[1]

                silence_started = datetime.datetime.now()
                # print "Silence detection started: {0}".format(silence_start)
                msg = {station: {'start': silence_started}}
                q.put(msg)

            elif 'silence_end' in out:
                silence_end = out.split('|')[0].split(': ')[1]
                notify(station, silence_start, silence_end)
                silence_started = None
                q.put({station: {'end': datetime.datetime.now()}})

        time.sleep(0.4)

    thread.close()

def ingest_video(watch_id, queue):
    command = STREAM_CMD.format(watch_id=watch_id, ice_creds=CREDENTIALS['ice_creds'])
    # thread = pexpect.popen_spawn.PopenSpawn(command)
    # cpl = thread.compile_pattern_list(
    #     [pexpect.EOF, '\[silencedetect .*] (.*)'])
    # print(command)
    # child = pexpect.spawn('/bin/bash')
    # child.sendline(command)
    print("Starting stream...")

    # queue.put({'message': "Starting stream {0}".format(command)})
    # result = child.expect('Closing currently open stream')
    # print("Exited")
    # queue.put({
    #     'message': "Stream ended",
    #     'ingesting': False})

    print(STREAM_LINK.format(watch_id=watch_id))
    print(FFMPEG_STREAM.format(ice_creds=CREDENTIALS['ice_creds']))
    p1 = Popen(STREAM_LINK.format(watch_id=watch_id).split(' '), stdout=PIPE, stderr=PIPE)
    p2 = Popen(
        FFMPEG_STREAM.format(ice_creds=CREDENTIALS['ice_creds']).split(' '),
        stdin=PIPE,
        stderr=PIPE,
        stdout=PIPE)
    
    while True:
        output = p1.stdout.readline()
        p2.stdin.write(output)
        # print(output)
        # print(p2.stdout.readline())
        # print(p2.stderr.readline())
        # print(p2.stdout.readline())
        # print(p1.stderr.readline())
        # output = p2.stdout.readline()
        # if p2.poll() is not None:
            # break
        # if output:
            # print(output.strip())

    # print(o)
    # print(e)


    # s = SlackPost()
    # s.data = {"text": "Stream stopped."}
    # s.send()

    # while True:
    #     # print("Running {0}".format(command))
    #     exit = thread.wait()
    #     if exit == 0:
    #         print("Good finsh")
    #     elif exit == 1:
    #         print("Error")
    #         break
    #     else:
    #         print(exit)


def run():

    NUM_PROC = 1
    # killer = GracefulKiller()
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)

    pool = Pool(processes=NUM_PROC)
    m = Manager()
    q = m.Queue()

    messages = {}

    loop = True
    watching = False

    while loop:
        try:
            if not watching:
                print("Checkign channels...")
                for channel in CHANNELS:
                    watch_id = get_watch_id(channel[1])
                    if watch_id is not None:
                        break
                    time.sleep(2)

            if watch_id and not watching:
                print("Ingesting {0}".format(watch_id))
                watching = True

                res = pool.apply_async(ingest_video, (watch_id, q))

            try:
                message = q.get_nowait()
                for k in message.keys():
                    messages[k] = message[k]
            except:
                pass

            for key in messages.keys():
                if 'ingesting' == key:
                    if messages[key]:
                        print("Ingesting")
                    else:
                        print("Ingestion stopped")
                        watching = False
                        watch_id = None                 
                        # # ALERT
                        notify(
                            key, messages[key]['start'], 0, priority='ALERT')
                        messages[key]['sent'] = True
                if 'message' == key:

                    pass
                    # s = SlackPost()
                    # s.data = {"text": messages[key]}
                    # s.send()

            time.sleep(60)
            continue

        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, terminating workers")
            pool.terminate()
            loop = False
        except Exception as e:
            print("All detectors died")
            print(e)
            pool.close()
            loop = False
        else:
            print("Normal termination")
            pool.close()
            loop = False


def main():
    run()


if __name__ == "__main__":    
    main()