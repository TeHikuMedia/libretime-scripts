from subprocess import Popen
import glob
import os


BASE_SOURCE_DIRECTORY = r'Y:\\'

SEARCH_DIR = os.path.join(BASE_SOURCE_DIRECTORY, '\\Station ID\\English')
os.chdir(SEARCH_DIR)

audio_files = glob.glob(r'*.mp3')
audio_files.extend(glob.glob(r'*.MP3'))
audio_files.extend(glob.glob(r'*.m4a'))
audio_files.extend(glob.glob(r'*.mp4'))
audio_files.extend(glob.glob(r'*.wav'))
audio_files.extend(glob.glob(r'*.flac'))

# count = 0

for file in audio_files:
    print(file)
    
    source = 'Y:\\Station ID\\English'
    output = 'Y:\\Station ID\\Converted'
    source = os.path.join(source,file)
    output = os.path.join(output,file)

    print(source)
    print(output)
    
    run = [
            'ffmpeg', '-y', 
            '-i', source,
            '-codec:a',
            'copy', 
            #'-b:a',
            #'160k', 
            output]

    p = Popen(run)

    count = count +1

    if count == 1:
        break

#cmd = [
         #'ffprobe',
         #'-i', file,
         #'-show_entries',
         #'format=duration',
         #'-v', 'quiet',
         #'-of', 'json']
