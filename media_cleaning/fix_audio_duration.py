from mutagen.easyid3 import EasyID3
from subprocess import Popen, PIPE
import os
import glob 
import json

BASE_SOURCE_DIRECTORY = 'Y:\\'
    
TEST_DIR = os.path.join(BASE_SOURCE_DIRECTORY, '*\\')
print('Scanning' +TEST_DIR)

print(os.listdir(BASE_SOURCE_DIRECTORY))

##for item in glob.glob(BASE_SOURCE_DIRECTORY):
##    print(item)


SEARCH_DIR = os.path.join(BASE_SOURCE_DIRECTORY, 'Station ID\\English')
os.chdir(SEARCH_DIR)
for item in glob.glob(r'[*.mp3|MP3|wav|flacc|mp4|m4a]'):
    print(item)

audio_files = glob.glob(r'*.mp3')
audio_files.extend(glob.glob(r'*.MP3'))
audio_files.extend(glob.glob(r'*.m4a'))
audio_files.extend(glob.glob(r'*.mp4'))
audio_files.extend(glob.glob(r'*.wav'))
audio_files.extend(glob.glob(r'*.flac'))

#count = 0

for file in audio_files:
    print(file)

    cmd = [
         'ffprobe',
         '-i', file,
         '-show_entries',
         'format=duration',
         '-v', 'quiet',
         '-of', 'json']
     
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate()

    print('Output:\t', output)
    print('Error: \t', error)

    data = json.loads(output)


    duration = float(data['format']['duration'])*1000
    print('Duration:', duration,'ms')

    try:
        audio = EasyID3(file)
        tag_length  = float(audio['length'][0])
    except IndexError:
            print('ERROR:     Something is janky...')
            continue
    except KeyError:
        tag_length = None
    except Exception as error:
        print(error)
        continue
        
    print('Tag Length', tag_length)

    if tag_length is None:
        print("Message:      Tag is None, setting to", duration)
        audio['length'] = str(duration)
        audio.save()

    elif round(duration) != round(tag_length):
        print("Message:      Tag is different",duration)
        audio['length'] = str(duration)
        audio.save()

    else:
        print("Message: Tag length is correct.")

    audio = EasyID3(file)
    tag_length = audio['length']
    
    print('TAG LENGTH: ', tag_length)
    print('')

   #count = count + 1

   #if count > 5:
    #   break
