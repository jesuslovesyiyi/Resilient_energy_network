# Resilient energy network
This project seeks to build a better understanding of the impact of covective weather on energy network in India.

**Datasets**
- Voltage: [Electricity Supply Monitoring Initiative](https://watchyourpower.org/the_initiative.php) (ESMI)
- Weather: [ERA5-Land](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=overview)

**File organization**

Data preparation:  
- india_esmi_scraper.py: scrapes the ESMI website to get available data for currently online stations, resuming where the last scraping session had left off.  
Ignores data before January 1st, 2015, because that was when Prayas officially launched the ESMI program, and the available data quality before that is flawed.  
Outputs csv files in the format [id]+[location]+[district]+[state].csv  
The minute by minute datetimes are recorded in the default pandas export format yyyy-MM-dd HH:mm:ss.
- indonesia_date_conversion.py: converts dates in the indonesia dataset to the uniform date format used throughout this project

Previous:
- india_pkl2csv.py: [Deprecated] converted previous pkl output of the india scraper to the final csv format.