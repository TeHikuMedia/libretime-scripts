import taglib
import urllib2
from datetime import datetime
import commands 
from math import floor
import time
import json
from subprocess import Popen

def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset


url = 'https://tehiku.nz/api/te-reo/nga-tohu/latest?mp3=True'
url2 = 'https://tehiku.nz/api/te-reo/nga-tohu/latest'
response = urllib2.urlopen(url2)
data = response.read()
j = json.loads(data)
print j

utc = datetime.strptime(j['publish_date'], '%Y-%m-%dT%H:%M:%SZ')
print utc
dt = utc2local(utc)
print dt

title = u"Nga Tohu %s" % (dt.strftime('%d%m%y'))

f_name = 'Nga_Tohu.mp3'

cmd = [ 'curl', '-L', url, '-o', f_name]
p = Popen(cmd)
p.communicate()

# convert to ogg
#data = commands.getstatusoutput( 'ffmpeg -y -i "%s" -c:a libvorbis -q:a 5 "%s"' % ( f_name, f_name.replace('.mp3','.ogg') ) )
#commands.getstatusoutput('rm %s'%(f_name))
#f_name = f_name.replace('.mp3','.ogg')

fd = taglib.File(f_name)

len = commands.getstatusoutput('ffprobe -i %s -show_entries format=duration -v quiet -of csv="p=0"'%(f_name))[1]
sec = int(len.split('.')[0])
hund = int(round(float(len.split('.')[1][0:2])/10))
min = int(floor(int(sec)/60.))
sec = int(sec - 60*min+1)
#print "%d:%02d.%d"%(min, sec, hund)

fd.tags['Length'] = u"%d:%02d.%d"%(min, sec, hund)
fd.tags['TLEN'] = u"%d:%02d.%d"%(min, sec, hund)

fd.tags['Date'] = datetime.now().strftime('%Y-%m-%d')
fd.tags['Year'] = datetime.now().strftime('%Y')
fd.tags['Title'] =  u"%s - Updated %s" % (title, datetime.now().strftime('%H:%M-%d-%m-%Y'))
fd.tags['Artist'] = u"Te Hiku Media "
# fd.tags['LABEL'] = u"Panui-Auto-Imported, Last-Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
# fd.tags['UFID'] = u"1840-TEHIKUMEDIA-NGATOHU-MP3"
fd.tags['OWNER'] = u"admin"
retval = fd.save()
print retval

commands.getstatusoutput('mv %s /srv/airtime/watch_folder/tehiku_ngatohu/'%(f_name))
commands.getstatusoutput('sudo chown www-data /srv/airtime/watch_folder/tehiku_ngatohu/%s'%(f_name))
commands.getstatusoutput('sudo chgrp www-data /srv/airtime/watch_folder/tehiku_ngatohu/%s'%(f_name))
