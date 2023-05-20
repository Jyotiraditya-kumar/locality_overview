import urllib3
import cv2
from io import BytesIO
import numpy as np
import json

black_lower = (0, 0, 0)
black_upper = (180, 255, 30)
red_lower = (0, 50, 50)
red_upper = (10, 255, 255)


def get_image(x, y, z, api_key):
    http = urllib3.PoolManager()
    url = f'https://api.mapbox.com/styles/v1/lsda3m0ns/clf51knji005901q66lwmy0yj/tiles/{z}/{x}/{y}?access_token={api_key}'
    r = http.request('GET', url)
    image = np.asarray(bytearray(r.data), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


def get_pixel_summary(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    black_mask = cv2.inRange(hsv, black_lower, black_upper)
    red_mask = cv2.inRange(hsv, red_lower, red_upper)
    black_pixels = cv2.countNonZero(black_mask)
    red_pixels = cv2.countNonZero(red_mask)
    total_number_of_pixels = image.shape[0] * image.shape[1]
    return black_pixels, red_pixels, total_number_of_pixels


def lambda_handler(event, context):
    x, y, z, api_key = None, None, None, None
    if 'x' in event:
        x = event['x']
    else:
        x = event['queryStringParameters']['x']
    if 'y' in event:
        y = event['y']
    else:
        y = event['queryStringParameters']['y']
    if 'z' in event:
        z = event['z']
    else:
        z = event['queryStringParameters']['z']
    if 'api_key' in event:
        api_key = event['api_key']
    else:
        api_key = event['queryStringParameters']['api_key']

    x, y, z = int(x), int(y), int(z)
    try:
        image = get_image(x, y, z, api_key)
        black_pixels, red_pixels, total_number_of_pixels = get_pixel_summary(image)
    except Exception as e:
        print(e)
        black_pixels, red_pixels, total_number_of_pixels = None, None, None

    return [black_pixels, red_pixels, total_number_of_pixels]