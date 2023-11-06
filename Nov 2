import os
import netCDF4 as nc
import pandas as pd
import numpy as np
from netCDF4 import num2date
from datetime import datetime, timedelta

import os
import netCDF4 as nc
import pandas as pd
import numpy as np
from netCDF4 import num2date
from datetime import datetime, timedelta
# Open the NetCDF file for reading
nc_file = nc.Dataset('D:\ESMI_Dataset\ESMI_Data\IDN_EAST_EAR5_Land\IDN_EAST_EAR5_Land_NetCDF\IDN_EAST_2016_03.nc', 'r')

# Extract variables
u10 = nc_file.variables['u10']
file_dir = 'D:/ESMI_Dataset/ESMI_Data/IDN_EAST_EAR5_Land/IDN_EAST_EAR5_Land_NetCDF/'
for file in os.listdir(file_dir):
    nc_file = nc.Dataset(file_dir+file, 'r')
    break
file_dir+file

station_id = 111
station_lat = -10.17209
station_lon = 123.588203

# Open the NetCDF file for reading
file_dir = 'D:/ESMI_Dataset/ESMI_Data/IDN_EAST_EAR5_Land/IDN_EAST_EAR5_Land_NetCDF/'
output_dir = 'D:/ESMI_Dataset/ESMI_Data/IDN_EAST_EAR5_Land/output/'
for file in os.listdir(file_dir):
    nc_file = nc.Dataset(file_dir+file, 'r')
    
    if file[-3:] == '.nc':
        # Extract variable values at the station location
        year = file.split('_')[2]       # string format of year ####
        month = file.split('_')[-1][:-3] # string format of month ##

        # read station ID, latitude and longtitude from substation list
        
        # list of datetimes
        raw_time_array = np.array(nc_file['time'][:])
        datetime_lst = [datetime(1900, 1, 1, 0, 0, 0) + timedelta(hours = int(i)) for i in raw_time_array]

        longitude_raw = np.array(nc_file['longitude'][:])
        latitude_raw = np.array(nc_file['latitude'][:])

        long_pos = sum((station_lon>longitude_raw)*1)
        lat_pos = sum((station_lat>latitude_raw)*1)

        var_name_lst = [var_name for var_name, var in nc_file.variables.items()][3:]

        # Initiate an empty pandas df to store final results
        result_dic = {}

        result_dic['datetime'] = datetime_lst
        result_dic['station_lat'] = [station_lat]*len(datetime_lst)
        result_dic['station_lon'] = [station_lon]*len(datetime_lst)

        for var in var_name_lst:
            var_data = np.array(nc_file[var][:])
            var_values = []
            for i in range(len(datetime_lst)):
                data_matrix = var_data[i]
                upper_left_val = data_matrix[lat_pos, long_pos]
                upper_right_val = data_matrix[lat_pos, long_pos+1]
                lower_left_val = data_matrix[lat_pos+1, long_pos]
                lower_right_val = data_matrix[lat_pos+1, long_pos+1]

                ## Treating missing values: missing values are represented using -32767
                ## average value of upper_left_val, upper_right_val
                all_values = [upper_left_val, upper_right_val, lower_left_val, lower_right_val]
                boolean_vals = np.invert(np.array(all_values) == -32767)*1
                vals_avg = np.sum(np.multiply(np.array(all_values),boolean_vals))/boolean_vals.sum()

                var_values.append(vals_avg)

            result_dic[var] = var_values
        result_df = pd.DataFrame(result_dic)
        # Save as csv
        result_df.to_csv(output_dir+f'station_{station_id}_{year}_{month}.csv')
    else:
        continue
    break

output_dir+f'station_{station_id}_{year}_{month}.csv'

result_df.to_csv('../user/Desktop/test_station_march2016.csv')

result_df
