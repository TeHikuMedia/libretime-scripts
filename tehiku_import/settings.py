from sys import platform

if platform == 'darwin':
    BASE_MEDIA_DIR = "/Users/livestream/Downloads/"
    MD5_CMD = "md5"
else:
    BASE_MEDIA_DIR = "/home/admin/tehiku_import"
    MD5_CMD = "md5sum"