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


#parser.add_argument("--collection", help="Collection slug name, separated by comma.")
#parser.add_argument("--am-pm", help="Whether to write file with AM/PM")
#parser.add_argument("--remove-after-days", help="Remove file if it's older than X days.")

timezone = pytz.timezone("Pacific/Auckland")
parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", help="Download Waatea news items for each hour.", action="store_true")
args = parser.parse_args()

def get_waatea_all():
    for hour_increment in range(7,19):
        time = datetime.strptime('2015-12-09 %02d:00'%(hour_increment),'%Y-%m-%d %H:%M')
        time = time.astimezone(timezone)
        get_waatea(time)


def get_waatea_now():
    time = datetime.now() + timedelta(hours=1)
    time = time.astimezone(timezone)
    print("Getting news for {0}".format(time.strftime('%H:%M')))
    get_waatea(time)


def get_waatea(time):
    hour = int( time.strftime('%I') ) # always want to get an hour ahead!
    ampm = time.strftime('%p').split('M')[0].lower()

    if not os.path.exists(BASE_MEDIA_DIR):
        os.mkdir(BASE_MEDIA_DIR)

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
    f_path = os.path.join(BASE_MEDIA_DIR, 'waatea_news')
    if not os.path.exists(f_path):
        os.mkdir(f_path)

    tmp_path = os.path.join(BASE_MEDIA_DIR, 'tmp')
    if not os.path.exists(tmp_path):
        os.mkdir(tmp_path)

    tmp_file = os.path.join(tmp_path, f_name)
    final_file = os.path.join(f_path, f_name)

    target_length = 60*6.0
    print("Fetching %s"%(f_name))

    # Remove the file?
    # commands.getstatusoutput('rm %s/%s'%(f_path, f_name))

    ftp.retrbinary('RETR %s.MP3'%(f_id), open(tmp_file, 'wb').write)
    xml=[]
    ftp.retrlines( 'RETR %s.xml'%(f_id), lambda x: xml.append(x) )
    r_date = ''
    for line in xml:
        if '<recorded>' in line:
            r_date = line.replace('<recorded>','').replace('</recorded>','').strip()

    record_date = datetime.strptime(r_date,'%m/%d/%Y %H:%M:%S')
    print("Recorded", record_date)

    get_new_file = False
    # get current file '/srv/airtime/watch_folder/waatea_news/%s' % (f_name)
    if path.isfile(final_file):
        fd = taglib.File(final_file)
        print(fd.tags)
        try:
            file_record_date = datetime.strptime(fd.tags[u'DATE'][0], '%Y-%m-%d %H:%M:%S')
        except (ValueError, KeyError) as e:
            file_record_date = os.path.getmtime(final_file)
                        
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
        # check if we need to update the file

        try:
            media_length = scale_media(tmp_file, target_length)
        except Exception as e:
            print("Error scaling media.")
            print(e)
            return

        fd = taglib.File(tmp_file)
        a = fd.tags[u'TITLE'][0].split(' - ')[0].strip()
        fd.tags[u'DATE'] = record_date.strftime('%Y-%m-%d %H:%M:%S')
        fd.tags[u'TIME'] = record_date.strftime('%Y-%m-%d %H:%M:%S')
        fd.tags[u'YEAR'] = datetime.now().strftime('%Y')
        fd.tags[u'TITLE'] = "%02d%sM "%(hour,ampm.upper()) + 'Waatea News' #fd.tags[u'TITLE'][0].split(' - ')[0].strip()
        fd.tags[u'ARTIST'] = u"Waatea"
        fd.tags[u'LABEL'] = u"News-Auto-Imported, Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
        fd.tags[u'UFID'] = u"1840-WAATEA-NEWS-%02d%s-MP3"%(hour, ampm.upper())
        fd.tags[u'OWNER'] = u"Te Hiku Media"
        fd.tags[u'ORGANIZATION'] = u"News"
        fd.tags[u'LABEL'] = u"News"
        fd.tags[u'LENGTH'] = u"%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
        fd.tags[u'TLEN'] = u"%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
        retval = fd.save()
        print(retval)
        print(fd.tags)

        p = Popen(['chown', 'www-data', tmp_file], stdin=PIPE, stdout=PIPE)
        p.communicate()
        p = Popen(['chgrp', 'www-data', tmp_file], stdin=PIPE, stdout=PIPE)
        p.communicate()

        p = Popen(['mv', tmp_file, final_file], stdin=PIPE, stdout=PIPE)
        p.communicate()

        td =  (datetime.now() - start_time)
        print('elapsed time = %s' % ( td.seconds ))


    else:
        p = Popen(['rm', tmp_file])


def main():
    if args.all:
        get_waatea_all()
    else:
        get_waatea_now()
    sys.exit(0)


if __name__ == "__main__":

    
    main()
