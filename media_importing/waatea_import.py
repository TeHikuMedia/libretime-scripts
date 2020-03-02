import taglib

from datetime import datetime, timedelta
import commands 
from math import floor
from ftplib import FTP
from os import fchown, path
from pwd import getpwnam  
from grp import getgrnam
from shutil import copyfile
from import_functions import time_string, convert_media, scale_media
from settings import BASE_MEDIA_DIR

import os

if not os.path.exists(BASE_MEDIA_DIR):
    os.mkdir(BASE_MEDIA_DIR)


start_time = datetime.now()

ftp = FTP('ftp.irirangi.net') 
ftp.login('NGWAN_Upload','ngwanupload')
ftp.cwd('MP3_News')
items=[]
ftp.retrlines('RETR file_ids.txt', lambda x: items.append(x) ).split('\n')

time = datetime.now() + timedelta(hours=1)

hour = int( time.strftime('%I') ) # always want to get an hour ahead!
ampm = time.strftime('%p').split('M')[0].lower()

f_id = ''
for item in items:
    if 'news sport %s%s'%(hour,ampm) in item:
        f_id = item.split(' ')[0].strip()
if f_id == '':
    print("No News for this Hour")
    raise NameError('news sport %s%s'%(hour,ampm))

f_name = 'Waatea_News_%s%s.mp3'%(hour,ampm)
f_path = os.path.join(BASE_MEDIA_DIR, 'waatea_news')
if not os.path.exists(f_path):
    os.mkdir(f_path)

tmp_path = os.path.join(BASE_MEDIA_DIR, 'tmp')
if not os.path.exists(tmp_path):
    os.mkdir(tmp_path)

target_length = 60*6.0
print("Fetching %s"%(f_name))

# Remove the file?
# commands.getstatusoutput('rm %s/%s'%(f_path, f_name))

ftp.retrbinary('RETR %s.MP3'%(f_id), open(f_name, 'wb').write)
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
if path.isfile('%s/%s'%(f_path, f_name)):
    # Copy file then probe as FTAG seems to cause a file change event that airtime media monitor reads
    copyfile(path.join(f_path, f_name), path.join(tmp_path, 'tmp.mp3'))
    fd = taglib.File(path.join(tmp_path, 'tmp.mp3'))
    try:
        file_record_date = datetime.strptime(fd.tags[u'DATE'][0], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        file_record_date = datetime.strptime(fd.tags[u'DATE'][0], '%Y-%m-%d')
        
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

    media_length = scale_media(f_name, target_length)

    fd = taglib.File(f_name)
    a = fd.tags[u'TITLE'][0].split(' - ')[0].strip()
    fd.tags[u'DATE'] = record_date.strftime('%Y-%m-%d %H:%M:%S')
    fd.tags[u'YEAR'] = datetime.now().strftime('%Y')
    fd.tags[u'TITLE'] = "%02d%sM "%(hour,ampm.upper()) + fd.tags[u'TITLE'][0].split(' - ')[0].strip()
    fd.tags[u'ARTIST'] = u"Waatea"
    fd.tags[u'LABEL'] = u"News-Auto-Imported, Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
    fd.tags[u'UFID'] = u"1840-WAATEA-NEWS-%02d%s-MP3"%(hour, ampm.upper())
    fd.tags[u'OWNER'] = u"admin"
    fd.tags[u'ORGANIZATION'] = u"*** NEWS *** Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
    fd.tags[u'LABEL'] = u"*** NEWS *** Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
    fd.tags[u'LENGTH'] = u"%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
    fd.tags[u'TLEN'] = u"%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
    retval = fd.save()
    print(retval)
    print(fd.tags)

    commands.getstatusoutput('sudo chown www-data %s'%(f_name))
    commands.getstatusoutput('sudo chgrp www-data %s'%(f_name))
    os.rename(f_name, os.path.join(f_path, f_name))

    td =  (datetime.now() - start_time)
    print('elapsed time = %s' % ( td.seconds ))

    # Try to force move file into airtime shit
    # try:
    #     dest_file = commands.getstatusoutput('sudo cat /var/log/airtime/pypo/pypo.log | grep copy.*%s.*/scheduler/'%(f_name))[1].split('\n')[0].split('/scheduler/')[1].split('.mp3')[0]+'.mp3'
    #     print("Copying %s to .../scheduler/%s" %(f_name, dest_file))

    #     success = commands.getstatusoutput('sudo cp -v %s/%s /var/tmp/airtime/pypo/cache/scheduler/%s'%(f_path,f_name,dest_file))
    #     commands.getstatusoutput('sudo chown www-data /var/tmp/airtime/pypo/cache/scheduler/%s'%(dest_file))
    #     commands.getstatusoutput('sudo chgrp www-data /var/tmp/airtime/pypo/cache/scheduler/%s'%(dest_file))
    #     commands.getstatusoutput('sudo chmod a+rw /var/tmp/airtime/pypo/cache/scheduler/%s'%(dest_file))
    #     for i in success: print(i)
    # except:
    #     print("Something went wrong while trying to fudge Airtime")

else:
    commands.getstatusoutput('rm %s'%(f_name) )

