from sys import platform

if platform == 'darwin':
    CONF_FILE = "/tmp/conf.json"
else:
	CONF_FILE = "/etc/librescripts/conf.json"