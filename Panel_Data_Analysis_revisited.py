#!/usr/bin/env python
# coding: utf-8

# In[19]:


import pandas as pd
import numpy as np
import statsmodels.api as sm
from linearmodels.panel import PanelOLS, RandomEffects
from scipy import stats


# In[ ]:


## Daily Panel Data Analysis


# In[35]:


daily_panel_data = pd.read_csv('D:/panel_daily_070824.csv')


# In[36]:


daily_panel_data.describe().round(3)


# In[37]:


daily_panel_data['t2m_f'] = (daily_panel_data['t2m_k'] - 273.15) * 9/5 + 32
daily_panel_data['tp'] = daily_panel_data['tp'].apply(lambda x: max(x, 0))
daily_panel_data['date'] = pd.to_datetime(daily_panel_data['date'])


# In[38]:


daily_panel_data.describe().round(3)


# In[32]:


print(daily_panel_data)


# In[39]:


duplicate_keys = daily_panel_data.groupby(['station_id', 'date']).filter(lambda x: len(x) > 1)

# Select distinct 'station_id' and 'date'
duplicate_keys = duplicate_keys[['station_id', 'date']].drop_duplicates()

# Join with the original data to get all columns for duplicate rows
duplicate_data = daily_panel_data.merge(duplicate_keys, on=['station_id', 'date'])

# Print all rows of duplicate data
print(duplicate_data)


# In[43]:


# Set the index for panel data (assuming 'date' and 'station_id' are indices)
daily_panel_data = daily_panel_data.set_index(['station_id', 'date'])


# In[45]:


FE_daily_freq = PanelOLS(daily_panel_data['freq'], daily_panel_data[['t2m_f', 'wind', 'tp']], entity_effects=True)

# Print the results summary
print(FE_daily_freq.fit())


# In[46]:


FE_daily_dur = PanelOLS(daily_panel_data['pct_blackout'], daily_panel_data[['t2m_f', 'wind', 'tp']], entity_effects=True)

# Print the results summary
print(FE_daily_dur.fit())


# In[50]:


## hourly panel data analysis


# In[67]:


hourly_panel_data = pd.read_csv('D:/panel_hourly_070824.csv')


# In[55]:


hourly_panel_data.describe().round(3)


# In[74]:


hourly_panel_data['t2m_f'] = (hourly_panel_data['t2m_k'] - 273.15) * 9/5 + 32
hourly_panel_data['tp'] = hourly_panel_data['tp'].apply(lambda x: max(x, 0))
hourly_panel_data['datetime'] = pd.to_datetime(hourly_panel_data['datetime'], format='%Y-%m-%d %H')


# In[89]:


# Set the index for panel data (assuming 'date' and 'station_id' are indices)
hourly_panel_data = hourly_panel_data.set_index(['station_id', 'datetime'])


# In[75]:


hourly_panel_data.describe().round(3)


# In[88]:


print(hourly_panel_data)


# In[81]:


hourly_panel_data.columns


# In[77]:


duplicate_hourly_keys = hourly_panel_data.groupby(['station_id', 'datetime']).filter(lambda x: len(x) > 1)

# Select distinct 'station_id' and 'date'
duplicate_hourly_keys = duplicate_hourly_keys[['station_id', 'datetime']].drop_duplicates()

# Join with the original data to get all columns for duplicate rows
duplicate_hourly_data = hourly_panel_data.merge(duplicate_hourly_keys, on=['station_id', 'datetime'])

# Print all rows of duplicate data
print(duplicate_hourly_data)


# In[91]:


dep = hourly_panel_data[['pct_blackout']]
indep= hourly_panel_data[['t2m_f', 'wind', 'tp']] 

FE_hourly_dur = PanelOLS(dep, indep, entity_effects=True)

# Print the results summary
print(FE_hourly_dur.fit())

