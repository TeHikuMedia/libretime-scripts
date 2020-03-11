from datetime import datetime, timedelta
from subprocess import Popen, PIPE
from math import floor
import json
import os

def time_string(length):
    length = str(length)
    secs = int(length.split('.')[0])
    hunds = int(round(float(length.split('.')[1][0:2])/10))
    mins = int(floor(int(secs)/60.))
    secs = int(secs - 60*mins)
    length = float(length)
    return { 'mins':mins , 'secs':secs , 'hunds':hunds , 'length':length}

def convert_media(from_format, to_format, file_path):
    cmd = 'ffmpeg -y -i "%s" -c:a libvorbis -q:a 5 "%s"' % ( file_path, file_path.replace(from_format,to_format) )
    Popen(cmd.split(' '))
    Popen(['rm',file_path])
    return file_path.replace('from_format','to_format')

def scale_media(file_path, target_length, length=0, max_scale=0.05, max_seconds_delta=1):
    if length==0:
        command = 'ffprobe -i %s -show_entries format=duration -v quiet -of json'%(file_path)
        p = Popen(command.split(' '), stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        data = json.loads(out)
        media_length = time_string(str(data['format']['duration']))
        length = media_length['length']

    if abs(target_length - length)<max_seconds_delta:
        print("Not Scaling as Duration is withing %d seconds."%(max_seconds_delta))
        scale = 1

    else:
        scale = length/target_length
        if scale>(1+max_scale): scale = 1+max_scale
        elif scale < (1-max_scale): scale = 1-max_scale
        print("Length = %d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds']))
        print("Target Length = %d"%(target_length))
        print("Scaling by %0.04f"%(scale))

        path = '/'.join(file_path.split('/')[0:-1])
        out = os.path.join(path, 'out.'+file_path.split('.')[-1])
        cmd = 'ffmpeg -i %s -filter:a "atempo=%0.04f" -vn %s'%(file_path,scale,out)
        Popen(cmd.split(' '))
        Popen(['mv', out, file_path])

    return time_string(str(scale*length))


def media_type(s): ### <= if i make this an attr vs a function i can use it in templates!
    '''Figures out and returns the media type of self.media_file'''
    return s.split('?')[0].split('.')[-1].lower()
    
def is_image(s):
    return True if s in 'png jpg jpeg gif svg bmp' else False

def is_video(s):
    return True if s in 'mp4 mov avi m4v m3u8 flv 3gp wmv ts' else False

def is_audio(s):
    return True if s in 'mp3 wav m4a aiff mid snd au m3u aac' else False

def convert_audio(file):
    new_file_name = file.split('.')[0]+'_CONVERTED.m4a'
    command = '/usr/bin/ffmpeg -y -i {0} -b:a 128k {1}'.format(file, new_file_name)
    p = Popen(command.split(' '), stdout=PIPE, stderr=PIPE)
    data, err =p.communicate()

    return new_file_name
