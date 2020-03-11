FILENAME="$(date +%a)"
sudo -u postgres pg_dumpall | gzip -c > libretime-backup-$FILENAME.gz
s3cmd sync libretime-backup-$FILENAME.gz s3://tehiku-airtime-bucket/tehiku_fm/tehiku_db_backup_$FILENAME.gz
