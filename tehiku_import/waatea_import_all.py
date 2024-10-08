import taglib
import mutagen
import re
from datetime import datetime, timedelta
import json
import subprocess
from math import floor
from ftplib import FTP
from os import fchown
from pwd import getpwnam
from grp import getgrnam
import os
from settings import BASE_MEDIA_DIR


def filter_file(file_name, xml_data, hour, ampm):
    results = re.findall(r'<title>(.*)</title>', xml_data)
    if results:
        title = results[0]
        if 'WAATEA' in title:
            search = re.escape(str(hour)) + r'\.(.*)' + re.escape(ampm) + 'm'
            match = re.findall(search, title)
            if match:
                return file_name


file_path = os.path.join(BASE_MEDIA_DIR, 'waatea_news')

if not os.path.exists(BASE_MEDIA_DIR):
    os.mkdir(BASE_MEDIA_DIR)

if not os.path.exists(file_path):
    os.mkdir(file_path)

start_time = datetime.now()

ftp = FTP('ftp.irirangi.net')
ftp.login('NGWAN_Upload', 'ngwanupload')
ftp.cwd('MP3_News')
items = []
ftp.retrlines('NLST', lambda x: items.append(x))

for hour_increment in range(7, 19):

    time = datetime.strptime('2015-12-09 %02d:00' %
                             (hour_increment), '%Y-%m-%d %H:%M')

    hour = int(time.strftime('%I'))  # always want to get an hour ahead!
    ampm = time.strftime('%p').split('M')[0].lower()

    print(hour, ampm)

    f_id = ''
    chosen = []
    for item in items:
        if 'xml' in item:
            ftp.retrlines(f'RETR {item}', lambda x: chosen.append(
                filter_file(item, x, hour, ampm)))
    chosen = [i.replace('.xml', '') for i in chosen if i is not None]
    if chosen:
        f_id = chosen[0]

    if f_id == '':
        print("No News for this Hour")
        continue
        # raise NameError('news sport %s%s'%(hour,ampm))

    f_name = 'Waatea_News_%s%s.mp3' % (hour, ampm)
    target_length = 60*6.0

    ftp.retrbinary('RETR %s.MP3' % (f_id), open(f_name, 'wb').write)
    xml = []
    ftp.retrlines('RETR %s.xml' % (f_id), lambda x: xml.append(x))
    r_date = ''
    for line in xml:
        if '<recorded>' in line:
            r_date = line.replace('<recorded>', '').replace('</recorded>', '')

    # convert to ogg
    # data = commands.getstatusoutput( 'ffmpeg -y -i "%s" -c:a libvorbis -q:a 5 "%s"' % ( f_name, f_name.replace('.mp3','.ogg') ) )
    # commands.getstatusoutput('rm %s'%(f_name))
    # f_name = f_name.replace('.mp3','.ogg')

    cmd = 'ffprobe -i %s -show_entries format=duration -v quiet -of json' % (
        f_name)
    p = subprocess.Popen(
        cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    print(out)
    data = json.loads(out)
    length = data['format']['duration']
    print(length)
    sec = int(length.split('.')[0])
    hund = int(round(float(length.split('.')[1][0:2])/10))
    min = int(floor(int(sec)/60.))
    sec = int(sec - 60*min)
    length = float(length)

    # dont scale if within 1 second
    if abs(target_length - length) < 1:
        print("Not Scaling")
        scale = 1
    else:
        scale = length/target_length
        if scale > 1.05:
            scale = 1.05
        elif scale < .95:
            scale = .95
        print("Length = %d:%02d.%d" % (min, sec, hund))
        print("Scaling by %0.04f" % (scale))
        cmd = ['ffmpeg', '-i', f_name,
               '-filter:a', "atempo=%0.04f" % (scale),
               '-vn', '-v', 'quiet', '_'+f_name]
        p = subprocess.Popen(cmd)
        p.communicate()
        p = subprocess.Popen(['mv', '_'+f_name, f_name])
        p.communicate()

    length = str(scale*length)
    sec = int(length.split('.')[0])
    hund = int(round(float(length.split('.')[1][0:2])/10))
    min = int(floor(int(sec)/60.))
    sec = int(sec - 60*min)

    fd = taglib.File(f_name)
    fd.tags[u'DATE'] = datetime.now().strftime('%Y-%m-%d')
    fd.tags[u'YEAR'] = datetime.now().strftime('%Y')
    fd.tags[u'TITLE'] = "%02d%sM " % (
        hour, ampm.upper()) + fd.tags[u'TITLE'][0].split(' - ')[0].strip()
    fd.tags[u'ARTIST'] = u"Waatea"
    fd.tags[u'ORGANIZATION'] = u"*** NEWS ***"
    fd.tags[u'LABEL'] = u"*** NEWS *** Updated-%s" % (
        datetime.now().strftime('%H:%M-%d-%m-%Y'))
    fd.tags[u'PUBLISHER'] = u"*** NEWS ***"
    fd.tags[u'UFID'] = u"1840-WAATEA-NEWS-%02d%s-MP3" % (hour, ampm.upper())
    fd.tags[u'OWNER'] = u"admin"
    fd.tags[u'LENGTH'] = u"%d:%02d.%d" % (min, sec, hund)
    fd.tags[u'TLEN'] = u"%d:%02d.%d" % (min, sec, hund)
    retval = fd.save()
    print(retval)
    print(fd.tags)

    from mutagen.id3 import ID3, TPUB
    audio = ID3(f_name)
    audio.add(TPUB(encoding=3, text=u"*** NEWS ***"))
    audio.save()

    f_name_abs = os.path.join(file_path, f_name)
    os.rename(f_name, f_name_abs)

    cmd = 'sudo chown www-data {0}'.format(f_name_abs)
    p = subprocess.Popen(cmd.split(' '))
    p.communicate()

    cmd = 'sudo chgrp www-data {0}'.format(f_name_abs)
    p = subprocess.Popen(cmd.split(' '))
    p.communicate()

    td = (datetime.now() - start_time)
    print('elapsed time = %s' % (td.seconds))


def main():
    for folder in ROOT_FOLDERS:
        logging.info('Scanning {0}'.format(folder))
        scan_folder(folder)


if __name__ == "__main__":
    main()
