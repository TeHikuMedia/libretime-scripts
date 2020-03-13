# from __future__ import absolute_import

import taglib
import argparse

from datetime import datetime, timedelta
import pytz
from subprocess import Popen, PIPE
from math import floor
from ftplib import FTP
from os import fchown, path
from pwd import getpwnam  
from grp import getgrnam
from shutil import copyfile


import sys
import os

from tehiku_import.settings import BASE_MEDIA_DIR
from tehiku_import.import_functions import time_string, convert_media, scale_media
from tehiku_import.add_artwork import add_artwork

timezone = pytz.timezone("Pacific/Auckland")
parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", help="Download Waatea news items for each hour.", action="store_true")
parser.add_argument("-t", "--hour", help="Hour to download")
parser.add_argument("-x", "--delete", help="Delete all the downloaded files befor continuing.", action="store_true")
args = parser.parse_args()


def prepare_folders(path=None):
    if not os.path.exists(BASE_MEDIA_DIR):
        os.mkdir(BASE_MEDIA_DIR)
        p = Popen(['chown', 'www-data', BASE_MEDIA_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['chgrp', 'www-data', BASE_MEDIA_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()

    BASE_DIR = os.path.join(BASE_MEDIA_DIR, 'waatea_news')        
    if not os.path.exists(BASE_DIR):
        os.mkdir(BASE_DIR)
        p = Popen(['chown', 'www-data', BASE_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['chgrp', 'www-data', BASE_DIR], stdin=PIPE, stdout=PIPE)
        p.communicate()

    if path:
        if not os.path.exists(path):
            os.mkdir(path)
            p = Popen(['chown', 'www-data', path], stdin=PIPE, stdout=PIPE)
            p.communicate()
            p = Popen(['chgrp', 'www-data', path], stdin=PIPE, stdout=PIPE)
            p.communicate()

    return BASE_DIR


def delete_waatea():
    base = prepare_folders()
    for root, folder, files in os.walk(base):
        for file in files:
            fp = os.path.join(root, file)
            print("Removing {0}".format(fp))
            p = Popen(['rm', fp], stdin=PIPE, stdout=PIPE)
            p.communicate()


def get_waatea_all():
    for hour_increment in range(6,19):
        time = datetime.strptime('2015-12-09 %02d:00'%(hour_increment),'%Y-%m-%d %H:%M')
        time = timezone.localize(time)
        time = time.astimezone(timezone)
        get_waatea(time)


def get_waatea_now():
    time = datetime.now() + timedelta(hours=1)
    time = time.astimezone(timezone)
    print("Getting news for {0}".format(time.strftime('%H:%M')))
    get_waatea(time)


def get_waatea_hour(hour):
    time = datetime.strptime('2015-12-09 %02d:00'%(hour),'%Y-%m-%d %H:%M')
    time = timezone.localize(time)
    time = time.astimezone(timezone)
    get_waatea(time)


def get_waatea(time):
    hour = int( time.strftime('%I') ) # always want to get an hour ahead!
    ampm = time.strftime('%p').split('M')[0].lower()

    start_time = datetime.now()

    ftp = FTP('ftp.irirangi.net') 
    ftp.login('NGWAN_Upload','ngwanupload')
    ftp.cwd('MP3_News')
    items=[]
    ftp.retrlines('RETR file_ids.txt', lambda x: items.append(x) ).split('\n')

    f_id = ''
    for item in items:
        if 'news sport %s%s'%(hour,ampm) in item:
            f_id = item.split(' ')[0].strip()
    if f_id == '':
        print("No News for this Hour")
        return

    f_name = 'Waatea_News_%s%s.mp3'%(hour,ampm)

    f_path = prepare_folders()
    tmp_path = os.path.join(BASE_MEDIA_DIR, 'tmp')    
    prepare_folders(tmp_path)


    tmp_file = os.path.join(tmp_path, f_name)
    final_file = os.path.join(f_path, f_name)

    target_length = 60*6.0
    print("Fetching %s"%(f_name))

    xml=[]
    ftp.retrlines( 'RETR %s.xml'%(f_id), lambda x: xml.append(x) )
    r_date = ''
    for line in xml:
        if '<recorded>' in line:
            r_date = line.replace('<recorded>','').replace('</recorded>','').strip()

    record_date = timezone.localize(datetime.strptime(r_date,'%m/%d/%Y %H:%M:%S'))
    print("Recorded", record_date)

    get_new_file = False
    # get current file '/srv/airtime/watch_folder/waatea_news/%s' % (f_name)
    if path.isfile(final_file):
        fd = taglib.File(final_file)
        print(fd.tags)
        try:
            file_record_date = datetime.strptime(fd.tags[u'DATE'][0], '%Y-%m-%d %H:%M:%S')
        except (ValueError, KeyError) as e:
            mdate = datetime.fromtimestamp(os.path.getmtime(final_file))
            file_record_date = mdate.astimezone(timezone)
                        
        print("Old recorded", file_record_date)
        if int(record_date.strftime('%Y%m%d%H%M%S')) > int(file_record_date.strftime('%Y%m%d%H%M%S')):
            print("File needs updating...")
            get_new_file = True
        else:
            if hour==7 and ampm=='a':
                if int(record_date.strftime('%Y%m%d')) < int(time.strftime('%Y%m%d')):
                    print("File needs updating...")
                get_new_file = True
            else:
                print("File up to date.")
                get_new_file = False
    else:
        print("File doesn't exist...")
        get_new_file = True

    if get_new_file:
        print("Downloading new file...")
        ftp.retrbinary('RETR %s.MP3'%(f_id), open(tmp_file, 'wb').write)

        try:
            media_length = scale_media(tmp_file, target_length)
        except Exception as e:
            print("Error scaling media.")
            print(e)
            return

        p = Popen(['chown', 'www-data', tmp_file], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['chgrp', 'www-data', tmp_file], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['mv', tmp_file, final_file], stdin=PIPE, stdout=PIPE)
        p.communicate()

        print(final_file)
        print(tmp_file)
        fd = taglib.File(final_file)
        fd.tags[u'DATE'] = record_date.strftime('%Y')
        # fd.tags[u'TIME'] = record_date.strftime('%Y-%m-%d %H:%M:%S')
        # fd.tags[u'YEAR'] = datetime.now().strftime('%Y')
        fd.tags[u'TITLE'] = "%02d%sM "%(hour,ampm.upper()) + 'Waatea News - {0}'.format(record_date.strftime('%a').upper())
        fd.tags[u'ARTIST'] = u"Waatea"
        fd.tags[u'LANGUAGE'] = u"Māori"
        fd.tags[u'OWNER'] = u"Te Hiku Media"
        fd.tags[u'ORGANIZATION'] = u"News"
        # fd.tags[u'TLEN'] = u"%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
        fd.save()
        print(fd.tags)

        td =  (datetime.now() - start_time)
        print('elapsed time = %s' % ( td.seconds ))


        # Try to add album art.
        image_url = 'https://www.waateanews.com/site/uma/images/COLOR-Waatea%20logo%202016-final.jpg'
        add_artwork(image_url, final_file)

    else:
        p = Popen(['rm', tmp_file], stdin=PIPE, stdout=PIPE)
        p.communicate()


def main():
    if args.delete:
        delete_waatea()

    if args.all:
        get_waatea_all()
    if args.hour:
        get_waatea_hour(int(args.hour))
    else:
        get_waatea_now()

    sys.exit(0)


if __name__ == "__main__":

    
    main()
