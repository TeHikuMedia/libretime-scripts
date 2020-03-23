import boto3
from botocore.exceptions import ClientError
import requests
import json
ACCESS_KEY = "AKIAJKSOLCGF6JTCJGRQ"
SECRET_KEY = "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"


class Emailer():
    SENDER = "Silence Detector <webapp@tehiku.nz>"
    RECIPIENT = "keoni@tehiku.co.nz"
    AWS_REGION = "us-west-2"
    SUBJECT = "Silence Detected"
    BODY_TEXT = ("Test")
    BODY_HTML = "<html><body>hi</body></html>"
    CHARSET = "UTF-8"

    def __init__(self):
        self.client = boto3.client(
            'ses',
            region_name=self.AWS_REGION,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY)
        self.html = self.BODY_HTML
        self.text = self.BODY_TEXT
        self.sender = self.SENDER
        self.subject = self.SUBJECT
        self.to = self.RECIPIENT

    def send(self):
        try:
            response = self.client.send_email(
                Destination={
                    'ToAddresses': [
                        self.to,
                    ],
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': self.CHARSET,
                            'Data': self.html,
                        },
                        'Text': {
                            'Charset': self.CHARSET,
                            'Data': self.text,
                        },
                    },
                    'Subject': {
                        'Charset': self.CHARSET,
                        'Data': self.subject,
                    },
                },
                Source=self.sender,
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            print("Email sent! Message ID: " + \
                   response['ResponseMetadata']['RequestId'])


class SlackPost():
    URL = 'https://hooks.slack.com/services/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'
    COMMAND = """curl -X POST -H 'Content-type: application/json' --data '{0}' {1}"""

    def __init__(self):
        self.url = self.URL
        self.data = {"text": "You didn't provide any data"}

    def send(self):
        response = requests.post(
            self.url,
            data=json.dumps(self.data),
            headers={"Content-type": "application/json;"})

        print("Slack post: "+response[content])
