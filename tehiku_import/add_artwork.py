import traceback
import requests
from PIL import Image, ImageFilter
from io import BytesIO
from mimetypes import MimeTypes
from pilkit.processors import SmartResize
from colorthief import ColorThief
import mutagen
from mutagen.id3 import APIC


class PortraitToLandscapeEffect(object):
    '''
    Custom image processor which adds a blurred background effect of the
    original image where the image is a portrait and we want it to be
    landscape. This is similar to what people do when the show a mobile
    phone video that's in portrait in a widescreen video viewport.
    '''

    def __init__(self, original_im=None, ar=16.0/9.0):
        self.aspect_ratio = ar
        self.blur_radius = 160
        self.portrait_ratio = 1

        self.original = original_im
        if original_im is None:
            self.width = 1
            self.height = 1
        else:
            self.width, self.height = original_im.size

        self.target_width = int(self.aspect_ratio * float(self.height))
        self.target_height = int(self.target_width / self.aspect_ratio)

        self.scaled_height = \
            int(self.target_width * float(self.height)/float(self.width))

        self.landscape = False
        self.scaled_width = self.scaled_height

    def is_portrait(self):
        if self.height > self.width:
            return True
        else:
            return False

    def should_reprocess(self):
        if float(self.width)/float(self.height) <= self.portrait_ratio:
            return True
        else:
            return False

    def make_background(self):
        self.background = self.original.copy()
        if self.landscape:
            self.background = self.background.resize(
                (self.scaled_width, self.target_height), Image.ANTIALIAS)
        else:
            self.background = self.background.resize(
                (self.target_width, self.scaled_height), Image.ANTIALIAS)

        self.background = self.background.filter(
            ImageFilter.GaussianBlur(radius=self.blur_radius))

    def make_image(self):
        self.processed = Image.new(
            'RGB', (self.target_width, self.target_height))
        if self.landscape:
            self.processed.paste(
                self.background,
                (-int((self.scaled_width - self.target_width)/2.0), 0))
            x_loc = 0
            y_loc = int((self.target_height - self.height)/2.0)
        else:
            self.processed.paste(
                self.background,
                (0, -int((self.scaled_height - self.target_height)/2.0)))
            x_loc = int((self.target_width - self.width)/2.0)
            y_loc = 0

        del self.background
        self.processed.paste(self.original, (x_loc, y_loc))

    def process(self, image=None):
        if image is not None:
            self.__init__(image)

        if self.should_reprocess():
            self.make_background()
            self.make_image()
            return self.processed
        else:
            return self.original


class SquareImageEffect(PortraitToLandscapeEffect):
    '''
    Like the Portrain to Landscape effect only it targests a sqaure output
    '''

    def __init__(self, original_im=None):
        self.aspect_ratio = 1
        self.blur_radius = 160

        self.original = original_im
        if original_im is None:
            self.width = 1
            self.height = 1
        else:
            self.width, self.height = original_im.size

        # Landscape
        if self.width >= self.height:
            self.landscape = True
            self.target_width = self.width
            self.target_height = self.width
            self.scaled_width = \
                int(self.target_width * float(self.target_height)/float(self.height))

        # Portrait
        else:
            self.target_width = self.height
            self.target_height = self.height
            self.scaled_height = \
                int(self.target_height * float(self.target_width)/float(self.width))

    def should_reprocess(self):
        if float(self.width)/float(self.height) == 1:
            return False
        else:
            return True


def add_artwork(image_uri, file_path, processor='SmartResize'):
    size = (300, 300)
    try:
        if 'http' in image_uri:
            # Remote image file
            r = requests.get(image_uri)
            image_data = r.content
        else:
            # Local image file
            with open(image_uri, 'rb') as file:
                image_data = file.read()

    except Exception:
        print("Could not open {0}".format(image_uri))
        return False

    # Try to embed picture
    try:

        image = Image.open(BytesIO(image_data))
        if 'resizetofit' in processor.lower():
            color_thief = ColorThief(BytesIO(image_data))
            # get the dominant color
            # dominant_color = color_thief.get_color(quality=10)
            dominant_color = color_thief.get_palette()[0]
            processors = [SquareImageEffect(), SmartResize(size[0], size[1])]
        else:
            processors = [SmartResize(size[0], size[1])]
            dominant_color = (255, 255, 255)

        for p in processors:
            image = p.process(image)

        background = Image.new("RGB", size, dominant_color)
        try:
            # 3 is the alpha channel
            background.paste(image, mask=image.split()[3])
        except Exception:
            background.paste(image)
        temp = BytesIO()
        background.save(temp, format="JPEG")
        fd = mutagen.File(file_path)
        fd.tags.add(
            APIC(
                encoding=3,
                mime='image/jpeg',
                type=3, desc=u'Album',
                data=temp.getvalue()
            )
        )
        fd.save()
        return True
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        print('Could not set album art')
        return False
