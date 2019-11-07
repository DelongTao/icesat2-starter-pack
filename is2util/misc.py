import os
import zipfile
from itertools import islice
from pathlib import Path
from tempfile import TemporaryDirectory

import fiona
import geopandas as gpd
import h5py
import pandas as pd
from shapely.geometry import Point, mapping


def geometry_to_shapefile(geometry, crs, filepath):
    '''
    Write a shapely geometry object to a shapefle
    '''
    shp_filepath = Path(filepath).with_suffix('.shp')
    schema = {'geometry': 'Polygon', 'properties': {'id': 'int'}}

    with fiona.open(
        shp_filepath, mode='w', driver='ESRI Shapefile', schema=schema, crs=crs
    ) as c:
        c.write({'geometry': mapping(geometry), 'properties': {'id': 123}})


def geometry_to_zipped_shapefile(geometry, crs, filepath):
    '''
    Write a shapely geometry object to a zipped shapefle
    '''
    with TemporaryDirectory() as d:
        shp_filepath = Path(d) / 'tmp.shp'
        geometry_to_shapefile(geometry, crs, shp_filepath)
        filepaths = list(shp_filepath.parent.glob(shp_filepath.stem + '.*'))
        zip_files(filepath, filepaths)


def zip_files(zip_filepath, filepaths):
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as z:
        for filepath in filepaths:
            z.write(filepath, filepath.name)
            os.remove(filepath)

    return zip_filepath
