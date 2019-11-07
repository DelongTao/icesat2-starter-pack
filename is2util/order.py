import json
import socket
import tempfile
import zipfile
from datetime import timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import fiona
import geopandas as gpd
import requests
import requests.auth
from shapely.geometry.polygon import orient

import is2util.misc as misc

# enable KML support which is disabled by default
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'


EGI_URL = 'https://n5eil02u.ecs.nsidc.org/egi/request'

GEOG_CRS = fiona.crs.from_epsg(4326)


def format_datetime(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def format_time_range(start_datetime, end_datetime=None):
    '''Return serialized datetime string for e.g. 'time' api parameter'''
    if end_datetime is None:
        end_datetime = start_datetime + timedelta(days=1)

    return format_datetime(start_datetime) + ',' + format_datetime(end_datetime)


def format_polygon(poly):
    '''Return serialized polygon string for e.g. 'polygon' api parameter'''

    # Orient counter-clockwise
    poly = orient(poly, sign=1.0)

    # Format dictionary to polygon coordinate pairs for CMR polygon filtering
    formatted = ','.join(
        ['{0:.5f}'.format(c) for xy in zip(*poly.exterior.coords.xy) for c in xy]
    )

    return formatted


def simplify_for_url(polygon, limit=1000):
    '''
    Iteratively simplify 'polygon' until it is below 'limit' number of points
    '''
    tolerance = 0.05
    factor = 1.5
    simplified = polygon
    for _ in range(1000):
        if len(format_polygon(simplified)) >= limit:
            tolerance *= factor
            simplified = polygon.simplify(tolerance, preserve_topology=True)
        else:
            return simplified
    else:
        raise Exception("Unable to simplify sufficiently?")


def spatial_subset(geometry, time_range=None, short_name='ATL06', version='001'):
    '''
    Perform spatial subset from shapely geometry
    '''
    with tempfile.TemporaryDirectory() as tmpdir:
        zipped_shapefile_path = Path(tmpdir) / 'subset.zip'
        misc.geometry_to_zipped_shapefile(
            geometry, crs=GEOG_CRS, filepath=zipped_shapefile_path
        )
        result = spatial_subset_from_zipshapefile(
            zipped_shapefile_path=zipped_shapefile_path,
            time_range=time_range,
            short_name=short_name,
            version=version,
        )

    return result


def spatial_subset_from_zipshapefile(
    zipped_shapefile_path,
    time_range=None,
    short_name='ATL06',
    version='001',
    email=None,
):
    '''
    Perform spatial subset from first geometry in provided zipped shapefile
    '''
    with tempfile.TemporaryDirectory() as tmpdir:
        zipfile.ZipFile(zipped_shapefile_path).extractall(path=tmpdir)
        shapefile_paths = list(Path(tmpdir).glob('*.shp'))
        assert len(shapefile_paths) == 1
        shape_filepath = shapefile_paths[0]

        gdf = gpd.read_file(shape_filepath).to_crs({'init': 'epsg:4326'})

        geometry = simplify_for_url(gdf.iloc[0].geometry)

        polygon = format_polygon(geometry)

        # Common parameters
        params = {'short_name': short_name, 'version': version}
        # Granule filtering parameters
        params.update({'polygon': polygon})
        if time_range is not None:
            params.update({'time': format_time_range(*time_range)})
        # Other parameters
        params.update({'page_size': 2000, 'request_mode': 'async'})
        if email is not None:
            params.update({'email': email})

        files = {'shapefile': open(zipped_shapefile_path, 'rb')}

        response = requests.post(EGI_URL, files=files, params=params)

        response.raise_for_status()
        order_id = _parse_order_id(response.content)

    return order_id


def spatial_subset_from_url_params_async(
    geometry, time_range=None, short_name='ATL06', version='001', email=None
):
    '''Order a spatial subset using url parameters'''
    geometry = simplify_for_url(geometry)
    polygon = format_polygon(geometry)

    # Common params
    params = {'short_name': short_name, 'version': version, 'email': email}
    # Subset params
    params.update({'boundingshape': polygon})
    # Other params
    params.update({'subagent_id': 'ICESAT2'})
    # Granule filtering parameters
    params.update({'polygon': polygon})
    if time_range is not None:
        params.update({'time': format_time_range(time_range)})

    response = requests.get(EGI_URL, params=params)
    response.raise_for_status()
    order_id = _parse_order_id(response.content)

    return order_id


def spatial_subset_from_url_params_sync(
    geometry, time_range=None, short_name='ATL06', version='001'
):
    '''Order a spatial subset using url parameters'''
    geometry = simplify_for_url(geometry)
    polygon = format_polygon(geometry)

    # Common params
    params = {'short_name': short_name, 'version': version}
    # Subset params
    params.update({'boundingshape': polygon})
    # Other params
    params.update({'request_mode': 'sync', 'agent': 'NO'})
    # Granule filtering parameters
    params.update({'polygon': polygon})
    if time_range is not None:
        params.update({'time': format_time_range(time_range)})

    response = requests.get(EGI_URL, params=params)
    response.raise_for_status()

    return response.content


def _parse_order_id(xml):
    '''Extract order id from xml response'''
    root = ET.fromstring(xml)
    order_ids = [order.text for order in root.findall("./order/orderId")]
    assert len(order_ids) == 1
    order_id = order_ids[0]

    return order_id
