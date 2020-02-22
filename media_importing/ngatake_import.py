import taglib
import urllib2
from datetime import datetime, timedelta
import time

import commands 
from math import floor
from os import fchown, path
import os
from pwd import getpwnam  
from grp import getgrnam
import json
from import_functions import time_string, convert_media, scale_media

from settings import BASE_MEDIA_DIR

def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset

start_time = datetime.now()

url = 'https://tehiku.nz/api/te-reo/nga-take/latest?mp3=True'
url2 = 'https://tehiku.nz/api/te-reo/nga-take/latest'
target_length = 60.0*3.0 + 45.0
response = urllib2.urlopen(url2)
# headers = response.info().headers
# for item in headers:
#     if 'content-disposition' in item.lower():
#         title = item.split('filename=')[1].lower().replace('mp3','').replace('nga_take','').replace('_',' ').replace('.','').upper().strip()
data = response.read()
j = json.loads(data)

utc = datetime.strptime(j['publish_date'], '%Y-%m-%dT%H:%M:%SZ')
print utc
dt = utc2local(utc)
print dt

title = dt.strftime('%d%m%y')
PM = dt.strftime('%p')

print title

f_name = 'Nga_Take_{0}.mp3'.format(PM)
f_path = path.join(BASE_MEDIA_DIR, 'tehiku_ngatake')
if not os.path.exists(f_path):
    os.mkdir(f_path)

from subprocess import Popen

cmd = [ 'curl', '-L', 'https://tehiku.nz/api/te-reo/nga-take/latest?mp3=True', '-o', f_name]
p = Popen(cmd)
p.communicate()

get_new_file = True

if get_new_file:
    print "Downloading new file..."
    # check if we need to update the file

    media_length = scale_media(f_name, target_length)

    fd = taglib.File(f_name)
    fd.tags['DATE'] = datetime.now().strftime('%Y-%m-%d')
    fd.tags['YEAR'] = datetime.now().strftime('%Y')
    fd.tags['TITLE'] =  u"Nga Take %s %s - Updated %s" % (PM, title, datetime.now().strftime('%H:%M-%d-%m-%Y') )
    fd.tags['ARTIST'] = u"Te Hiku Media"
    fd.tags['LABEL'] = u"*** NEWS *** Last-Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
    fd.tags['ORGANIZATION'] = u"*** NEWS *** Last-Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))

    fd.tags['UFID'] = u"1840-TEHIKUMEDIA-NGATAKE-MP3"
    fd.tags['OWNER'] = u"admin"
    fd.tags['GENRE'] = u"News & Current Affairs"
    fd.tags['LENGTH'] = "%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
    fd.tags['TLEN'] = "%d:%02d.%d"%(media_length['mins'], media_length['secs'], media_length['hunds'])
    retval = fd.save()
    print retval

    commands.getstatusoutput('sudo chown www-data %s'%(f_name))
    commands.getstatusoutput('sudo chgrp www-data %s'%(f_name))
    commands.getstatusoutput('mv %s %s/'%(f_name,f_path))

    td =  (datetime.now() - start_time)
    print 'elapsed time = %s' % ( td.seconds )

    # Try to force move file into airtime shit
    # try:
    #     dest_file = commands.getstatusoutput('sudo cat /var/log/airtime/pypo/pypo.log | grep copy.*%s.*/scheduler/'%(f_name))[1].split('\n')[0].split('/scheduler/')[1].split('.mp3')[0]+'.mp3'
    #     print "Copying %s to .../scheduler/%s" %(f_name, dest_file)

    #     success = commands.getstatusoutput('sudo cp -v %s/%s /var/tmp/airtime/pypo/cache/scheduler/%s'%(f_path,f_name,dest_file))
    #     commands.getstatusoutput('sudo chown www-data /var/tmp/airtime/pypo/cache/scheduler/%s'%(dest_file))
    #     commands.getstatusoutput('sudo chgrp www-data /var/tmp/airtime/pypo/cache/scheduler/%s'%(dest_file))
    #     commands.getstatusoutput('sudo chmod a+rw /var/tmp/airtime/pypo/cache/scheduler/%s'%(dest_file))
    #     for i in success: print i
    # except:
    #     print "Something went wrong while trying to fudge Airtime"

else:
    commands.getstatusoutput('rm %s'%(f_name) )

