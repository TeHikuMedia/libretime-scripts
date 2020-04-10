import requests
import json
from remote_streams.settings import CONF_FILE


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

def call_webhooks(queue, message, hooks=['Kingi', 'Slack Automation Channel']):

    for hook in WEBHOOKS:
        name = hook['name']

        if name not in hooks:
            continue

        url = hook['url']
        if 'slack' in hook['type']:
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
    call_webhooks(None,'test')
