import requests
import json
from remote_streams.settings import CONF_FILE
from datetime import datetime
import pytz

timezone = pytz.timezone("Pacific/Auckland")


# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    USER = d['wowza']['user']
    PASSWORD = d['wowza']['password']
    AWS_KEY = d['aws']['access_key_face']
    AWS_ID = d['aws']['secret_key_face']
    WEBHOOKS = d['webhooks']
except KeyError as e:
    print('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    print('Could not read configuration file {0}.'.format(CONF_FILE))
    raise


HEADERS ={
    'Content-Type': 'application/json; charset=utf-8'
}

def call_webhooks(queue, message, hooks=['Slack Automation Channel', 'Kingi' ]):

    for hook in WEBHOOKS:
        name = hook['name']

        NOW = datetime.utcnow().replace(tzinfo=pytz.utc)
        NOW_NZ = NOW.astimezone(timezone)


        slack_time_string = "<!date^%s^[{date_num} {time_secs}]|[%s NZT]>" % (NOW.strftime('%s'), NOW_NZ.strftime('%Y-%m-%d %H:%M:%S'))

        if name not in hooks:
            continue

        url = hook['url']
        if 'slack' in hook['type']:
            if 'live' in message.lower():
                message = f"```{slack_time_string} {message}\nWATCH:  https://tehiku.nz/c.B3\nLISTEN: http://tehiku.radio```"
            else:
                message = f"```{slack_time_string} {message}```"
            payload = {
                "text": message
            }
        else:
            payload = {
                "text": message,
                "listen": "https://tehiku.nz/te-hiku-radio/",
                "watch": "https://tehiku.nz/c.B3",
            }

        r = requests.post(url, headers=HEADERS, data=json.dumps(payload))

        print(r.content)

if __name__ == "__main__":
    call_webhooks(None,'Test ')
