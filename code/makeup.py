import cv2
import os
import numpy as np
from skimage.filters import gaussian


def sharpen(img):
    img = img * 1.0
    gauss_out = gaussian(img, sigma=5, channel_axis=-1)

    alpha = 1.5
    img_out = (img - gauss_out) * alpha + img

    img_out = img_out / 255.0

    mask_1 = img_out < 0
    mask_2 = img_out > 1

    img_out = img_out * (1 - mask_1)
    img_out = img_out * (1 - mask_2) + mask_2
    img_out = np.clip(img_out, 0, 1)
    img_out = img_out * 255
    return np.array(img_out, dtype=np.uint8)


def soft_light_blend(base, blend_color_img):
    """
    Applies soft light blending mode.
    Assumes base and blend_color_img are in the same color space (e.g., BGR)
    and have the same dimensions.
    """
    # Scale to 0-1 float range
    base_float = base.astype(np.float32) / 255.0
    blend_float = blend_color_img.astype(np.float32) / 255.0

    # Soft light formula
    result_float = np.where(blend_float < 0.5,
                            2 * base_float * blend_float + base_float**2 * (1 - 2 * blend_float),
                            2 * base_float * (1 - blend_float) + np.sqrt(base_float) * (2 * blend_float - 1))

    # Scale back to 0-255 uint8 range
    return np.clip(result_float * 255, 0, 255).astype(np.uint8)


def hair(image, parsing, part=17, color=[230, 50, 20], intensity=0.75):
    """
    Applies color to a specific part of the image using soft light blending with adjustable intensity.
    'image' is expected in BGR format.
    'color' is a list [b, g, r].
    'intensity' is a float between 0.0 and 1.0.
    """
    b, g, r = color
    # Create a solid color image with the target color
    tar_color_img = np.zeros_like(image)
    tar_color_img[:, :] = (b, g, r)

    # Blend the original image with the solid color image
    blended_image = soft_light_blend(image, tar_color_img)

    # Apply sharpening for hair
    if part == 17:
        blended_image = sharpen(blended_image)

    # Create a copy of the original image to modify
    changed = image.copy()
    
    # Extract the pixels for the original and the makeup version
    original_pixels = image[parsing == part]
    makeup_pixels = blended_image[parsing == part]

    if len(original_pixels) > 0:
        # Ensure intensity is within a valid range [0.0, 1.0]
        safe_intensity = np.clip(intensity, 0.0, 1.0)
        
        # Blend the makeup pixels with the original pixels based on intensity
        # dst = src1*alpha + src2*beta + gamma
        blended_pixels = cv2.addWeighted(makeup_pixels, safe_intensity, original_pixels, 1 - safe_intensity, 0)
        
        # Apply the result back to the image
        changed[parsing == part] = blended_pixels
    
    return changed


if __name__ == '__main__':
    # 1  face
    # 10 nose
    # 11 teeth
    # 12 upper lip
    # 13 lower lip
    # 17 hair
    num = 116
    table = {
        'hair': 17,
        'upper_lip': 12,
        'lower_lip': 13
    }
    image_path = '/home/zll/data/CelebAMask-HQ/test-img/{}.jpg'.format(num)
    parsing_path = 'res/test_res/{}.png'.format(num)

    image = cv2.imread(image_path)
    ori = image.copy()
    parsing = np.array(cv2.imread(parsing_path, 0))
    parsing = cv2.resize(parsing, image.shape[0:2], interpolation=cv2.INTER_NEAREST)

    parts = [table['hair'], table['upper_lip'], table['lower_lip']]
    # colors = [[20, 20, 200], [100, 100, 230], [100, 100, 230]]
    colors = [[100, 200, 100]]
    for part, color in zip(parts, colors):
        image = hair(image, parsing, part, color)
    cv2.imwrite('res/makeup/116_ori.png', cv2.resize(ori, (512, 512)))
    cv2.imwrite('res/makeup/116_2.png', cv2.resize(image, (512, 512)))

    cv2.imshow('image', cv2.resize(ori, (512, 512)))
    cv2.imshow('color', cv2.resize(image, (512, 512)))

    # cv2.imshow('image', ori)
    # cv2.imshow('color', image)

    cv2.waitKey(0)
    cv2.destroyAllWindows()