# m    h  dom mon dow   user command
#15 5,17 * * * /home/ubuntu/sync_db_to_bucket.sh
#1 0 * * MON-SAT /home/ubuntu/sync_files_no_md5.sh
#1 0 * * SUN /home/ubuntu/sync_files_md5.sh
#
#
*/15,56-59 16-23,0-4 * * 1-5	root	/usr/local/bin/waatea-fetch > /var/log/airtime/cron.waatea.log
*/15 17-23,0-6 * * 1-5	root	/usr/local/bin/tehiku-fetch -c kuaka-marangaranga,te-reo-o-te-rangatira,taumatahanga -r 7 > /var/log/airtime/cron.interviews.log
*/10 19-23,0-4 * * 1-5	root	/usr/local/bin/tehiku-fetch -c panui -d -l Pānui > /var/log/airtime/cron.daily.log
*/10 19-23,0-4 * * 1-5	root	/usr/local/bin/tehiku-fetch -c nga-tohu -d -l 'Ngā Tohu'> /var/log/airtime/cron.daily.log
*/15,26-29 17-23,0-5 * * 1-5	root	/usr/local/bin/tehiku-fetch -c nga-take -a -l News > /var/log/airtime/cron.ampm.log
