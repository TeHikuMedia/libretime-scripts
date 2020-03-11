# fix_audio_duration.py

from mutagen.easyid3 import EasyID3
from subprocess import Popen, PIPE
import os
import glob
import json

BASE_DIRECTORY_OSX = '/Volumes/Sunshine_Radio_Database'
BASE_DIRECTORY_WIN_JAMASON = r'Y:\\'
SEARCH_DIR = os.path.join(BASE_DIRECTORY_OSX, 'Unsorted/')
os.chdir(SEARCH_DIR)


audio_files = glob.glob(r'*.mp3')
audio_files.extend(glob.glob(r'*.MP3'))
audio_files.extend(glob.glob(r'*.m4a'))
audio_files.extend(glob.glob(r'*.mp4'))
audio_files.extend(glob.glob(r'*.wav'))
audio_files.extend(glob.glob(r'*.flac'))

count = 0
for file in audio_files:
    print(file)

    command = [
        'ffprobe',
        '-i', file,
        '-show_entries', 'format=duration',
        '-v', 'quiet',
        '-of', 'json'
    ]

    p = Popen(command, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate()

    print('Output:     ', output)
    print('Error:      ', error)

    data = json.loads(output)

    duration = float(data['format']['duration'])*1000
    print('Duration:   ', duration, 'ms')

    audio = EasyID3(file)

    try:
        tag_length = float(audio['length'][0])
    except IndexError:
        print('ERROR:      Something is janky...')
        continue
    except KeyError:
        tag_length = None

    print('Tag Length: ', tag_length)

    if tag_length is None:
        print("Message:     Tag is None, setting to", duration)
        audio['length'] = str(duration)
        audio.save()
    elif round(duration) != round(tag_length):
        print("Message:     Tag is different, setting to", duration)
        audio['length'] = str(duration)
        audio.save()
    else:
        print("Message:     Tag length is correct.")

    audio = EasyID3(file)
    tag_length = audio['length'][0]
    print('TAG LENGTH: ', tag_length)
    print('')

    count = count + 1

    if count > 10:
        break
    

    # break



