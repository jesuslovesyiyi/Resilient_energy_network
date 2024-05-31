import csv
import numpy as np
import sys
from bs4 import BeautifulSoup
from lxml import etree
import os
from datetime import datetime
from datetime import time, tzinfo, timedelta
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import requests

import pandas as pd
from tqdm import tqdm
import re
import pickle

session = requests.Session()
login_url = 'http://www.watchyourpower.org/admin/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
}

page_text = session.get(url=login_url,headers=headers)
img_url = 'http://www.watchyourpower.org/captcha.php'
img_data = session.get(url=img_url,headers=headers).content
with open('./Code.jpg','wb') as fp:
    fp.write(img_data)
image = mpimg.imread("./Code.jpg")
plt.imshow(image)
plt.show()
img_code = input('Enter code：')
username ='junrentschler'
password ='jun@2018'
data ={   'username': username,    'password': password, 'code':img_code, 'login': 'Login'}
print(data)
index = session.post(url=login_url, headers=headers, data=data)
print(index)
detial_url = 'http://www.watchyourpower.org/reports.php?category_id=3&location_id=119&from_date=13%2F01%2F2017&to_date=13%2F02%2F2017'
detial_text = session.get(url=detial_url,headers=headers).text
print(detial_text.find('Welcome'))
if detial_text.find('Welcome') == -1:
    exit()

url_lists = []
month_2dight={1:"01", 2:"02",3:"03",4:"04",5:"05", 6:"06",7:"07", 8:"08",9:"09",10:"10",11:"11", 12:"12"}

for c in [2, 3, 4, 5]:
    api_url = f'http://www.watchyourpower.org/reports.php?category_id={c}'
    print(api_url)
    res = session.get(url=api_url, headers=headers)
    if res.ok:
        text = res.text
        text_list = text.split('<option value="">-- Select  --</option>')[1].split('</select>')[0]
        text_list = re.split('<option class="" | >', text_list)
        text_list2 = [elem[6:].replace('\"', '').replace(' ', '+') for elem in text_list if elem.startswith("value=")]
        print(c, text_list2)

        for id in text_list2:
            if os.path.exists(f'India_new/{id}.pkl'):
                continue

            # Ensure the 'India_new' directory exists
            if not os.path.exists('India_new'):
                os.makedirs('India_new')

            result = []
            for year in range(2004, 2024):
                for month in range(1, 13):
                    next_month = 1 if month == 12 else month + 1
                    next_year = year + 1 if month == 12 else year
                    url = f'http://www.watchyourpower.org/reports.php?category_id={c}&location_id={id}&from_date=13%2F{month_2dight[month]}%2F{year}&to_date=13%2F{month_2dight[next_month]}%2F{next_year}'
                    print(url)

                    try:
                        res = session.get(url=url, headers=headers, timeout=5)
                    except requests.Timeout:
                        # back off and retry
                        pass
                    except requests.ConnectionError:
                        pass

                    if res.ok:
                        print('ok', year, month)
                        text = res.text
                        title = text.split('<title>')[1].split('for')[0]
                        print(title)
                        text_list = text.split('\n')
                        for elem in text_list:
                            if elem.startswith("\t\tvar linechartData"):
                                voltage_list = elem[24:-3].split('},{')
                                for volt in tqdm(voltage_list):
                                    result.append(eval("{" + volt.replace('null', '\"null\"') + "}"))

            print(len(result))
            save = {'name': title, 'timeseris': result}
            with open(f'India_new/{id}.pkl', 'wb') as f:
                pickle.dump(save, f)

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
            state_name = state_name.replace("/", "_")
            if '/' in district_name:
                district_name = district_name.replace("/", "_")
            if '/' in location_name:
                location_name = location_name.replace("/", "_")

            # Extract datetime and voltage data
            df = raw_df[['timeseris']]
            df['datetime'] = df.apply(lambda row: datetime.strptime(row['timeseris']['date'], '%a %b %d %Y %H:%M:%S'), axis=1)
            df['voltage'] = df.apply(lambda row: row['timeseris']['voltage'], axis=1)

            # Save to csv file
            df[['datetime', 'voltage']].to_csv(india_esmi_voltage_ts_dir+f'{int(item[:-4])}_{state_name}_{district_name}_{location_name}.csv')

    else:
        continue
