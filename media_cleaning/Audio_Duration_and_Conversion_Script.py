from subprocess import Popen, PIPE
from mutagen.easyid3 import EasyID3
import mutagen
import glob
import os
import json
from pathlib import Path

BASE_SOURCE_DIRECTORY = 'Y:\\'

# SEARCH_DIR = os.path.join(BASE_SOURCE_DIRECTORY, '\\#WORKING\\Ads\\English\\#Remake')
SEARCH_DIR = os.path.join(BASE_SOURCE_DIRECTORY, '\\Music\\')
DESTINATION_DIR = os.path.join(BASE_SOURCE_DIRECTORY, '\\~WORKING\\')
os.chdir(SEARCH_DIR)

audio_files = glob.glob(r'*.mp3')
audio_files.extend(glob.glob(r'*.MP3'))
audio_files.extend(glob.glob(r'*.m4a'))
audio_files.extend(glob.glob(r'*.mp4'))
audio_files.extend(glob.glob(r'*.wav'))
audio_files.extend(glob.glob(r'*.flac'))

all_files_count = 0
files_to_check_count = 0
files_to_fix_count = 0
for root, dirs, files in os.walk(SEARCH_DIR):

    for file in files:
        all_files_count = all_files_count + 1

        if file[0] == '.':
            continue
        elif file.split('.')[-1].lower() not in 'mp3 m4a mp4 wav flac':
            continue

        # print(file)
        files_to_check_count = files_to_check_count + 1

        source = os.path.join(root, file)
        BASE_OUT = root.replace(BASE_SOURCE_DIRECTORY, DESTINATION_DIR)
        output = os.path.join(BASE_OUT, file)

        Path(BASE_OUT).mkdir(parents=True, exist_ok=True)

        # print(source)
        # print(output)

        cmd = [
             'ffprobe',
             '-i', source,
             '-show_entries',
             'format=duration',
             '-v', 'quiet',
             '-of', 'json']
         
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        data, error = p.communicate()

        # print('Data:\t', data)
        # print('Error: \t', error)

        data = json.loads(data)


        duration = float(data['format']['duration'])*1000
        # print('Duration:', duration,'ms')

        try:
            audio = mutagen.File(source, easy=True)
            tag_length  = float(audio['length'][0])
        except IndexError:
                print('ERROR: Something is janky...')
                continue
        except KeyError:
            try:
                tag_length  = float(audio['TLEN'][0])
            except KeyError:
                tag_length = None
        except Exception as error:
            print(error)
            continue
            
        # print('Tag Length', tag_length)

        if tag_length is None or round(duration) != round(tag_length):
            files_to_fix_count = files_to_fix_count + 1
            print("Fixing {0} with TLEN {1} vs {2}".format(source, tag_length, duration))
            run = [
                'ffmpeg', '-y', 
                '-i', source,
                '-codec:a',
                'copy', 
                #'-b:a',
                #'160k', 
                output]

            # p = Popen(run)

        else:
            continue
            # print("Message: Tag length is correct.")

print("Scanned: {0}".format(all_files_count))
print("Checked: {0}".format(files_to_check_count))
print("Fixed:   {0}".format(files_to_fix_count))


# *********************************************************
#     run = [
#             'ffmpeg', '-y', 
#             '-i', source,
#             '-codec:a',
#             'copy', 
#             #'-b:a',
#             #'160k', 
#             output]

#     p = Popen(run)

#     #count = count +1

#     #if count == 1:
#         #break

# #cmd = [
#          #'ffprobe',
#          #'-i', file,
#          #'-show_entries',
#          #'format=duration',
#          #'-v', 'quiet',
#          #'-of', 'json']
