import requests
from PIL import Image
from io import BytesIO
from mimetypes import MimeTypes
from pilkit.processors import SmartResize, ResizeToFit
from colorthief import ColorThief
import mutagen
from mutagen.id3 import APIC


def add_artwork(image_uri, file_path, processor='SmartResize'):
    size = (300, 300)
    try:
        if 'http' in image_uri:
            # Remote image file
            h = requests.head(image_uri)
            content_type = h.headers.get('content-type')
            r = requests.get(image_uri)
            image_data = r.content
            print(content_type)
        else:
            # Local image file
            mime = MimeTypes()
            content_type, a = mime.guess_type(filename)
            with open(image_uri, 'rb') as file:
                image_data = file.read()
    except Exception as e:
        print("Coult not open {0}".format(image_uri))
        return False

    # Try to embed picture
    try:
        fd = mutagen.File(file_path)
        image = Image.open(BytesIO(image_data))
        if 'resizetofit' in processor.lower():
            color_thief = ColorThief(BytesIO(image_data))
            # get the dominant color
            # dominant_color = color_thief.get_color(quality=10)
            dominant_color = color_thief.get_palette()[0]
            processor = ResizeToFit(size[0], size[1])
        else:
            processor = SmartResize(size[0], size[1])
            dominant_color = (255, 255, 255)
        print(dominant_color)
        new_img = processor.process(image)
        background = Image.new("RGB", size, dominant_color)
        background.paste(new_img, mask=new_img.split()[3]) # 3 is the alpha channel
        temp = BytesIO()
        background.save(temp, format="JPEG")
        fd.tags.add(
            APIC(
                encoding=3,
                mime=content_type,
                type=3, desc=u'Album',
                data=temp.getvalue()
            ))
        fd.save()
        return True
    except Exception as e:
        print(e)
        print('Could not set album art')
        return False
