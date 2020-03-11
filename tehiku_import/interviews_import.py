#!/usr/bin/env python
# -*- coding: utf-8 -*-

import taglib
import mutagen
import urllib2
from datetime import datetime
import commands 
from math import floor
import time
import json
from subprocess import Popen, PIPE
import unicodedata

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii

def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp (epoch)
    return utc + offset


collections = ['te-reo-o-te-rangatira', 'kuaka-marangaranga', 'taumatahanga']

for collection in collections:
    url = 'https://tehiku.nz/api/te-hiku-radio/{0}/latest?mp3=True'.format(collection)
    url2 = 'https://tehiku.nz/api/te-hiku-radio/{0}/latest'.format(collection)
    response = urllib2.urlopen(url2)
    data = response.read()
    j = json.loads(data)
    print j

    utc = datetime.strptime(j['publish_date'], '%Y-%m-%dT%H:%M:%SZ')
    print utc
    dt = utc2local(utc)
    print dt

    title = u"{0}".format(j['headline'])
    title = remove_accents(title)
    print title

    f_name = u"{0}_{1}.mp3".format(collection.replace('-','_'), title.replace(' ', '_'))
    f_name = remove_accents(f_name)
    print f_name

    cmd = [ 'curl', '-L', url, '-o', f_name]
    p = Popen(cmd)
    p.communicate()

    # convert to ogg
    #data = commands.getstatusoutput( 'ffmpeg -y -i "%s" -c:a libvorbis -q:a 5 "%s"' % ( f_name, f_name.replace('.mp3','.ogg') ) )
    #commands.getstatusoutput('rm %s'%(f_name))
    #f_name = f_name.replace('.mp3','.ogg')

    fd = taglib.File(f_name)

    length = commands.getstatusoutput(u'ffprobe -i {0} -show_entries format=duration -v quiet -of csv="p=0"'.format(f_name))[1]
    print length
    sec = int(length.split('.')[0])
    hund = int(round(float(length.split('.')[1][0:2])/10))
    mins = int(floor(int(sec)/60.))
    sec = int(sec - 60*mins+1)
    #print "%d:%02d.%d"%(min, sec, hund)

    fd.tags['Length'] = u"%d:%02d.%d"%(mins, sec, hund)
    fd.tags['TLEN'] = u"%d:%02d.%d"%(mins, sec, hund)

    fd.tags['Date'] = dt.strftime('%Y-%m-%d')
    fd.tags['Year'] = dt.strftime('%Y')
    fd.tags['TITLE'] = u"{0}".format(title.title())
    fd.tags['ALBUM'] = u"{0}".format(collection.replace('-', ' ').title())
    fd.tags['LABEL'] = "label"
    fd.tags['ORGANIZATION'] = "test"
    fd.tags['GENRE'] = u"Interview"
    fd.tags['Artist'] = u"Te Hiku Media"
    # fd.tags['LABEL'] = u"Panui-Auto-Imported, Last-Updated-%s" % (datetime.now().strftime('%H:%M-%d-%m-%Y'))
    # fd.tags['UFID'] = u"1840-TEHIKUMEDIA-PANUI-OGG"
    fd.tags['OWNER'] = u"admin"
    retval = fd.save()
    print retval

    from mutagen.easyid3 import EasyID3
    audio = EasyID3(f_name)
    # audio['label'] = u"{0}".format(collection.replace('-', ' ').title())
    audio['organization'] = u"{0}".format(collection.replace('-', ' ').title())
    audio['title'] = u"{0}".format(title.title())
    # audio['label'] = u'test'
    audio.save()

    audio_file = mutagen.File(f_name, easy=True)
    try:
        print audio_file['organization']
    except:
        pass
    print audio_file.keys()
    print audio_file['title']

    commands.getstatusoutput('mv %s /srv/airtime/watch_folder/tehiku_interviews/'%(f_name))
    commands.getstatusoutput('sudo chown www-data /srv/airtime/watch_folder/tehiku_interviews/%s'%(f_name))
    commands.getstatusoutput('sudo chgrp www-data /srv/airtime/watch_folder/tehiku_interviews/%s'%(f_name))
