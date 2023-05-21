# -*- coding: utf-8 -*-
"""Building And Road Growth.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1RKYplQeBhgjnSLZthhKwHTeP525C4w4Z
"""
import time
from src import clogger as logger

from src import lambda_function

log = logger.get_logger('LocalityArea')
import streamlit as st

"""## Imports"""
API_KEY = "pk.eyJ1IjoibHNkYTNtMG5zIiwiYSI6ImNreHBzb2FlbzAyZHMycG1wd2lvaXF3dDcifQ.otSnSJfhxkSjeXRTGGTE3w"

from typing import Tuple
import mercantile
from collections import namedtuple
from shapely.geometry import Polygon, MultiPolygon, box
from shapely import wkt
import random
import requests
import pyproj
import json
from shapely.geometry import Point, mapping
from functools import partial
from shapely.ops import transform
import pandas as pd
from pandarallel import pandarallel
import folium

from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
# from IPython.display import display, HTML

import warnings
from shapely.errors import ShapelyDeprecationWarning

# from src import lambda_function

# from shapely.errors import FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)

"""## util functions"""

"""
  NOTE :
    1. degree to wms functions are slightly inaccurate hence we are using mercantile library
    2. check here for more info :
    https://github.com/mapbox/mercantile/blob/main/mercantile/__init__.py
    3. a tile can only be converted to bbox 
    if exact location is needed use top left as exact location of tile
    4. image is 256x256
    5. pixel cords are 0 indexed
"""

CORDINATE = namedtuple('CORDINATE', ['lat', 'lng'])
WMTS_TILE = namedtuple('WMTS_TILE', ['lat', 'lng', 'x', 'y', 'zoom'])
WMTS_TILE_BBOX = namedtuple('WMTS_TILE_BBOX', ["left", "bottom", "right", "top", 'zoom'])
POINT_LOCATION = namedtuple('POINT_LOCATION', ['cordinate', 'zoom'])
PIXEL_CORD = namedtuple('PIXEL_CORD', ['lng_x', 'lat_y'])


def dict_get(data, keys, default=None):
    assert type(keys) is list
    if data is None:
        return default
    if not keys:
        return data
    return dict_get(data.get(keys[0]), keys[1:], default)


def epsg_4326_to_epsg_3857(cordinate: CORDINATE) -> CORDINATE:
    """converts lat lng to epsg 3857"""
    x, y = mercantile.xy(cordinate.lng, cordinate.lat)
    return CORDINATE(y, x)


def epsg_3857_to_epsg_4326(cordinate: CORDINATE) -> CORDINATE:
    """converts epsg 3857 to lat lng"""
    lng, lat = mercantile.xy(cordinate.lng, cordinate.lat)
    return CORDINATE(lat, lng)


def epsg_4326_to_wmts_tile_cords(point_loc: POINT_LOCATION) -> WMTS_TILE:
    """converts epsg 3857 to wmts tile cords"""
    tile = mercantile.tile(point_loc.cordinate.lng, point_loc.cordinate.lat, point_loc.zoom)
    return WMTS_TILE(tile.y, tile.x, tile.x, tile.y, point_loc.zoom)


def wmts_tile_to_epsg_4326(tile: WMTS_TILE) -> WMTS_TILE_BBOX:
    """converts wmts tile cords to lat lng"""
    mb = mercantile.bounds(tile.x, tile.y, tile.zoom)
    return WMTS_TILE_BBOX(mb.west, mb.south, mb.east, mb.north, tile.zoom)  # mb.left, mb.bottom, mb.right, mb.top


def epsg_3857_to_wmts_tile_cords(point_loc: POINT_LOCATION) -> WMTS_TILE:
    """converts epsg 3857 to wmts tile cords"""
    point_loc = POINT_LOCATION(epsg_3857_to_epsg_4326(point_loc.cordinate), point_loc.zoom)
    tile = mercantile.tile(point_loc.cordinate.lng, point_loc.cordinate.lat, point_loc.zoom)
    return WMTS_TILE(tile.y, tile.x, tile.x, tile.y, point_loc.zoom)


def wmts_tile_to_epsg_3857(tile: WMTS_TILE) -> WMTS_TILE_BBOX:
    """converts wmts tile cords to epsg 3857"""
    mb = mercantile.xy_bounds(tile.x, tile.y, tile.zoom)
    return WMTS_TILE_BBOX(mb.left, mb.bottom, mb.right, mb.top, tile.zoom)


def pixel_to_epsg_3857(tile: WMTS_TILE, pixel_cord: PIXEL_CORD) -> CORDINATE:
    """converts pixel cords to epsg 3857"""
    tile_bbox = wmts_tile_to_epsg_3857(tile)
    x = tile_bbox.left + (pixel_cord.lng_x * (tile_bbox.right - tile_bbox.left) / 256)
    y = tile_bbox.top - (pixel_cord.lat_y * (tile_bbox.top - tile_bbox.bottom) / 256)
    return CORDINATE(y, x)


def epsg_3857_to_pixel(tile: WMTS_TILE, cordinate: CORDINATE) -> PIXEL_CORD:
    """converts epsg 3857 to pixel cords"""
    tile_bbox = wmts_tile_to_epsg_3857(tile)
    lng_x = int(256 * (cordinate.lng - tile_bbox.left) / (tile_bbox.right - tile_bbox.left))
    lat_y = int(256 * (tile_bbox.top - cordinate.lat) / (tile_bbox.top - tile_bbox.bottom))
    return PIXEL_CORD(lng_x, lat_y)


def pixel_to_epsg_4326(tile: WMTS_TILE, pixel_cord: PIXEL_CORD) -> CORDINATE:
    """converts pixel cords to epsg 4326"""
    tile_bbox = wmts_tile_to_epsg_4326(tile)
    x = tile_bbox.left + (pixel_cord.lng_x * (tile_bbox.right - tile_bbox.left) / 256)
    y = tile_bbox.top - (pixel_cord.lat_y * (tile_bbox.top - tile_bbox.bottom) / 256)
    return CORDINATE(y, x)


def epsg_4326_to_pixel(tile: WMTS_TILE, cordinate: CORDINATE) -> PIXEL_CORD:
    """converts epsg 4326 to pixel cords"""
    tile_bbox = wmts_tile_to_epsg_4326(tile)
    lng_x = int(256 * (cordinate.lng - tile_bbox.left) / (tile_bbox.right - tile_bbox.left))
    lat_y = int(256 * (tile_bbox.top - cordinate.lat) / (tile_bbox.top - tile_bbox.bottom))
    return PIXEL_CORD(lng_x, lat_y)


def _wkt_to_geom(wkt_str):
    return wkt.loads(wkt_str)


def _polygon_to_bbox(polygon):
    return polygon.bounds


def _bbox_to_polygon(bbox):
    return box(*bbox)


def _geom_bbox(geom):
    if isinstance(geom, Polygon) or isinstance(geom, MultiPolygon):
        return _polygon_to_bbox(geom)
    elif isinstance(geom, str):
        return _polygon_to_bbox(_wkt_to_geom(geom))
    elif len(geom) == 4:
        return geom
    else:
        raise Exception(f"Invalid geometry type ", {type(geom)})


def geom_bbox_to_wmts_tile_bbox(geom_bbox: tuple, zoom: int) -> Tuple[WMTS_TILE, WMTS_TILE]:
    """converts geom bbox to wmts tile bbox"""
    top_left = CORDINATE(lng=geom_bbox[0], lat=geom_bbox[3])
    bottom_right = CORDINATE(lng=geom_bbox[2], lat=geom_bbox[1])
    # print(top_left, bottom_right)
    tile1 = epsg_4326_to_wmts_tile_cords(POINT_LOCATION(top_left, zoom))
    tile2 = epsg_4326_to_wmts_tile_cords(POINT_LOCATION(bottom_right, zoom))
    return (WMTS_TILE(tile1.y, tile1.x, tile1.x, tile1.y, zoom), WMTS_TILE(tile2.y, tile2.x, tile2.x, tile2.y, zoom))


def geom_to_wmts_tile_bbox(geom, zoom: int) -> Tuple[WMTS_TILE, WMTS_TILE]:
    """converts geom to wmts tile bbox"""
    geom_bbox = _geom_bbox(geom)
    # print(geom_bbox)
    return geom_bbox_to_wmts_tile_bbox(geom_bbox, zoom)


def show_image(img, resized=False, factor=0.5):
    import cv2
    if resized:
        img = cv2.resize(img, (0, 0), fx=factor, fy=factor)

    cv2.imshow('image' + str(random.randint(0, 100)), img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def image_pixel_to_epsg_4326_cords(x, y, tile: WMTS_TILE, image_shape: tuple) -> CORDINATE:
    """converts image pixel cords to epsg 4326"""
    tile_bbox = wmts_tile_to_epsg_4326(tile)

    lng_x = tile_bbox.left + (x * (tile_bbox.right - tile_bbox.left) / image_shape[1])
    lat_y = tile_bbox.top - (y * (tile_bbox.top - tile_bbox.bottom) / image_shape[0])
    return CORDINATE(lat_y, lng_x)


def get_tile_road_building_area1(tile: WMTS_TILE):
    event = {'x': tile.x, 'y': tile.y, 'z': tile.zoom, 'api_key': API_KEY}
    # lambda_url = f"https://am5a7ipqwtbms5wzuo5bxapwta0espgk.lambda-url.us-east-2.on.aws/?x={tile.x}&y={tile.y}&z={tile.zoom}&api_key={API_KEY}"
    # response = requests.get(lambda_url)
    # if response.status_code == 200:
    data = lambda_function.lambda_handler(event, context=None)
    return [data[0], data[1], data[2]]


def get_tile_road_building_area(tile: WMTS_TILE):
    lambda_url = f"https://am5a7ipqwtbms5wzuo5bxapwta0espgk.lambda-url.us-east-2.on.aws//?x={tile.x}&y={tile.y}&z={int(float(tile.zoom))}&api_key={API_KEY}"
    response = requests.get(lambda_url)
    print(lambda_url)
    if response.status_code == 200:
        data = response.json()
        return [data[0], data[1], data[2]]
    else:
        print(response.text, lambda_url)
        return [None, None, None]


def generate_polygon(lat, lng, radius):
    point = Point(lng, lat)
    local_azimuthal_projection = f"+proj=aeqd +R=6371000 +units=m +lat_0={point.y} +lon_0={point.x}"

    wgs84_to_aeqd = partial(
        pyproj.transform,
        pyproj.Proj('+proj=longlat +datum=WGS84 +no_defs'),
        pyproj.Proj(local_azimuthal_projection),
    )

    aeqd_to_wgs84 = partial(
        pyproj.transform,
        pyproj.Proj(local_azimuthal_projection),
        pyproj.Proj('+proj=longlat +datum=WGS84 +no_defs'),
    )

    point_transformed = transform(wgs84_to_aeqd, point)

    buffer = point_transformed.buffer(radius)
    area_meters = buffer.area

    buffer_wgs84 = transform(aeqd_to_wgs84, buffer)
    return buffer_wgs84, area_meters


def generate_tile_list_which_fall_in_polygon(polygon, zoom):
    tile1, tile2 = geom_to_wmts_tile_bbox(polygon, zoom)
    X1 = min(tile1.x, tile2.x)
    X2 = max(tile1.x, tile2.x)
    Y1 = min(tile1.y, tile2.y)
    Y2 = max(tile1.y, tile2.y)

    tile_list = []
    for x in range(X1, X2 + 1):
        for y in range(Y1, Y2 + 1):
            log.info(f'Tile {x},{y} Generated')
            wmts_bbox = wmts_tile_to_epsg_4326(WMTS_TILE(y, x, x, y, zoom))
            top_corner = Point(wmts_bbox.left, wmts_bbox.top)
            # print(top_corner)
            if polygon.contains(top_corner):
                tile_list.append(WMTS_TILE(y, x, x, y, zoom))
    return tile_list


def get_tile_inside_poly(x, y, zoom, polygon):
    wmts_bbox = wmts_tile_to_epsg_4326(WMTS_TILE(y, x, x, y, zoom))
    top_corner = Point(wmts_bbox.left, wmts_bbox.top)
    if polygon.contains(top_corner):
        return WMTS_TILE(y, x, x, y, zoom)
    else:
        return None


def generate_tile_list_which_fall_in_polygon1(polygon, zoom):
    tile1, tile2 = geom_to_wmts_tile_bbox(polygon, zoom)
    X1 = min(tile1.x, tile2.x)
    X2 = max(tile1.x, tile2.x)
    Y1 = min(tile1.y, tile2.y)
    Y2 = max(tile1.y, tile2.y)

    tile_list = []
    tot = (X2 + 1 - X1) * (Y2 + 1 - Y1)
    x_range = range(X1, X2 + 1)
    y_range = range(Y1, Y2 + 1)
    import streamlit as st
    # bar = st.progress(0, f'Tiles generting')
    c = 0
    start_time = time.perf_counter()
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(get_tile_inside_poly, x, y, zoom, polygon) for x in x_range for y in y_range]
        for future in as_completed(futures):
            res = future.result()
            c += 1
            per = round(c / tot, 2)
            if res is not None:
                tile_list.append(res)
            # bar.progress(0,
            #              f'Tiles generting {per} | {c}/{tot} | Inside Polygon {len(tile_list)}| Elapsed time {time.perf_counter() - start_time}')
    return tile_list


def building_road_area_for_polygon1(polygon, zoom, num_workers=100):
    start_time = time.perf_counter()
    tile_list = generate_tile_list_which_fall_in_polygon(polygon, zoom)
    if not tile_list:
        return 0, 0, 0
    pandarallel.initialize(nb_workers=num_workers, progress_bar=True)
    tile_df = pd.DataFrame({'tile': tile_list})
    try:
        building_areas = tile_df.parallel_apply(lambda x: get_tile_road_building_area(x['tile']), axis=1)
    except:
        building_areas = tile_df.apply(lambda x: get_tile_road_building_area(x['tile']), axis=1)
    end_time = time.perf_counter()
    import streamlit as st
    st.write(end_time - start_time)
    building_area = sum(building_areas.apply(lambda x: x[0]))
    road_area = sum(building_areas.apply(lambda x: x[1]))
    total_area = sum(building_areas.apply(lambda x: x[2]))

    return building_area, road_area, total_area


def _thread_func(tiles_list):
    if st.secrets.app_configs.use_lambda_function:
        road_building_function = get_tile_road_building_area1
    else:
        road_building_function = get_tile_road_building_area
    all_threads_result = []
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(road_building_function, tile) for tile in tiles_list]
        # res = executor.map(get_tile_road_building_area, tile_list)
        for future in as_completed(futures):
            res = future.result()
            all_threads_result.append(res)
    return all_threads_result


def building_road_area_for_polygon(polygon, zoom, num_workers=100):
    log.info('Tile List Generating')
    tile_list = generate_tile_list_which_fall_in_polygon(polygon, zoom)
    log.info('Tile List Generated')
    import streamlit as st
    start_time = time.perf_counter()
    complete_area = []
    tile_list_ = [tile_list[i:i + 100] for i in range(0, len(tile_list), 100)]
    c = 0
    # bar = st.progress(0, 'area searched')
    with ProcessPoolExecutor(max_workers=7) as executor_:
        futures_ = [executor_.submit(_thread_func, tiles) for tiles in tile_list_]
        for future_ in as_completed(futures_):
            x = future_.result()
            complete_area.extend(x)
            c += len(x)
            # per = c / len(tile_list)
            # bar.progress(per,
            #              text=f'{round(per * 100, 2)} {c}/{len(tile_list)} searched | Elapsed time : {time.perf_counter() - start_time}')
    # st.write()
    # bar.empty()
    # building_areas = tile_df.parallel_apply(lambda x: get_tile_road_building_area(x['tile']), axis=1)
    building_areas = pd.Series(complete_area)
    building_area = sum(building_areas.apply(lambda x: x[0] if x[0] else 0))
    road_area = sum(building_areas.apply(lambda x: x[1] if x[1] else 0))
    total_area = sum(building_areas.apply(lambda x: x[2] if x[2] else 0))

    return building_area, road_area, total_area


def print_report(building_area, road_area, total_area, area_meters):
    print("-" * 50)
    print(f"Total Area: {round(area_meters / 1000_000, 2)} km^2")
    print(f"Building Area: {round(building_area * area_meters / (total_area * 1000_000), 2)} km^2")
    print(f"Road Area: {round(road_area * area_meters / (total_area * 1000_000), 2)} km^2")
    print("-" * 50)


"""## Parameters

### KEYS
"""

"""### Location Params"""
if __name__ == "__main__":
    ...
    # lat = 12.918877105665517
    # lng = 77.64305106225419
    # zoom = 18
    # radius = 500  # meters
    # num_workers = 100
    # a,b=main(lat, lng, zoom, radius, None)
    # print(a,b)

# print_report(building_area, road_area, total_area, area_meters)
