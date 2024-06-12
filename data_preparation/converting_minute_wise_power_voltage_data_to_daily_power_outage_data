import os
import pandas as pd
from tqdm import tqdm

# Path to the folder containing CSV files
folder_path = "C:/Users/user/Desktop/data_check/Original_Study_Stations/"

# Path to the folder where you want to save the result files
result_folder = "C:/Users/user/Desktop/data_check/only_0"

# Ensure the result folder exists, if not create it
os.makedirs(result_folder, exist_ok=True)  # Create folder only if it doesn't exist

# Get a list of CSV files in the folder
csv_files = [file_name for file_name in os.listdir(folder_path) if file_name.endswith('.csv')]

# Create a progress bar with tqdm
with tqdm(total=len(csv_files), desc="Processing CSV files") as pbar:
    for file_name in csv_files:
        # Read the CSV file into a DataFrame
        df = pd.read_csv(os.path.join(folder_path, file_name))

        # Filter rows where voltage column holds the value of 0
        df_filtered = df[df['voltage'] == 0]

        # Save the filtered DataFrame to a new CSV file
        result_file_name = os.path.splitext(file_name)[0] + "_only0.csv"
        result_file_path = os.path.join(result_folder, result_file_name)
        df_filtered.to_csv(result_file_path, index=False)

        # Update the progress bar
        pbar.update(1)


# Read the original CSV file
df = pd.read_csv("D:/ESMI_Dataset/Final_Data/power_output_analysis/India_all_stations_power_outage_data.csv")

# Convert the 'datetime' column to datetime objects
df['datetime'] = pd.to_datetime(df['datetime'])

# Sort the DataFrame by 'station_name' and 'datetime'
df = df.sort_values(by=['station_name', 'datetime'])

# Initialize an empty list to store the power outage events
power_outages = []

# Initialize variables to keep track of the current outage
current_station = None
current_start = None
current_end = None
current_duration = 0
current_rows = 0

# Create a tqdm progress bar
progress_bar = tqdm(total=len(df), desc="Processing data", unit="rows")

# Iterate through the DataFrame
for index, row in df.iterrows():
    progress_bar.update(1)  # Update progress bar
    if current_station is None:
        # Start a new outage event
        current_station = row['station_name']
        current_start = row['datetime']
        current_end = row['datetime']
        current_duration = 1
        current_rows = 1
    elif row['station_name'] == current_station and row['datetime'] == current_end + pd.Timedelta(minutes=1):
        # Continue current outage event
        current_end = row['datetime']
        current_duration += 1
        current_rows += 1
    else:
        # End current outage event and start a new one
        power_outages.append([current_station, current_duration, current_start, current_end, current_rows])
        current_station = row['station_name']
        current_start = row['datetime']
        current_end = row['datetime']
        current_duration = 1
        current_rows = 1

# Add the last outage event to the list
if current_station is not None:
    power_outages.append([current_station, current_duration, current_start, current_end, current_rows])

# Close the progress bar
progress_bar.close()

# Convert the list of outage events into a DataFrame
outages_df = pd.DataFrame(power_outages, columns=['station_name', 'duration', 'start', 'end', 'number_of_rows'])

# Write the DataFrame to a new CSV file
outages_df.to_csv("D:/ESMI_Dataset/Final_Data/power_output_analysis/power_outages.csv", index=False)
