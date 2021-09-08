from sys import platform

if platform == 'darwin':
    BASE_MEDIA_DIR = "/Users/livestream/Downloads/"
    MD5_CMD = "md5"
    CONF_FILE = "/etc/librescripts/conf.json"
else:
    BASE_MEDIA_DIR = "/home/admin/tehiku_import"
    MD5_CMD = "md5sum"
    CONF_FILE = "/etc/librescripts/conf.json"
