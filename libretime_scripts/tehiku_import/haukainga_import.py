import taglib
import urllib2
import json
from datetime import datetime, timedelta
import commands 
from math import floor
from os import fchown, path
from pwd import getpwnam  
from grp import getgrnam
import re
from import_functions import *


start_time = datetime.now()

url = 'https://tehiku.nz/api/te-hiku-tv/haukainga/latest'
# target_length = 60*4.0
response = urllib2.urlopen(url)
data = json.loads(response.read())

DATE = data['publish_date']
TITLE = data['collection']['name'].upper() + u' ' + data['headline']
ALBUM = data['collection']
CREATOR = u'Te Hiku Media'
ARTIST = u'Te Hiku Media'
GENRE = [u'Documentary']
YEAR = data['publish_date'][0:4]
LABEL = [data['collection'], u'Auto-Import']
IS_AUDIO=False
media = data['media']

for item in media:
    # item = media[pk]
    file_url = item['media_file']
    
    if is_audio(media_type(file_url)):
        IS_AUDIO=True
        break

    for pk_v in item['versions']:

        version = item['versions'][pk_v]

        file_url = version['media_file']

        if is_audio(media_type(file_url)):
            
            IS_AUDIO=True
            break

# check if file exists. if so, don't fetch it!
f_path = '/srv/airtime/watch_folder/haukainga/'
f_name = TITLE.lower().replace(' ','_').strip()
f_name = re.sub(r'\W+', '', f_name)+'.'+media_type(file_url)

ffex = f_path + f_name.split('.')[0] + "_CONVERTED.m4a"
result = path.isfile(ffex)
if not result:

    if IS_AUDIO:
        response = urllib2.urlopen(file_url)
        data = response.read()
        f = open(f_path+f_name, 'w')
        f.write(data)
        f.close()

    # convert file

    new_f_name = convert_audio(f_path+f_name)
    import commands
    commands.getstatusoutput('rm '+f_path+f_name)
    f_name = new_f_name



    fd = taglib.File(f_name)
    fd.tags['DATE'] = DATE
    fd.tags['YEAR'] = YEAR
    fd.tags['TITLE'] =  TITLE
    fd.tags['ARTIST'] = ARTIST
    fd.tags['GENRE'] = GENRE
    fd.tags['ALBUM'] = ALBUM
    fd.tags['CREATOR'] = CREATOR
    fd.tags['LABEL'] = LABEL
    fd.tags['COMMENT'] = LABEL
    # fd.tags['UFID'] = u"1840-TEHIKUMEDIA-NGATAKE-MP3"
    # fd.tags['OWNER'] = u"admin"
    # fd.tags['LENGTH'] = "%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
    # fd.tags['TLEN'] = "%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
    retval = fd.save()

    commands.getstatusoutput('sudo chown www-data %s'%(f_name))
    commands.getstatusoutput('sudo chgrp www-data %s'%(f_name))
    #commands.getstatusoutput('mv %s %s/'%(f_name,f_path))
    print u"Downloaded {0}".format(TITLE)

else: 
    print "File Exists."
