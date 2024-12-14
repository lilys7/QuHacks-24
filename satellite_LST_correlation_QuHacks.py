import numpy as np # perform array operations 
import pandas as pd # data analysis
import matplotlib.pyplot as plt # make plots 
from netCDF4 import Dataset # read and write netcdf files
from cartopy import crs as ccrs # make maps
import matplotlib as mpl
from pyresample import geometry
from pyresample.kd_tree import resample_nearest
from osgeo import gdal 
import pyproj
import xarray as xr
import mpl_scatter_density # adds projection='scatter_density'
from matplotlib.colors import LinearSegmentedColormap
import math

date = sys.argv[1]
# VIIRS
# Open file
# first case:
# fname='LST_v1r4_npp_s202405250515532_e202405250517174_c202405250718010.nc'
fname='LST_v1r4_npp_s202404070657364_e202404070659006_c202404070857190.nc'
lst_file_id = Dataset(fname)

# Import variables
lst = lst_file_id.variables['VLST'][:,:]
lst_qf = lst_file_id.variables['VLST_Quality_Flag'][:,:] ## quality flag (not used) 

lst_dqf = lst_file_id.variables['DataQualityFlag'][:,:] ## data quality flag (not used) 
lst_offset = lst_file_id.variables['LST_Offset'] 
lst_sf = lst_file_id.variables['LST_ScaleFact'] ## scale factor
lst = (lst*lst_sf) + lst_offset
# Excluding fill values
missing = lst_file_id.variables['VLST']._FillValue
lst[lst == missing] = np.nan

# Select clear pixel data only
lst_hq = np.ma.masked_where(lst_qf & 4 == 4, lst) # bit 2
lst_hq = np.ma.masked_where(lst_qf & 8 == 8, lst_hq) # bit 3

# Latitude and longitude
lat = lst_file_id.variables['Latitude'][:,:]
lon = lst_file_id.variables['Longitude'][:,:]

# Input list of swath points
oldLonLat = geometry.SwathDefinition(lons=lon, lats=lat)

x = np.arange(67, 75, 0.009)
y = np.arange(69, 71, 0.009)
newLon, newLat = np.meshgrid(x, y)

# Define the new grid using
newLonLat = geometry.GridDefinition(lons=newLon, lats=newLat)

# Resample the data
newLST = resample_nearest(oldLonLat, lst_hq, newLonLat, radius_of_influence=5000, fill_value=None)

# Landsat
# Open the TIFF file
# first case:
# dataset = gdal.Open('LCO8_path_148_row_10_202405146_band_ST_B10.tif', gdal.GA_ReadOnly)
dataset = gdal.Open('LCO8_path_164_row_11_20240498_band_ST_B10.tif', gdal.GA_ReadOnly)

geotransform = dataset.GetGeoTransform()

if not dataset:
    print("Failed to open the dataset.")
else:
    # Get the number of bands
    num_bands = dataset.RasterCount
    print(f"Number of bands: {num_bands}")

    # Loop through each band and print information
    for i in range(1, num_bands + 1):
        band = dataset.GetRasterBand(i)
        
        # Get statistics (minimum, maximum, mean, standard deviation)
        stats = band.GetStatistics(True, True)
        
        # Read the band data as a NumPy array (if necessary)
        band_data = band.ReadAsArray()
        # print(f"Band data (first 100x100 elements):\n{band_data[:100, :100]}")

def pixel_to_coords(geotransform, shape, src_crs, tgt_crs):
     ulx, xres, xskew, uly, yskew, yres = geotransform
     rows, cols = shape

     x_idx, y_idx = np.meshgrid(np.arange(cols), np.arange(rows))
     lon0 = ulx + x_idx * xres + y_idx * xskew
     lat0 = uly + y_idx * yres + x_idx * yskew

     # Create a transformer object
     transformer = pyproj.Transformer.from_crs(src_crs, tgt_crs,
always_xy=True)

     # Transform coordinates
     lon, lat = transformer.transform(lon0.flatten(), lat0.flatten())

     lon = lon.reshape(shape)
     lat = lat.reshape(shape)

     return lon, lat

# get geoinfomation
geotransform = dataset.GetGeoTransform()
projection = dataset.GetProjection()

src_crs = pyproj.CRS.from_wkt(projection)
tgt_crs = pyproj.CRS.from_epsg(4326) 

s =  band_data.shape

lon, lat = pixel_to_coords(geotransform, s, src_crs, tgt_crs)

# Input list of swath points
oldLonLat = geometry.SwathDefinition(lons=lon, lats=lat)

# second case:
x = np.arange(67, 75, 0.009)
y = np.arange(69, 71, 0.009)
newLon, newLat = np.meshgrid(x, y)

# Define the new grid using
newLonLat = geometry.GridDefinition(lons=newLon, lats=newLat)

# Resample the data
new_band_data = resample_nearest(oldLonLat, band_data, newLonLat, radius_of_influence=5000, fill_value=None)

# Creating arrays for the scatter plot
where_both = np.where((newLST > 240) & (new_band_data > 240))

# scatt_viirs = arr_viirs[where_viirs]
scatt_viirs = newLST[where_both]
scatt_landsat = new_band_data[where_both]
scatt_diff = scatt_viirs - scatt_landsat

where_diff = np.where((scatt_diff < 100) & (scatt_diff > -100))
scatt_diff_2 = scatt_diff[where_diff]
scatt_viirs_2 = scatt_viirs[where_diff]
scatt_landsat_2 = scatt_landsat[where_diff]

print(f"Shape of x: {(scatt_viirs_2.shape)}")
print(f"Shape of y: {(scatt_landsat_2.shape)}")
print(f"Shape of scatt_diff_2: {(scatt_diff_2.shape)}")
print(f"VIIRS data (first 100 elements):\n{scatt_viirs_2[:100]}")
print(f"Landsat data (first 100 elements):\n{scatt_landsat_2[:100]}")
print(f"scatt_diff_2:\n{scatt_diff_2[:100]}")

print("Mean difference:", np.mean(scatt_diff_2))
print("Standard deviation difference:", np.std(scatt_diff_2))
print("Correlation coefficient:", np.corrcoef(scatt_viirs_2, scatt_landsat_2))
mean_diff = np.round(np.mean(scatt_diff_2), 3)
stdev_diff = np.round(np.std(scatt_diff_2), 3)
corrceof_both = np.round(np.corrcoef(scatt_viirs_2, scatt_landsat_2), 3)
# Pearson correlation coefficient
MSE = np.square(np.subtract(scatt_viirs_2, scatt_landsat_2)).mean()
rmse = np.round(math.sqrt(MSE), 3)
print("Root Mean Square Error:", rmse)
# MSE_2 = np.square(scatt_diff_2).mean()
# rmse_2 = math.sqrt(MSE_2)
# print("Root Mean Square Error(2):", rmse_2)

# add title, 1=1 line, mean difference, sample size, stdev
# use density plot

# "Viridis-like" colormap with white background
white_viridis = LinearSegmentedColormap.from_list('white_viridis', [
    (0, '#ffffff'),
    (1e-20, '#440053'),
    (0.2, '#404388'),
    (0.4, '#2a788e'),
    (0.6, '#21a784'),
    (0.8, '#78d151'),
    (1, '#fde624'),
], N=256)

def using_mpl_scatter_density(fig, x, y):
    ax = fig.add_subplot(1, 1, 1, projection='scatter_density')
    density = ax.scatter_density(x, y, cmap=white_viridis)
    fig.colorbar(density, label='Number of matchups')
    plt.xlabel("VIIRS LST data")
    plt.ylabel("Landsat LST data")
    # first case:
    # second case: 
    ax.set_xlim(250, 265)
    ax.set_ylim(250, 265)

fig = plt.figure()
using_mpl_scatter_density(fig, scatt_viirs_2, scatt_landsat_2)
myMax = max(max(scatt_viirs_2), max(scatt_landsat_2))
plt.plot([0, myMax], [0, myMax])
# plt.text(251,279, 'Statistics: '+'\nN: '+str((scatt_diff_2.shape[0]))+'\nR: '+str(corrceof_both[0,1]) +'\nBias: '+str(mean_diff*-1)+'\nStdev: '+str(stdev_diff)+"\nRMSE: "+str(rmse), ha='left', va='top', color='black')
plt.text(251,264, 'Statistics: '+'\nN: '+str((scatt_diff_2.shape[0]))+'\nR: '+str(corrceof_both[0,1]) +'\nBias: '+str(mean_diff*-1)+'\nStdev: '+str(stdev_diff)+"\nRMSE: "+str(rmse), ha='left', va='top', color='black')
plt.title(f"Comparison of VIIRS and Landsat LST on {date}")
plt.savefig(f"combined_scatter_density_{date}.png")
plt.show()
