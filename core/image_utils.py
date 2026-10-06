from PIL import Image


def resize_image(image, size=(400, 400)):
    """
    Resize the image to ensure that the smallest dimension is at least the target size,
    while maintaining the aspect ratio. This function preserves transparency for PNG images.
    """
    # Check if the image has an alpha channel (transparency)
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        # Do not convert to 'RGB' as this would remove transparency
        pass  # Keep the image as is if it has transparency
    else:
        # Convert to 'RGB' only if there is no transparency (e.g., JPEG or other formats)
        image = image.convert('RGB')


    img_width, img_height = image.size
    target_width, target_height = size

    # Calculate the scaling factor
    scale = max(target_width / img_width, target_height / img_height)
    new_width = int(img_width * scale)
    new_height = int(img_height * scale)

    # Resize the image with the new dimensions
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return image
