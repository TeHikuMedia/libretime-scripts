import requests
from requests.auth import HTTPDigestAuth
import os
from datetime import datetime
import time

'''
curl -X GET -H 'Accept:application/json; charset=utf-8' -H 'Content-Type:application/json; charset=utf-8' --digest -u "API:Ku4ka1840" "https://rtmp.tehiku.live:8087/v2/servers/_defaultServer_/vhosts/_defaultVHost_/applications/rtmp/adv"
'''


BASEURL = "https://rtmp.tehiku.live:8087/v2/servers/_defaultServer_/vhosts/_defaultVHost_/"
RESOURCE = "applications/rtmp/adv"

HEADERS ={
	'Accept': 'application/json; charset=utf-8' ,
	'Content-Type': 'application/json; charset=utf-8'
}

# r = requests.get(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS)

# settings = r.json()


# print(settings['modules'])




# RESOURCE = "applications/rtmp/actions/restart"

# # Restart application
# r = requests.put(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS)
# print(r.json())


# Get list of stream targets
RESOURCE = "applications/rtmp/pushpublish/mapentries"
r = requests.get(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS)
data = r.json()

START_TIME = datetime.strptime('2020/03/31 13:30:00', '%Y/%m/%d %H:%M:%S')
NOW = datetime.now()
ENABLED = False


entries = ['Push to tehiku.radio', 'Sunshine Radio']

while not ENABLED:
	NOW = datetime.now()
	print(NOW)
	try:
		for target in entries:
			print(target)
			for entry in data['mapEntries']:
				if target in entry['entryName']:
					st = entry
					print(st['enabled'])
					if START_TIME < NOW:
						# Stream shoudl be disabled
						if st['enabled']:
							st['enabled'] = False
							RESOURCE = "applications/rtmp/pushpublish/mapentries/" + entry['entryName']
							r = requests.put(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS, data=st)
							res = r.json()
							print("Result:", res)
					elif START_TIME >= NOW:
						print("Starting")
						if not st['enabled']:
							st['enabled'] = True
							RESOURCE = "applications/rtmp/pushpublish/mapentries/" + entry['entryName']
							r = requests.put(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS, data=st)
							res = r.json()
							print("Result:", res)


					# RESOURCE = "applications/rtmp/pushpublish/mapentries/" + entry['entryName']
					# r = requests.put(os.path.join(BASEURL, RESOURCE), auth=HTTPDigestAuth('API', 'Ku4ka1840'), headers=HEADERS)
					# data = r.json()

					# print(data)

	except Exception as e:
		print(e)
		# print(data)

	time.sleep(10)