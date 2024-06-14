import os
import pandas as pd
import numpy as np
from netCDF4 import Dataset
from datetime import datetime, timedelta

# Define paths and lists
file_dir = 'D:/ESMI_Dataset/ESMI_Data/IDN_WEST_EAR5_Land/IDN_WEST_EAR5_Land_NetCDF/'
output_dir = 'D:/ESMI_Dataset/ESMI_Data/IDN_WEST_EAR5_Land/output/'
station_data_file = "D:/ESMI_Dataset/ESMI_Data/IDN_WEST_EAR5_Land/ESMI_Location_IDN_WEST.csv"

# Read station information
station_info_df = pd.read_csv(station_data_file)

# Iterate over each station
for index, station_row in station_info_df.iterrows():
    station_id = station_row['Id']
    station_lat = station_row['latitude']
    station_lon = station_row['longtitude']
    
    # Initialize a list to store data for the current station
    all_data = []

    for file in os.listdir(file_dir):
        nc_file_path = os.path.join(file_dir, file)
    
        if file.endswith('.nc'):
            try:
                with Dataset(nc_file_path, 'r') as nc_file:  # Open the NetCDF file for reading
                    # Extract variable values at the station location
                    year = file.split('_')[2]       # string format of year ####
                    month = file.split('_')[-1][:-3] # string format of month ##
            
                    # list of datetimes
                    raw_time_array = np.array(nc_file['time'][:])
                    datetime_lst = [datetime(1900, 1, 1, 0, 0, 0) + timedelta(hours=int(i)) for i in raw_time_array]

                    # Extract hourly climate data at the specified location
                    lat_idx = np.abs(nc_file['latitude'][:] - station_lat).argmin()
                    lon_idx = np.abs(nc_file['longitude'][:] - station_lon).argmin()

                    data = {
                        'station_id': [station_id] * len(datetime_lst),
                        'station_lat': [station_lat] * len(datetime_lst),
                        'station_lon': [station_lon] * len(datetime_lst),
                        'datetime': datetime_lst,
                        't2m': nc_file.variables['t2m'][:, lat_idx, lon_idx].tolist(),
                        'u10': nc_file.variables['u10'][:, lat_idx, lon_idx].tolist(),
                        'v10': nc_file.variables['v10'][:, lat_idx, lon_idx].tolist(),
                        'd2m': nc_file.variables['d2m'][:, lat_idx, lon_idx].tolist(),
                        'ro': nc_file.variables['ro'][:, lat_idx, lon_idx].tolist(),
                        'skt': nc_file.variables['skt'][:, lat_idx, lon_idx].tolist(),
                        'snowc': nc_file.variables['snowc'][:, lat_idx, lon_idx].tolist(),
                        'rsn': nc_file.variables['rsn'][:, lat_idx, lon_idx].tolist(),
                        'sde': nc_file.variables['sde'][:, lat_idx, lon_idx].tolist(),
                        'sf': nc_file.variables['sf'][:, lat_idx, lon_idx].tolist(),
                        'smlt': nc_file.variables['smlt'][:, lat_idx, lon_idx].tolist(),
                        'ssro': nc_file.variables['ssro'][:, lat_idx, lon_idx].tolist(),
                        'sp': nc_file.variables['sp'][:, lat_idx, lon_idx].tolist(),
                        'sro': nc_file.variables['sro'][:, lat_idx, lon_idx].tolist(),
                        'e': nc_file.variables['e'][:, lat_idx, lon_idx].tolist(),
                        'tp': nc_file.variables['tp'][:, lat_idx, lon_idx].tolist(),
                    }

                    all_data.append(pd.DataFrame(data))

                print(f"Processed data for station {station_id} in {year}-{month}")
                
            except Exception as e:
                print(f"Error processing data for station {station_id} in {year}-{month}: {str(e)}")

    # Concatenate data for the current station and save to a CSV file
    if all_data:
        station_data_df = pd.concat(all_data, ignore_index=True)
        output_file = os.path.join(output_dir, f'station_{station_id}_data.csv')
        station_data_df.to_csv(output_file, index=False)

print('Done')
