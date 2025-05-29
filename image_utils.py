from PIL import Image, ExifTags
from typing import Optional


def load_image(image_path: str) -> Image.Image:
    return Image.open(image_path)


def get_exif_datetime(image_path: str) -> Optional[str]:
    try:
        img = Image.open(image_path)
        exif_data = img.getexif()
        if exif_data:
            for tag, value in exif_data.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                if decoded == "DateTimeOriginal":
                    return value
        return None
    except Exception as e:
        print(f"Error extracting EXIF from {image_path}: {e}")
        return None
