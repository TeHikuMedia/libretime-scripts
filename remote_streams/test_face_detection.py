import io
import logging
import image2pipe
from PIL import Image
from multiprocessing import Queue
from face_detection import face_in_image
from pathlib import Path
from timeit import default_timer as timer

  

logging.basicConfig()

def yield_from_queue(q, timeout_sec=0.42):
    while True:
        try:
            x = q.get(True, timeout_sec)
            if x is None:
                break
            yield x
        except queues.Empty:
            pass

def test():


    Path("tmp").mkdir(exist_ok=True)

    q = Queue(maxsize=4)

    # equivalent to
    # ffmpeg -v error -ss 00:00:00 -i data/COVID-19.mp4 -an -sn -f image2pipe -vcodec rawvideo -pix_fmt rgb24 -vf fps=2,scale=640x360     
    decoder = image2pipe.images_from_url(q, "data/COVID-19.mp4", fps="2", scale=(640, 360), pix_fmt='rgb24')
    # if this is the press conference we might be scaling a (1280, 720) -> to (640, 360) here
    decoder.start()

    
    face_confidence = 0
    for pair in yield_from_queue(q):
        i, img = pair
        timer_start = timer()
        image = Image.fromarray(img)
        is_face, confidence = face_in_image(image)
        timer_total = timer() - timer_start
        print("Checking for faces took {0:.3f}s.".format(timer_total))
        if is_face:
            image.save("tmp/face_test_{}.jpg".format(i))
            face_confidence += 1
            if face_confidence>10:
                break
        else:
            face_confidence = 0
        print("{} {}:{}".format(i,is_face,confidence))

    # FFMPEG_STREAM = \
    #     #'ffmpeg -y -re -loglevel warning -i pipe:0 -c:v copy -c:a copy -f flv rtmp://rtmp.tehiku.live:1935/rtmp/youtube_ingest'
    #   'ffmpeg -y -re -loglevel warning -i covid.mp4 -vf -vsync 0 /tmp/out%d.png'
     
    # print(FFMPEG_STREAM)
    # p2 = Popen(
    #     FFMPEG_STREAM.split(' '),
    #     stdin=PIPE,
    #     stderr=PIPE,
    #     stdout=PIPE)
    
    # while True:
    #     output = p1.stdout.readline()
    #     p2.stdin.write(output)
    #     # print(output)
    #     # print(p2.stdout.readline())
    #     # print(p2.stderr.readline())
    #     # print(p2.stdout.readline())
    #     # print(p1.stderr.readline())
    #     # output = p2.stdout.readline()
    #     # if p2.poll() is not None:
    #         # break
    #     # if output:
    #         # print(output.strip())

if __name__ == "__main__":    
    test()
