import os
import tqdm
import pickle
import pandas as pd
from datetime import datetime

# Directory where the raw .pk files are stored
india_pk_dir = 'C:/Users/user/India_new/'
# Directory to save the processed csv files
india_esmi_voltage_ts_dir = 'C:/Users/user/India_esmi/'

# Record locations (list of location ids) that have been processed already
loc_visited_lst = []
for file in os.listdir(india_esmi_voltage_ts_dir):
    loc_visited_lst.append(int(file[:3]))

for item in tqdm(os.listdir(india_pk_dir)):
    if item[-3:] == 'pkl':
        if int(item[:3]) in loc_visited_lst:
            continue
        else:
            # Load raw pickle files
            file = pickle.load(open(india_pk_dir + item, 'rb'))
            raw_df = pd.DataFrame(file)

            # Extract name of the monitoring station: state, district, and location
            full_name = pd.DataFrame(file)['name'].unique()[0]
            # State
            state_name = full_name.split(' - ')[1].split(', ')[0]
            # District
            district_name = full_name.split(' - ')[1].split(', ')[1]
            # Location
            location_name = full_name.split(' - ')[1].split(', ')[-1][:-1]

            # check '/' in names
            if '/' in state_name:
                state_name = state_name.replace("/", "_")
            if '/' in district_name:
                district_name = district_name.replace("/", "_")
            if '/' in location_name:
                location_name = location_name.replace("/", "_")

            # Extract datetime and voltage data
            df = raw_df[['timeseries']]
            df['datetime'] = df.apply(lambda row: datetime.strptime(row['timeseries']['date'], '%a %b %d %Y %H:%M:%S'), axis=1)
            df['voltage'] = df.apply(lambda row: row['timeseries']['voltage'], axis=1)

            # Save to csv file
            df[['datetime', 'voltage']].to_csv(india_esmi_voltage_ts_dir+f'{int(item[:-4])}_{state_name}_{district_name}_{location_name}.csv')

    else:
        continue