# Understanding the impact of weather conditions on energy infrastructure: a case study of India
This paper seeks to build a better understanding of the impact of covective weather on energy network in India.

**Datasets**
- Voltage: [Electricity Supply Monitoring Initiative](https://watchyourpower.org/the_initiative.php) (ESMI)

ESMI provides a database on supply interruptions and voltage levels at consumer locations in India. They installed Electricity Supply Monitors (ESM) in households, farms, and small commercial establishments all over India. The ESM is a plug-in device that integrates a voltage recorder. It provides voltage records by the minute at its location and sends data to a central server using Ground Penetrating Radar System (GPRS)

- Weather: [ERA5-Land](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=overview)

ERA5-Land is a reanalysis dataset providing a consistent view of the evolution of land variables over several decades at an enhanced resolution compared to ERA5. ERA5-Land has been produced by replaying the land component of the ECMWF ERA5 climate reanalysis. Reanalysis combines model data with observations from across the world into a globally complete and consistent dataset using the laws of physics. Reanalysis produces data that goes several decades back in time, providing an accurate description of the climate of the past.

**File organization**

Data preparation:  
- india_esmi_scraper.py: scrapes the ESMI website to get available data for currently online stations, resuming where the last scraping session had left off.  
Ignores data before January 1st, 2015, because that was when Prayas officially launched the ESMI program, and the available data quality before that is flawed.  
Outputs csv files in the format [id]+[location]+[district]+[state].csv  
The minute by minute datetimes are recorded in the default pandas export format yyyy-MM-dd HH:mm:ss.
- indonesia_date_conversion.py: converts dates in the indonesia dataset to the uniform date format used throughout this project

Previous:
- india_pkl2csv.py: [Deprecated] converted previous pkl output of the india scraper to the final csv format.