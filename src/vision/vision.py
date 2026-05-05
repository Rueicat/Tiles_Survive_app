## Vision functions
## list:
##    - resize to template size
##    - similarity tool, return true or false

from PIL import Image, ImageChops

##------Similarity by using PIL------------------
## ImageCHops, math method to calulate pictuire

def resize_to_template_size(image_from_adb):



##------Similarity by using PIL------------------
## ImageCHops, math method to calulate pictuire


def similarity_by_pil(image1_path, image2_path, threshold=0.6):

    image_capture = Image.open(image_capture_frome_adb)
    image_template = Image.open(image_template_in_project)

    # resize
