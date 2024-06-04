import os
from datetime import datetime
from datetime import time, tzinfo, timedelta
import urllib
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import requests
import pandas as pd
from tqdm import tqdm
import re
import pickle

def date2query(date):
    return urllib.parse.quote(date.strftime('%d/%m/%Y'), safe='')


def retry_request(url, session, total=4, status_forcelist=[429, 500, 502, 503, 504], **kwargs):
    # Make number of requests required
    for _ in range(total):
        try:
            response = session.get(url, **kwargs)
            if response.status_code in status_forcelist:
                # Retry request 
                continue
            return response
        except requests.exceptions.ConnectionError:
            pass
    return None


session = requests.Session()
LOGIN_URL = 'http://www.watchyourpower.org/admin/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
}

# Retrieve and display login captcha
page_text = retry_request(url=LOGIN_URL, session=session, headers=HEADERS)
img_url = 'http://www.watchyourpower.org/captcha.php'
img_data = retry_request(url=img_url, session=session, headers=HEADERS).content

with open('./captcha.jpg','wb') as fp:
    fp.write(img_data)

image = mpimg.imread("./captcha.jpg")
plt.imshow(image)
plt.show()
img_code = input('Enter captcha：')

USERNAME ='junrentschler'
PASSWORD ='jun@2018'
data = {'username': USERNAME,
        'password': PASSWORD,
        'code': img_code,
        'login': 'Login'}

# Sign into watch your power session
index = session.post(url=LOGIN_URL, headers=HEADERS, data=data)
print(index)

DETAIL_URL = 'http://www.watchyourpower.org/reports.php?category_id=3&location_id=119&from_date=13%2F01%2F2017&to_date=13%2F02%2F2017'
detail_text = retry_request(url=DETAIL_URL, session=session, headers=HEADERS).text

if detail_text.find('Welcome') == -1:
    exit()

# Output directory, india_esmi by default, change as needed
INDIA_SCRAPE_DIR = f'india_esmi'

# Pull up the dashboard page and retrieve all available monitoring station ids
# Because nothing is specified, the rightmost dropdown "Location" will have all the monitoring stations available
API_URL = f'http://www.watchyourpower.org/reports.php?'
print(API_URL)

res = retry_request(url=API_URL, session=session, headers=HEADERS)
if res.ok:
    text = res.text

    # Isolate the section of the html that contains the monitoring station dropdown
    text_list = text.split('<option value="">-- Select  --</option>')[1].split('</select>')[0]
    text_list = re.split('<option class="" | >', text_list)
    stationIDs = [elem[6:].replace('\"', '').replace(' ', '+') for elem in text_list if elem.startswith("value=")]
    print(f'Stations: {stationIDs}, {len(stationIDs)} stations total')

    # If the output directory already exists, check the log to see the ids and last scraped dates for all of the stations
    last_scraped = {}
    today_string = datetime.now().strftime('%m/%d/%Y')

    # Ensure the output directory exists for the latest run of the scraper and retrieve last scraped dates
    # to avoid repeat work
    if os.path.exists(INDIA_SCRAPE_DIR):
        if os.path.exists(f'{INDIA_SCRAPE_DIR}/log.txt'):
            with open(f'{INDIA_SCRAPE_DIR}/log.txt', 'r') as f:
                print('Previous scraping log found:')
                print(f'Last read: {f.readline().split(':')[1]}')

                for line in f:
                    _, id, date = f.readline().split(',')
                    last_scraped[id] = date.strptime('%m/%d/%Y')
    else:
        os.makedirs(INDIA_SCRAPE_DIR)
                
    for id in stationIDs:
        # Query just the location with no dates to pull up the error text which informs us of the available data dates
        url = f'http://www.watchyourpower.org/reports.php?location_id={id}'
        res = retry_request(url=url, session=session, headers=HEADERS)

        range_start = None
        range_end = None
        title = ""

        if res:
            empty_chart_match = re.search(r'<span class="empty_chart">([\S\s]*?)<\/span>', res.text)
            if empty_chart_match:
                empty_chart_content = empty_chart_match.group(1)
                range_start = datetime.strptime(empty_chart_content.split('From ')[1].split(' To ')[0].strip(), '%d/%m/%Y')
                range_end = datetime.strptime(empty_chart_content.split(' To ')[1].strip(), '%d/%m/%Y')
        else:
            print(f'Failed to retrieve data for station {id}')
            continue

        query_start = range_start
        query_end = query_start + timedelta(days=31)

        # Loop through the available data period in 31 day intervals
        result = []
        while query_end <= range_end and query_start < query_end:
            url = f'http://www.watchyourpower.org/reports.php?location_id={id}&from_date={date2query(query_start)}&to_date={date2query(query_end)}'

            res = retry_request(url=url, session=session, headers=HEADERS)

            if res:
                text = res.text
                title = text.split('<title>')[1].split('for')[0]

                print(title)
                print(f'Scraping {query_start.strftime('%m/%d/%Y')} to {query_end.strftime('%m/%d/%Y')} for station {id}')

                text_list = text.split('\n')
                for elem in text_list:
                    if elem.startswith("\t\tvar linechartData"):
                        voltage_list = elem[24:-3].split('},{')
                        for volt in tqdm(voltage_list):
                            result.append(eval("{" + volt.replace('null', '\"null\"') + "}"))
            
            query_start = query_end + timedelta(days=1)
            query_end = query_start + timedelta(days=31)

            if query_end > range_end:
                query_end = range_end

        print(len(result))

        if os.path.exists(f'{INDIA_SCRAPE_DIR}/{id}.pkl'):
            continue

        # Update last scraped
        last_scraped[id] = range_end

        save = {'name': title, 'timeseries': result}
        with open(f'{INDIA_SCRAPE_DIR}/{id}.pkl', 'wb') as f:
            pickle.dump(save, f)
    
    # Update the log file
    with open(f'{INDIA_SCRAPE_DIR}/log.txt', 'w') as f:
        f.write(f'Last Scraped:{today_string}\n')
        for id, date in last_scraped.items():
            f.write(f'{title},{id},{date.strftime('%m/%d/%Y')}\n')

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
