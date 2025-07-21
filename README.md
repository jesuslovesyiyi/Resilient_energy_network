# Lights Out: India’s Power Struggles Amid Rising Weather Extremes
This paper seeks to build a better understanding of the impact of covective weather on energy network in India.
## Authors:
Yiyi He, Georgia Tech<br>
Jun Rentschler, The World Bank<br>

## Research gap
Power grid is typically designed to provide a stable and continuous energy supply over long periods, as frequent disruptions—such as blackouts or brownouts—can have costly and far-reaching consequences. However, this stability is premised on design assumptions based on historically stable operating conditions.What has been studied extensively is the impact of extreme weather events on the power grid . However, not all power outages can be attributed to these extreme events. Daily and seasonal variations in weather conditions also contribute significantly to grid disruptions. While *acute* shocks to infrastructure systems—often intensified by a changing climate—have been the focus of much of the existing literature, the *chronic* and cumulative effects of gradual weather changes remain insufficiently examined.


## Datasets used in this work
### Voltage data: [Electricity Supply Monitoring Initiative](https://watchyourpower.org/the_initiative.php) (ESMI)

ESMI provides a database on supply interruptions and voltage levels at consumer locations in India. They installed Electricity Supply Monitors (ESM) in households, farms, and small commercial establishments all over India. The ESM is a plug-in device that integrates a voltage recorder. It provides voltage records by the minute at its location and sends data to a central server using Ground Penetrating Radar System (GPRS).

### Weather: [ERA5-Land](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=overview)

ERA5-Land is a reanalysis dataset providing a consistent view of the evolution of land variables over several decades at an enhanced resolution compared to ERA5. ERA5-Land has been produced by replaying the land component of the ECMWF ERA5 climate reanalysis. Reanalysis combines model data with observations from across the world into a globally complete and consistent dataset using the laws of physics. Reanalysis produces data that goes several decades back in time, providing an accurate description of the climate of the past.

### Project Dataset Repository - OneDrive Access




**File organization**

Data preparation: 
01_

Previous:
- india_esmi_scraper.py: scrapes the ESMI website to get available data for currently online stations, resuming where the last scraping session had left off.  
Ignores data before January 1st, 2015, because that was when Prayas officially launched the ESMI program, and the available data quality before that is flawed.  
Outputs csv files in the format [id]+[location]+[district]+[state].csv  
The minute by minute datetimes are recorded in the default pandas export format yyyy-MM-dd HH:mm:ss.
- indonesia_date_conversion.py: converts dates in the indonesia dataset to the uniform date format used throughout this project- india_pkl2csv.py: [Deprecated] converted previous pkl output of the india scraper to the final csv format.