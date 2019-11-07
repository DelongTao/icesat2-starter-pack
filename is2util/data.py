import logging
from bisect import bisect
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
from pyproj import Geod

BEAMS = {f'gt{beam}{side}' for beam in range(1, 4) for side in ['l', 'r']}
EPOCH = datetime(2018, 1, 1, 0, 0, 0)
VARIABLES = {
    'ATL03': {
        'delta_time': 'heights/delta_time',
        'latitude': 'heights/lat_ph',
        'longitude': 'heights/lon_ph',
        'dist_ph_along': 'heights/dist_ph_along',
        'h_ph': 'heights/h_ph',
    },
    'ATL06': {
        'delta_time': 'land_ice_segments/delta_time',
        'latitude': 'land_ice_segments/latitude',
        'longitude': 'land_ice_segments/longitude',
        'h_li': 'land_ice_segments/h_li',
    },
    'ATL08': {
        'delta_time': 'land_segments/delta_time',
        'latitude': 'land_segments/latitude',
        'longitude': 'land_segments/longitude',
        'h_canopy': 'land_segments/canopy/h_canopy',
        'h_te_mean': 'land_segments/terrain/h_te_mean',
        'h_te_interp': 'land_segments/terrain/h_te_interp',
    },
}


def load_icesat2(filepath):
    '''
    Load points from an icesat-2 granule as DataFrame of points

    Arguments:
        filepath
    '''
    ds = h5py.File(filepath, 'r')
    dataproduct = ds.attrs['identifier_product_type'].decode()
    variables = VARIABLES[dataproduct]
    dfs = []
    for beam in BEAMS:
        data_dict = defaultdict(list)
        try:
            for variable in set(variables):
                data_dict[variable].extend(ds[beam][variables[variable]])
        except KeyError:
            logging.info(
                f'Variable {variable} not found in {filepath}. Likely an empty granule'
            )

        df = pd.DataFrame.from_dict(data_dict)
        df['beam'] = beam
        dfs.append(df)

    df = pd.concat(dfs, sort=True)

    for column in df.columns:
        if column == 'beam':
            continue
        df[column] = df[column].astype(np.float64)

    df['filename'] = Path(filepath).name
    df = df.reset_index(drop=True)

    return df


def delta_time_to_utc(df):
    '''
    Convert ICESat-2 'delta_time' parameter to UTC datetime
    '''
    df['utc_datetime'] = [EPOCH + timedelta(seconds=s) for s in df['delta_time']]

    df = df.drop(columns='delta_time')

    return df


def along_track_distance(df, ref_point=None):
    '''
    Calculate along track distance for each point, using 'ref_point' as reference.
    Assumes single homogeneous beam profile.

    Arguments:
        df: DataFrame with icesat-2 data
        ref_point: point to use as reference for distance (defaults to first point)

    Returuns:
        distance: series of calculated distances along track
    '''
    geod = Geod(ellps='WGS84')
    if ref_point is None:
        ref_point = df.iloc[0][['longitude', 'latitude']]

    def calc_distance(row):
        return geod.line_length(*zip(ref_point, row[['longitude', 'latitude']]))

    distance = df.apply(calc_distance, axis=1)

    return distance


def convert_to_gdf(df):
    '''
    Converts a DataFrame of points with 'longitude' and 'latitude' columns to a
    GeoDataFrame
    '''
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs={'init': 'epsg:4326'},
    )

    return gdf


def load_icesat2_directory(directory):
    dfs = []
    for filepath in Path(directory).glob('**/*ATL*h5'):
        dfs.append(load_icesat2(filepath))

    df = pd.concat(dfs, sort=True)
    df.reset_index(inplace=True)
    return df
