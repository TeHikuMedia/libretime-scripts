from datetime import datetime, timedelta
import commands 
from math import floor


def time_string(length):
    length = str(length)
    secs = int(length.split('.')[0])
    hunds = int(round(float(length.split('.')[1][0:2])/10))
    mins = int(floor(int(secs)/60.))
    secs = int(secs - 60*mins)
    length = float(length)
    return { 'mins':mins , 'secs':secs , 'hunds':hunds , 'length':length}

def convert_media(from_format, to_format, file_path):
    data = commands.getstatusoutput( 'ffmpeg -y -i "%s" -c:a libvorbis -q:a 5 "%s"' % ( file_path, file_path.replace(from_format,to_format) ) )
    commands.getstatusoutput('rm %s'%(file_path))
    return file_path.replace('from_format','to_format')

def scale_media(file_path, target_length, length=0, max_scale=0.05, max_seconds_delta=1):
    if length==0:
        media_length = time_string(commands.getstatusoutput('ffprobe -i %s -show_entries format=duration -v quiet -of csv="p=0"'%(file_path))[1])
        length = media_length['length']

    if abs(target_length - length)<max_seconds_delta:
        print "Not Scaling as Duration is withing %d seconds."%(max_seconds_delta)
        scale = 1

    else:
        scale = length/target_length
        if scale>(1+max_scale): scale = 1+max_scale
        elif scale < (1-max_scale): scale = 1-max_scale
        print "Length = %d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
        print "Target Length = %d"%(target_length)
        print "Scaling by %0.04f"%(scale)
        cmd = 'ffmpeg -i %s -filter:a "atempo=%0.04f" -vn %s'%(file_path,scale,'_'+file_path)
        commands.getstatusoutput(cmd)
        commands.getstatusoutput('mv %s %s'%('_'+file_path , file_path))

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

    data = commands.getoutput(command)
    #
    #print data
    return new_file_name
