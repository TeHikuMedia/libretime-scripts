from subprocess import Popen
import glob
import os


BASE_SOURCE_DIRECTORY = r'Y:\\'

SEARCH_DIR = os.path.join(BASE_SOURCE_DIRECTORY, '\\#WORKING\\Ads\\English\\Cat A')
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
    
    source = 'Y:\\#WORKING\\Ads\\English\\Cat A'
    output = 'Y:\\#WORKING\\Ads_checked\\English\\Cat A'
    source = os.path.join(source,file)
    output = os.path.join(output,file)

    print(source)
    print(output)
    
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
        run = [
            'ffmpeg', '-y', 
            '-i', source,
            '-codec:a',
            'copy', 
            #'-b:a',
            #'160k', 
            output]

        #p = Popen(run)

    elif round(duration) != round(tag_length):
        print("Message:      Tag is different",duration)
        run = [
            'ffmpeg', '-y', 
            '-i', source,
            '-codec:a',
            'copy', 
            #'-b:a',
            #'160k', 
            output]

        #p = Popen(run)

    else:
        print("Message: Tag length is correct.")


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
