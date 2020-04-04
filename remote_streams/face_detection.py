import boto3
from botocore.exceptions import ClientError
import time
import tempfile as tf
from remote_streams.settings import CONF_FILE
import json

# Load Configuration
try:
    f = open(CONF_FILE, 'rb')
    d = json.loads(f.read())
    f.close()
    
    AWS_KEY = d['aws']['access_key_face']
    AWS_ID = d['aws']['secret_key_face']
except KeyError as e:
    print('Incorrectly formatted configuration file {0}'.format(CONF_FILE))
    raise
except Exception as e:
    print('Could not read configuration file {0}.'.format(CONF_FILE))
    raise
       
BUCKET = "face-detections"

FEATURES_BLACKLIST = ("Landmarks", "Emotions", "Pose", "Quality", "BoundingBox", "Confidence")

def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def upload_image(image, bucket, key): 
    s3_client = boto3.client('s3')
    try:
        tmp_file = tf.NamedTemporaryFile(delete=True, suffix='.jpg')
        image.save(tmp_file)
        response = s3_client.upload_file(tmp_file.name, bucket, key)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def detect_faces(bucket, key, attributes=['ALL'], region="ap-southeast-2"):
    rekognition = boto3.client("rekognition", region)
    response = rekognition.detect_faces(
        Image={
            "S3Object": {
                "Bucket": bucket,
                "Name": key,
            }
        },
        Attributes=attributes,
    )
    return response['FaceDetails']

def detect_faces_binary(binary_image, attributes=['DEFAULT'], region='us-west-2'):
    rekognition = boto3.client(
        'rekognition',region_name=region,
        aws_access_key_id=AWS_ID,
        aws_secret_access_key=AWS_KEY)
    img_json = {u'Bytes': binary_image}
    response = rekognition.detect_faces(
        Image=img_json,
        Attributes=attributes
    )
    return response['FaceDetails']

def is_face(aws_face_details):

    if len(aws_face_details)==0:
        return False, 0

    max_face = max(aws_face_details, key=lambda face: face['Confidence'])
    return max_face['Confidence'] > 90, max_face['Confidence']

    # for face in aws_face_details:
    #   bounding_box = face['BoundingBox']
    #   print("{}-{} ({})".format(bounding_box['Width'], bounding_box['Height'], face['Confidence']))
    #   if bounding_box['Width'] > .02 and  bounding_box['Height'] > .02:

def face_in_file(file_like):
    s3_key = time.strftime("test_for_face_%Y%m%d-%H%M%S_%f.jpg")
    upload_file(file_like, BUCKET, s3_key)
    aws_face_details = detect_faces(BUCKET, s3_key)
    return is_face(aws_face_details)

def face_in_image(image):
    s3_key = time.strftime("test_for_face_%Y%m%d-%H%M%S_%f.jpg")
    upload_image(image, BUCKET, s3_key)
    aws_face_details = detect_faces(BUCKET, s3_key)
    return is_face(aws_face_details)

def face_in_binary_image(image):
    aws_face_details = detect_faces_binary(image)
    return is_face(aws_face_details)

def test():
    for file_name in ["jacinda.jpg", "no_face.jpg", "yes_face.jpg", "press_conference.jpg"]:
        file_path = "data/{}".format(file_name)
        yesnoface, confidence = face_in_file(file_path)
        print("{0} - {1} : {2:.2f} %".format(file_name, yesnoface, confidence))


if __name__ == "__main__":    
    test()

