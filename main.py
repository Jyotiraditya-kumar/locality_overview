import datetime

import pandas as pd
import shapely
import streamlit as st
import streamlit_folium as st_folium
from PIL import Image
from folium.plugins import DualMap
import folium
import building_and_road_growth as map_utils
import osmnx as ox

if 'city_layout' not in st.session_state:
    st.session_state['city_layout'] = None
if 'coord_layout' not in st.session_state:
    st.session_state['coord_layout'] = None

if 'city_last_clicked' not in st.session_state:
    st.session_state['city_last_clicked'] = None


def generate_default_map(lat=12.918877105665517, lng=78.64305106225419, zoom=18):
    map_satellite = folium.Map(
        location=[lat, lng], zoom_start=zoom,
        width='50%',
        tiles='https://api.mapbox.com/styles/v1/lsda3m0ns/clgys7avm00fy01p6gw2i3gw9/tiles/256/{z}/{x}/{y}@2x?access_token=' + API_KEY,
        attr='Satellite data')

    map_building_road_mask = folium.Map(location=[lat, lng], zoom_start=zoom, width='100%',
                                        tiles='https://api.mapbox.com/styles/v1/lsda3m0ns/clf51knji005901q66lwmy0yj/tiles/256/{z}/{x}/{y}@2x?access_token=' + API_KEY,
                                        attr='Mapbox Light',
                                        )

    return map_satellite, map_building_road_mask





API_KEY = "pk.eyJ1IjoibHNkYTNtMG5zIiwiYSI6ImNreHBzb2FlbzAyZHMycG1wd2lvaXF3dDcifQ.otSnSJfhxkSjeXRTGGTE3w"


@st.cache_data(show_spinner=False)
def get_city_polygon_from_osm(city_name):
    try:
        data = ox.geocode_to_gdf(f'{city_name}', which_result=None)
    except ValueError:
        data = ox.geocode_to_gdf(f'{city_name}', which_result=1)
    except:
        st.info(f'Location {city_name} not found')
    return data


def get_maps_by_lat_lng_buffer(lat, lng, zoom, radius):
    polygon, area_tuple = get_polygon_and_area(lat, lng, zoom, radius)
    satellite_map, building_map = map_utils.generate_map1(lat, lng, zoom, polygon)
    building_area, road_area, total_area = area_tuple
    area = dict(building_area=building_area, road_area=road_area, total_area=total_area)
    area_km2 = {}
    for key, value in area.items():
        area_km2[f'{key} km^2'] = value
    # st.success(f'Map Extracted {datetime.datetime.now()}')
    return satellite_map, building_map, area_km2


def get_maps_by_polygon(city_name, radius, zoom):
    building_area, road_area, total_area, lat, lng, polygon, name = _get_maps_by_polygon(city_name, radius, zoom)
    satellite_map, building_map = map_utils.generate_map1(lat, lng, zoom, polygon, tooltip=name)
    area = dict(building_area=building_area, road_area=road_area, total_area=total_area)
    area_km2 = {}
    area_km2['name']=name
    for key, value in area.items():
        area_km2[f'{key} km^2'] = value
    # st.success(f'Map Extracted {datetime.datetime.now()}')
    # st.success(f'Extracted {city_name} polygons')

    return satellite_map, building_map, area_km2, lat, lng


@st.cache_data(ttl=None, persist='disk', show_spinner=False)
def _get_maps_by_polygon(city_name, radius, zoom):
    data = get_city_polygons(city_name)
    # data
    geom = data['geometry']
    lat = data['lat']
    lon = data['lon']
    name = data['display_name']
    if isinstance(geom, str):
        polygon = shapely.from_wkt(geom)
    elif isinstance(geom, shapely.Polygon):
        # lon, lat = geom.centroid.coords[0]
        polygon, area_meters = map_utils.generate_polygon(lat, lon, radius)
    elif isinstance(geom, shapely.Point):
        # lng, lat = geom.coords[0]
        polygon, area_meters = map_utils.generate_polygon(lat, lon, radius)
    else:
        polygon = geom
    building_area, road_area, total_area = map_utils.building_road_area_for_polygon(polygon, zoom, num_workers=100)
    total_area_ = round(area_meters / 1000_000, 2)
    building_area_ = round(building_area * area_meters / (total_area * 1000_000), 2)
    road_area_ = round(road_area * area_meters / (total_area * 1000_000), 2)
    return building_area_, road_area_, total_area_, lat, lon, polygon, name


def get_city_polygons(city_name):
    df = get_city_polygon_from_osm(city_name)
    if df is None:
        st.info(f'location {city_name} not found')
    data = df.to_dict(orient='records')[0]
    return data


@st.cache_data(show_spinner=False)
def get_polygon_and_area(lat, lng, zoom, radius, polygon=None):
    polygon, area_meters = map_utils.generate_polygon(lat, lng, radius)
    building_area, road_area, total_area = map_utils.building_road_area_for_polygon(polygon, zoom, num_workers=100)
    total_area_ = round(area_meters / 1000_000, 2)
    building_area_ = round(building_area * area_meters / (total_area * 1000_000), 2)
    road_area_ = round(road_area * area_meters / (total_area * 1000_000), 2)
    return polygon, tuple([building_area_, road_area_, total_area_])


def city_submit_callback(city, radius, zoom_level):
    try:
        radius = float(radius)
    except:
        st.sidebar.error('Enter proper radius')
        st.stop()
    st.session_state['city_radius'] = str(radius)
    st.session_state['city_name'] = str(city)
    map1, map2, area, lat, lng = get_maps_by_polygon(city.strip(), radius, int(zoom_level))
    area = pd.DataFrame([area])
    a = dict(map1=map1, map2=map2, area_info=area, lat=lat, lng=lng, zoom_level=int(zoom_level))
    st.session_state['city_layout'] = a


def coord_submit_callback(lat, lon, radius, zoom_level):
    try:
        lat = float(lat)
    except:
        st.sidebar.error('Enter proper Latitude')
        st.stop()
    try:
        lon = float(lon)
    except:
        st.sidebar.error('Enter proper Longitude')
        st.stop()
    try:
        radius = float(radius)
    except:
        st.sidebar.error('Enter proper Radius')
        st.stop()
    zoom_level = float(int(zoom_level))
    st.session_state['point_radius'] = str(radius)
    st.session_state['coords'] = ",".join([str(lat), str(lon)])
    map1, map2, area = get_maps_by_lat_lng_buffer(lat, lon, zoom_level, radius)
    area = pd.DataFrame([area])
    a = dict(map1=map1, map2=map2, area_info=area, lat=lat, lng=lon, zoom_level=int(zoom_level))
    st.session_state['coord_layout'] = a


def set_session_variable(key, val):
    st.session_state[key] = val


def main_loop():
    # rerun_count()
    # st.write("----")
    # st.session_state
    _, col1, col2, col3 = st.sidebar.columns((1, 5, 1, 4))
    with col1:
        st.title("Location Analysis")
    with col3:
        st.text("\n")
        # col11, col22 = st.columns((1, 3))
        # with col22:
        st.image("favicon.png", width=60)

    st.sidebar.write("----")
    select_by = st.sidebar.radio(
        "Select Area By",
        ("Locality", "Coordinates",),
        index=0,
        horizontal=True,
    )

    if select_by == "Locality":
        city = st.sidebar.text_input("Locality", value=st.session_state.get('city_name', ''),
                                     placeholder='locality..',
                                     autocomplete='bengaluru, hapur, aizawl')
        radius = st.sidebar.text_input('Radius', help='radius', value=st.session_state.get('city_radius', ''),
                                       key='city_radius_')

        # city_ = st.sidebar.multiselect("City Name",
        #                               options=['bengaluru', 'hapur', 'aizawl'])

        zoom_level = '18'
        if st.session_state.city_layout is not None:
            layout = st.session_state['city_layout']
            add_map_to_layout(**layout)
        else:
            map1, map2 = generate_default_map()
            add_map_to_layout(map1, map2, 0, 0, 18, None, None)
        submit = st.sidebar.button('Submit', type='primary', on_click=city_submit_callback, key='city_button',
                                   args=(city, radius, zoom_level))
        # city_submit_callback(city, int(radius), int(zoom_level))



    elif select_by == 'Coordinates':
        lat = st.sidebar.text_input('Latitude', value=st.session_state.get('coords', ',').split(',')[0])
        lng = st.sidebar.text_input('Longitude', value=st.session_state.get('coords', ',').split(',')[1])
        radius_ = st.sidebar.text_input('Radius', help='radius', value=st.session_state.get('point_radius', '500'),
                                        key='point_radius_')
        zoom_level = '18'  # st.sidebar.text_input('Zoom Level', help='radius in meters', value='18')
        st.sidebar.write("----")

        if st.session_state.coord_layout is not None:
            layout = st.session_state['coord_layout']
            add_map_to_layout(**layout)
        else:
            map1, map2 = generate_default_map()
            add_map_to_layout(map1, map2, 0, 0, 18, None, None)
        submit = st.sidebar.button('Submit', type='primary', on_click=coord_submit_callback, key='coord_button',
                                   args=(lat, lng, radius_, zoom_level))


def get_legend():
    from branca.element import Template, MacroElement

    template = """
    {% macro html(this, kwargs) %}

    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>jQuery UI Draggable - Default functionality</title>
      <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">

      <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
      <script src="https://code.jquery.com/ui/1.12.1/jquery-ui.js"></script>

      <script>
      $( function() {
        $( "#maplegend" ).draggable({
                        start: function (event, ui) {
                            $(this).css({
                                right: "auto",
                                top: "auto",
                                bottom: "auto"
                            });
                        }
                    });
    });

      </script>
    </head>
    <body>


    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index:9999; border:2px solid grey; background-color:rgba(255, 255, 255, 0.8);
         border-radius:6px; padding: 10px; font-size:14px; right: 30px; bottom: 30px;'>

    <div class='legend-title'>Legend</div>
    <div class='legend-scale'>
      <ul class='legend-labels'>
        <li><span style='background:red;opacity:1;'></span>Road</li>
        <li><span style='background:black;opacity:1;'></span>Building</li>

      </ul>
    </div>
    </div>

    </body>
    </html>

    <style type='text/css'>
      .maplegend .legend-title {
        text-align: left;
        margin-bottom: 5px;
        font-weight: bold;
        font-size: 90%;
        color:black;
        }
      .maplegend .legend-scale ul {
        margin: 0;
        margin-bottom: 5px;
        padding: 0;
        float: left;
        list-style: none;
        color:black;
        }
      .maplegend .legend-scale ul li {
        font-size: 80%;
        list-style: none;
        margin-left: 0;
        line-height: 18px;
        margin-bottom: 2px;
        }
      .maplegend ul.legend-labels li span {
        display: block;
        float: left;
        height: 16px;
        width: 30px;
        margin-right: 5px;
        margin-left: 0;
        border: 1px solid #999;
        font-color:black;
        }
      .maplegend .legend-source {
        font-size: 80%;
        color: #777;
        clear: both;
        }
      .maplegend a {
        color: #777;
        }
    </style>
    {% endmacro %}"""

    macro = MacroElement()
    macro._template = Template(template)

    return macro


def add_map_to_layout(map1, map2, lat, lng, zoom_level, area_info, marker=None):
    m = DualMap(location=(lat, lng), layout='horizontal', zoom_start=zoom_level, tiles=None)
    m.m1 = map1
    m.m2 = map2
    legend = get_legend()
    map2.get_root().add_child(legend)
    # legend.add_to(m)
    # testmarker = folium.Marker([12.921045075125779, 77.64285922050476])
    if marker is not None:
        marker.add_to(m)
    f = folium.Figure(width='90%',ratio='50%')
    m.add_to(f)
    legend.add_to(f)
    st_folium.st_folium(f, width='10%', key='2')
    st.dataframe(area_info, use_container_width=True)


def _remove_top_padding_():
    st.markdown("""
        <style>
               .css-z5fcl4 {
                    padding-top: 0rem;
                    padding-bottom: 10rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
               .css-1d391kg {
                    padding-top: 3.5rem;
                    padding-right: 1rem;
                    padding-bottom: 3.5rem;
                    padding-left: 1rem;
                }
        </style>
        """, unsafe_allow_html=True)


def _max_width_():
    max_width_str = f"max-width: 1400px;"
    st.markdown(
        f"""
    <style>
    .reportview-container .main .block-container{{
        {max_width_str}
    }}
    </style>    
    """,
        unsafe_allow_html=True,
    )


def _dual_map_with_():
    max_width_str = f"max-width: 1400px;"
    st.markdown(
        '''
    <style>
        iframe#map_div,iframe#map_div2
         {
            height: 700px;
            width: 100%;
            position: absolute;
            outline: none;
         }
    </style>
    ''',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    favicon = Image.open("favicon.png")
    st.set_page_config(
        page_title="Spatic | Hyperlocal Analysis",
        page_icon=favicon,
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': "https://www.gospatic.com/#team",
        }
    )
    _remove_top_padding_()
    _max_width_()
    _dual_map_with_()
    main_loop()
