from face_detection import face_in_binary_image
import os
from subprocess import Popen, PIPE
from datetime import datetime
import glob

import cv2


def detect_face_opencv(file):
    face_cascade = cv2.CascadeClassifier('/Users/livestream/Desktop/haarcascade_frontalface_default.xml')
    img = cv2.imread(file)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 2, 3)
    if len(faces)>0:
        return True, len(faces)
    else:
        return False, len(faces)

# def face_open_cv():
    # face_cascade = cv2.CascadeClassifier('/Users/livestream/Desktop/haarcascade_frontalface_default.xml')

    # for file in sorted(glob.glob('data/frame*.jpg')):
    #     img = cv2.imread(file)
    #     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    #     faces = face_cascade.detectMultiScale(gray, 1.1, 5)
    #     print(faces, file)

def get_face():
    src = "/Users/livestream/Desktop/teaonews_20200406_1600.mp4"

    width = 1920
    height = width * 9/16
    fps=2
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'info', '-i', src, 
        '-vf', f"fps={fps:0.0f},scale={width:0.0f}:{height:0.0f}",  '-f', 'image2', 'data/frame_%04d.jpg'
    ]
    print(' '.join(cmd))
    process = Popen(cmd, stderr=PIPE, stdout=PIPE)
    o,e = process.communicate()
    
    face_count = 0
    count = 0
    frame_count = 0
    batch_frames = 1
    if fps >= 1:
        batch_frames = fps

    try:

        for file in sorted(glob.glob('data/frame*.jpg')):
            count = count+1
            
            if count%batch_frames == 1 or batch_frames == 1:
                time = datetime.now()                
                result = detect_face_opencv(file)
                
                if result[0]:
                    frame_count = frame_count + 1

            if count%batch_frames == 0:
                if frame_count >= 1:
                    result = True, 100
                else:
                    result = False, 0
                frame_count = 0
                print(f'Found Face with {result[1]:6.2f}% confidence in {datetime.now()-time}s for {file}')

            # with open(file, 'rb') as f:
            #     time = datetime.now()
            #     data = f.read()
            #     result = face_in_binary_image(data)
            #     print(f'Found Face with {result[1]:6.2f}% confidence in {datetime.now()-time}s for {file}')
                # if result[0]:
                #     face_count = face_count + 1
            # if face_count > 2:
            #     return
            # print()
            
    except Exception as e:
        print(e)
        return


if __name__ == '__main__':
    get_face()
    # face_open_cv()