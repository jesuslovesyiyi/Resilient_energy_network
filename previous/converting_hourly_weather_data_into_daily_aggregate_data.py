import os
import pandas as pd
import numpy as np

# Define the folder containing the hourly weather variables CSV files
folder_path = 'D:/ESMI_Dataset/EAR5_Data/raw_ESMI_boundary'

# Create a sub-folder called 'daily'
daily_folder = os.path.join(folder_path, 'daily')
os.makedirs(daily_folder, exist_ok=True)

# Get a list of all CSV files in the folder
files = [file for file in os.listdir(folder_path) if file.endswith('.csv')]

# Iterate through each CSV file
for file in files:
    # Read the CSV file into a DataFrame
    df = pd.read_csv(os.path.join(folder_path, file))
    
    # Convert 'datetime' column to datetime type
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Extract station information from the current CSV file
    station_info = df[['station_id', 'station_lat', 'station_lon']].iloc[0]
    
    # Aggregate daily average for 't2m', 'd2m', 'sp'
    daily_avg = df.groupby(df['datetime'].dt.date)[['t2m', 'd2m', 'sp']].mean()
    
    # Aggregate daily average of squared values for 'u10' and 'v10'
    df['u10_sq'] = df['u10'] ** 2
    df['v10_sq'] = df['v10'] ** 2
    daily_avg_squared = df.groupby(df['datetime'].dt.date)[['u10_sq', 'v10_sq']].mean()
    
    # Calculate daily average wind speed
    daily_avg['wind_speed'] = np.sqrt(daily_avg_squared['u10_sq'] + daily_avg_squared['v10_sq'])
    
    # Extract 'tp' value for 11:00 pm of each day
    df['hour'] = df['datetime'].dt.hour
    last_hour_tp = df[df['hour'] == 23].groupby(df['datetime'].dt.date)['tp'].last()
    
    # Merge daily average, wind speed, and last hour tp columns
    daily_data = daily_avg.join(last_hour_tp, rsuffix='_last_hour')
    
    # Add station information to daily data
    daily_data['station_id'] = station_info['station_id']
    daily_data['station_lat'] = station_info['station_lat']
    daily_data['station_lon'] = station_info['station_lon']
    daily_data.reset_index(inplace=True)
    
    # Reorder columns to have station information first
    cols = ['station_id', 'station_lat', 'station_lon', 'datetime', 't2m', 'd2m', 'sp', 'wind_speed', 'tp_last_hour']
    daily_data = daily_data[cols]
    daily_data.rename(columns={'datetime': 'date'}, inplace=True)
    
    # Save the aggregated daily weather variables to a new CSV file in the 'daily' sub-folder
    output_file = os.path.join(daily_folder, file.split('.')[0] + '_daily.csv')
    daily_data.to_csv(output_file, index=False)
    print(f"Daily aggregated data saved to: {output_file}")
