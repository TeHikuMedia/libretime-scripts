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
    'streamlink https://www.youtube.com/watch?v={watch_id} best --stdout | ffmpeg -y -re -i pipe: -vn -ab 128k -acodec libvorbis -content_type audio/ogg -f ogg icecast://TeHikuMedia:Ku4ka1840@libreice.tehiku.radio:8001/master'


GOOGLE_API = \
    "https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&eventType=live&type=video&key={google_api_key}"


CHANNELS = (
    ('World Surf Leageu', 'UChuLeaTGRcfzo0UjL-2qSbQ'),
    ('Ministry of Health', 'UCPuGpQo9IX49SGn2iYCoqOQ')
)

with open("vault.yaml", 'r') as file:
    CREDENTIALS = yaml.safe_load(file)

def get_watch_id(channel_id):
    url = GOOGLE_API.format(channel_id=channel_id)
    r = requests.get(url)
    result = r.json()
    try:
        return result['items'][0]['id']['videoId']
    except:
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
    command = STREAM_CMD.format(watch_id=watch_id)
    thread = pexpect.popen_spawn.PopenSpawn(command)
    cpl = thread.compile_pattern_list(
        [pexpect.EOF, '\[silencedetect .*] (.*)'])

def run():

    NUM_PROC = 1
    # killer = GracefulKiller()
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)

    pool = Pool(processes=NUM_PROC)
    m = Manager()
    q = m.Queue()

    # results = []
    messages = {}


    # for i in range(NUM_PROC):
    #     command = COMMANDS[i]
    #     station = STATIONS[i]
    #     messages[station]={'init':True}
    #     res = pool.apply_async(run_silence_detection, (station, command, q))
    #     results.append(res)

    loop = True
    watching = False

    while loop:
        try:


            for channel in CHANNELS:
                watch_id = get_watch_id(channel[1])
                if watch_id:
                    break
                else:
                    continue

            if watch_id and not watching:
                watching = True
                # Do some stuff
                res = pool.apply_async(ingest_video, (watch_id, q))



            sum_r = 0
            for i in range(NUM_PROC):
                r = results[i]
                if r.ready():
                    sum_r = sum_r + 1

            if sum_r == 3:
                raise Exception

            try:
                message = q.get_nowait()
                for k in message.keys():
                    messages[k] = message[k]
            except:
                pass

            for key in messages.keys():
                if 'end' in messages[key].keys():
                    del messages[key]
                elif 'sent' in messages[key].keys():
                    continue
                elif 'start' in messages[key].keys():
                    delta = datetime.datetime.now() - messages[key]['start']
                    if delta.total_seconds() > 60:
                        # ALERT
                        notify(
                            key, messages[key]['start'], 0, priority='ALERT')
                        messages[key]['sent'] = True

            time.sleep(15)
            continue

        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, terminating workers")
            pool.terminate()
            loop = False
        except Exception:
            print("All detectors died")
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