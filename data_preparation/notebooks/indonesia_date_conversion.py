import tqdm
import pandas as pd
import os
from datetime import datetime

# Preprocess data
indonesia_csv_dir = '../../01_data/esmi_raw/indonesia_csv/'

for csv in tqdm(os.listdir(indonesia_csv_dir)):
    df = pd.read_csv(indonesia_csv_dir+csv, index_col=0)
    df['datetime'] = df.apply(lambda row: datetime.strptime(row['date'] + str(str(row['hour']).rjust(2, "0")) + str(str(row['minute']-1).rjust(2, "0")), '%Y-%m-%d%H%M%S'), axis=1)
    
    # save to csv
    df[['datetime', 'voltage']].to_csv('../../01_data/esmi_processed/indonesia_esmi_voltage/' + csv)