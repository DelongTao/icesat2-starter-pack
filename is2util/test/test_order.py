import geopandas as gpd

from is2util.order import (spatial_subset,
                           spatial_subset_from_url_params_async,
                           spatial_subset_from_url_params_sync)

test_region_file = (
    '/home/wallinb/projects/icesat2_tutorial/is2util/test/near_laselva.json'
)


def test_spatial_subset():
    gdf = gpd.read_file(test_region_file)

    result = spatial_subset(
        gdf.iloc[0].geometry, time_range=None, short_name='ATL08', version='001'
    )
    assert result


# def test_spatial_subset_from_url_params_async():
#     geometry = gpd.read_file(test_region_file).iloc[0].geometry


#     order_id = spatial_subset_from_url_params_async(
#         geometry,
#         time_range=None,
#         short_name='ATL06',
#         version='001',
#         email='bruce.wallin@colorado.edu',
#     )
#     assert order_id


# def test_spatial_subset_from_url_params_sync():
# geometry = gpd.read_file(test_region_file).iloc[0].geometry
# content = spatial_subset_from_url_params_sync(
#     geometry, time_range=None, short_name='ATL06', version='001'
# )
# assert content


# def test_spatial_subset_from_shapefile():
# pass
