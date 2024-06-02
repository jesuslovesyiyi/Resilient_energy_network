#######################################################################################################################
###################### Panel Data Analysis: Power Outage Frequency/Duration v. Weather variables ######################
#######################################################################################################################

#######################################################################################################################
############################################# PART 0. Pre-task. Library Setup #########################################
#######################################################################################################################

# Package Installation
install.packages("jtools")
install.packages("GGally")
install.packages("stargazer")
install.packages("lmtest")
install.packages("car")
install.packages("sandwich")
install.packages("fastDummies") 
install.packages("broom.mixed") 
install.packages("plm")
install.packages("margins")
install.packages("magrittr")
install.packages("urca")
install.packages("maps")

# Load R packages
library(plm)
library(dplyr)
library(tidyverse)
library(jtools)
library(GGally)
library(stargazer)
library(car)
library(lmtest)
library(sandwich)
library(fastDummies)
library(broom.mixed)
library(margins)
library(tidyverse)
library(stargazer)
library(sjPlot)
library(tseries)
library(urca)
library(maps)

#######################################################################################################################
############################################# Part 1. Data Cleaning ###################################################
#######################################################################################################################

power <- read.csv("D:/ESMI_Dataset/Final_Data/Panel_Data/panel_data_240406.csv")

# Set the directory containing the CSV files
csv_folder <- "D:/ESMI_Dataset/Final_Data/Panel_Data/daily_weather"

# Get the list of CSV files in the folder
csv_files <- list.files(csv_folder, pattern = "\\.csv$", full.names = TRUE)

# Initialize an empty list to store the data frames
data_frames <- list()

# Loop through each CSV file, read it, and store it in the list
for (file in csv_files) {
  data <- read.csv(file)
  data_frames[[length(data_frames) + 1]] <- data
}

# Merge all data frames in the list into a single data frame
merged_data <- do.call(rbind, data_frames)

# Optionally, write the merged data frame to a new CSV file
write.csv(merged_data, "D:/ESMI_Dataset/Final_Data/Panel_Data/daily_weather/new/new.csv", row.names = FALSE)

# Load the dplyr package
library(dplyr)

# Read CSV files A and B

# Merge files A and B on station_id and date
merged_df <- inner_join(power, merged_data, by = c("station_id", "date"))

merged_df

# Subset all columns except specified ones
subset_df <- merged_df[, !(names(merged_df) %in% c("station_lat.y", "station_lon.y", "t2m.y", "tp.y", "wind_speed", "Distance_10km_Y_N", "Distance_km", "outage_d_ave_dur"))]

summary(subset_df)
# Print the subsetted data frame
print(subset_df)

# Assuming your data frame is named df

# Rename columns
names(subset_df)[names(subset_df) == "station_lon.x"] <- "station_lon"
names(subset_df)[names(subset_df) == "station_lat.x"] <- "station_lat"
names(subset_df)[names(subset_df) == "t2m.x"] <- "t2m"
names(subset_df)[names(subset_df) == "tp.x"] <- "tp"

# Print the updated column names
print(names(subset_df))



# Save the merged DataFrame to a new CSV file
write.csv(subset_df, "panel_data_240417.csv", row.names = FALSE)

print("Merged data saved to: merged_file.csv")


view(dfready)
dfready <- read.csv("D:/ESMI_Dataset/Final_Data/Panel_Data/panel_data_240419_test_rh_heat_index.csv")

summary(dfready)

# Panel data declaration
panel_data <- pdata.frame(dfready, index = c("station_id", "date"))
head(panel_data)
summary(panel_data)



dfready <- dfready %>%
  mutate(whether_outage = ifelse(outage_d_gro_freq == 0, 0, 1))

# Assuming dfready is your data frame
dfready <- dfready %>%
  mutate(outage_d_ave_dur = ifelse(outage_d_gro_freq == 0, 0, outage_d_gro_dur / outage_d_gro_freq))

write.csv(dfready, file = "output_file_240405.csv", row.names = FALSE)


# Create histogram
ggplot(dfready, aes(x = outage_d_gro_freq)) +
  geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
  labs(title = "Distribution of Power Outage Frequency",
       x = "Power Outage Frequency (Nos.)",
       y = "Frequency") +
  theme_minimal() +
  xlim(0, 500)


# Create summary table
summary_table <- dfready %>%
  group_by(Frequency_Category) %>%
  summarise(Count = n())

# Add a row for total count
summary_table <- bind_rows(summary_table, data.frame(Frequency_Category = "Total", Count = sum(summary_table$Count)))

# Print summary table
print(summary_table)

dfready <- dfready %>%
  mutate(
    Duration_Category = case_when(
      outage_d_gro_dur == 0 ~ "0",
      between(outage_d_gro_dur, 1, 14.999) ~ "[1,15)",
      between(outage_d_gro_dur, 15, 59.999) ~ "[15, 60)",
      between(outage_d_gro_dur, 60, 179.999) ~ "[60, 180)",
      outage_d_gro_dur >= 180 ~ "180 or more"
    )
  )

# Create summary table
summary_table_2 <- dfready %>%
  group_by(Duration_Category) %>%
  summarise(Count = n())

# Add a row for total count
summary_table_2 <- bind_rows(summary_table_2, data.frame(Duration_Category = "Total", Count = sum(summary_table_2$Count)))

# Print summary table
print(summary_table_2)

# Create histogram
ggplot(dfready, aes(x = outage_d_gro_dur)) +
  geom_histogram(binwidth = 15, fill = "skyblue", color = "black") +
  labs(title = "Distribution of Power Outage Duration",
       x = "Power Outage Duration (minutes)",
       y = "Frequency") +
  theme_minimal() +
  xlim(0, 1440) +
  ylim(0, 50000)

view(panel_data)

dfready <- dfready %>%
  mutate(
    t2m_category = case_when(
      between(t2m, -15, -0.00000001) ~ "[-15, 0]",
      between(t2m, 0, 14.99999999) ~ "[0, 15)",
      between(t2m, 15, 24.9999999) ~ "[15, 25)",
      between(t2m, 25, 29.9999999) ~ "[25, 30)",
      between(t2m, 30, 34.9999999) ~ "[30, 35)",
      between(t2m, 35, 39.9999999) ~ "[35, 40)",
    )
  )

# Create summary table
summary_table_3 <- dfready %>%
  group_by(t2m_category) %>%
  summarise(Count = n())

# Add a row for total count
summary_table_3 <- bind_rows(summary_table_3, data.frame(t2m_category = "Total", Count = sum(summary_table_3$Count)))

# Print summary table
print(summary_table_3)

# Create histogram
ggplot(dfready, aes(x = t2m)) +
  geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
  labs(title = "distribution of daily 2m temperature",
       x = "daily 2m temperature (celsius)",
       y = "Frequency") +
  theme_minimal()

dfready <- dfready %>%
  mutate(
    wind_category = case_when(
      between(wind, 0, 2.9999999999) ~ "[0, 3)",
      between(wind, 3, 6.9999999999) ~ "[3, 7)",
      between(wind, 7, 12) ~ "[7, 12)",
    )
  )

# Create summary table
summary_table_4 <- dfready %>%
  group_by(wind_category) %>%
  summarise(Count = n())

# Add a row for total count
summary_table_4 <- bind_rows(summary_table_4, data.frame(wind_category = "Total", Count = sum(summary_table_4$Count)))

# Print summary table
print(summary_table_4)

# Create histogram
ggplot(dfready, aes(x = wind)) +
  geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
  labs(title = "distribution of daily wind speed",
       x = "daily wind speed (m/s))",
       y = "Frequency") +
  theme_minimal()

summary(panel_data)

dfready$tp[dfready$tp < 0] <- 0

panel_data$tp[panel_data$tp < 0] <- 0
summary(dfready)

write.csv(dfready, file = "panel_data_240404.csv", row.names = FALSE)

summary(panel_data)

dfready <- dfready %>%
  mutate(
    tp_category = case_when(
      tp == 0 ~ "No Rain",
      between(tp, 0.000000000000000001, 4.999999999999999999999999999) ~ "Light Rain (0, 5)",
      between(tp, 5, 19.99999999999999999999999) ~ "Moderate Rain [5, 20)",
      between(tp, 20, 49.999999999999999999999999) ~ "Heavy Rain [20, 50)",
      between(tp, 50, 99.99999999999999999999999) ~ "Violent Rain: 1 [50,100)",
      tp >= 100 ~ "Violent Rain: 2(100 or more)"
    )
  )

# Create summary table
summary_table_5 <- dfready %>%
  group_by(tp_category) %>%
  summarise(Count = n())

# Add a row for total count
summary_table_5 <- bind_rows(summary_table_5, data.frame(tp_category = "Total", Count = sum(summary_table_5$Count)))

# Print summary table
print(summary_table_5)

# Filter out the "Total" category
summary_table_plot <- summary_table_5 %>%
  filter(tp_category != "Total")

# Create a bar plot
ggplot(summary_table_plot, aes(x = factor(tp_category, levels = category_order), y = Count)) +
  geom_bar(stat = "identity", fill = "skyblue") +
  geom_text(aes(label = Count), vjust = -0.5, color = "black", size = 3) +  # Add count labels above the bars
  labs(x = "Precipitation Category", y = "Count", title = "Summary of Precipitation Categories") +
  theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1, lineheight = 0.5)) +  # Adjust x-axis text appearance
  scale_y_continuous(labels = scales::comma)  # Ensures that numbers on the y-axis are properly formatted

library(ggplot2)

ggplot(dfready, aes(x = tp)) +
  geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
  labs(title = "distribution of daily total precipitation",
       x = "Daily Total Precipitation (mm)",
       y = "Frequency") +
  theme_minimal()


panel_data <- panel_data %>%
  mutate(tp10mm = tp / 10,
         windsquare = wind^2)

summary(panel_data)

summary(dfready)


# Assuming your data frame is named combined_data and you want to count values in the 'date' column
count_result <- dfready %>% 
  count(whether_outage)

summary(panel_data)
summary(dfready)
count_result

# pair-wise visual inspection
ggpairs(dfready[, c("outage_d_gro_freq", "outage_d_gro_dur", "t2m", "tp", "wind_speed", "RH")])


ggpairs(dfready[, c("outage_freq", "outage_dur", "t2m_c", "tp", "wind", "rh", "heat_index")])

####################################### OPTIONAL INSPECTION ########################################

## Panel Data inspection
th_300 <- panel_data[panel_data$tp > 300, ]
th_500 <- panel_data[panel_data$tp > 500, ]
th_1000 <- panel_data[panel_data$tp > 1000, ]
th_2000 <- panel_data[panel_data$tp > 2000, ]

nrow(th_300)
nrow(th_500)
nrow(th_1000)
nrow(th_2000)
above_threshold

master_file <- read.csv("D:/ESMI_Dataset/Final_Data/ESMI_India_538_locations_final_climate_zone.csv")
ab_th_data <- merge(above_threshold, master_file, by = "station_id", all.x = TRUE)
ab_th_data

ab_th_data_1 <- ab_th_data[, c("station_id", "date", "tp", "Lat", "Lon")]
ab_th_data_1


lat_lon_data <- ab_th_data_1[, c("Lat", "Lon")]

south_asia_map_data <- map_data("world") %>% 
  filter(region %in% c("India","Bangladesh", "Nepal", "Bhutan", "Sri Lanka"))

# Create a new variable for tp ranges
ab_th_data_1$tp_range <- cut(ab_th_data_1$tp, breaks = seq(0, max(ab_th_data_1$tp), by = 500), include.lowest = TRUE)

# Plot latitude and longitude points on a map of South Asia with colored points based on tp ranges
ggplot() +
  geom_polygon(data = south_asia_map_data, aes(x = long, y = lat, group = group), fill = "lightgray", color = "black") +
  geom_point(data = ab_th_data_1, aes(x = Lon, y = Lat, color = tp_range), size = 1.2) +
  labs(x = "Longitude", y = "Latitude", title = "Location on Map of South Asia", color = "TP Range") +
  scale_color_brewer(name = "TP Range", palette = "Set1")  # Adjust color palette as needed

review_data <- merge(panel_data, master_file, by = "station_id", all.x = TRUE)

lat_lon_review_data <- review_data[, c("Lat", "Lon")]

south_asia_map_data <- map_data("world") %>% 
  filter(region %in% c("India","Bangladesh", "Nepal", "Bhutan", "Sri Lanka"))

head(review_data)

summary(daily_a)
# Create a new variable for tp ranges
lat_long_review_data$daily_average_duration_of_event <- cut(ab_th_data_1$tp, breaks = seq(0, max(ab_th_data_1$tp), by = 500), include.lowest = TRUE)

# Plot latitude and longitude points on a map of South Asia with colored points based on tp ranges
ggplot() +
  geom_polygon(data = south_asia_map_data, aes(x = long, y = lat, group = group), fill = "lightgray", color = "black") +
  geom_point(data = ab_th_data_1, aes(x = Lon, y = Lat, color = tp_range), size = 1.2) +
  labs(x = "Longitude", y = "Latitude", title = "Location on Map of South Asia", color = "TP Range") +
  scale_color_brewer(name = "TP Range", palette = "Set1")  # Adjust color palette as needed

summary(dfready)

#######################################################################################################################
############################################# Part 2. Data Inspection #################################################
#######################################################################################################################

#data inspection & diagnostics required?
head(panel_data)

# Assuming your data frame is named df

temperature_ranges <- c(-Inf, 0, 15, 25, 30, 35, 40)

# Create the dummy variable for temperature ranges
panel_data$dummy_temp <- cut(panel_data$t2m, breaks = temperature_ranges, labels = c("-15_to_0", "0_to_15", "15_to_25", "25_to_30", "30_to_35", "35_to_40"), include.lowest = TRUE)

# Print the first few rows of the data frame to verify the changes
summary(panel_data)

 
# non-normality: ADF test
for (col in names(panel_data)) {
  adf_result <- adf.test(panel_data[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_result)
}

# vector autoregressive model
install.packages("vars")
library(vars)

summary(panel_data)

# Estimate VAR model with different lag orders
lag_orders <- 1:10  # Example lag orders to test
aic_values <- numeric(length(lag_orders))

for (i in 1:length(lag_orders)) {
  # Estimate VAR model
  var_model <- VAR(panel_data, p = lag_orders[i], type = "const")
  
  # Compute AIC
  aic_values[i] <- AIC(var_model)
}

# Find lag order with minimum AIC
optimal_lag <- lag_orders[which.min(aic_values)]

# Print optimal lag order and corresponding AIC value
print(paste("Optimal lag order:", optimal_lag))
print(paste("AIC value:", min(aic_values)))


# Compute impulse response function
irf_results <- irf(var_model, n.ahead = num_periods)


#######################################################################################################################
############################################# Part 3. Logistics Regression ############################################
#######################################################################################################################

head(panel_data)

##### Logit regression
logit_reg <- glm(whether_outage ~ t2m + wind + tp, data = panel_data, family = binomial)

##### Print the summary of the model with coefficients rounded to 4 decimal points
summary_logit_reg <- summary(logit_reg)
summary_logit_reg$coefficients <- round(summary_logit_reg$coefficients, 4)
print(summary_logit_reg)

##### logit regression 2

logit_reg_2 <- glm(whether_outage ~ t2m + windsquare + tp10mm, data = panel_data_2, family = binomial)
summary_logit_reg_2 <- summary(logit_reg_2)
summary_logit_reg_2$coefficients <- round(summary_logit_reg_2$coefficients, 4)
print(summary_logit_reg_2)

##### Logit regression 3
logit_reg_3 <- glm(whether_outage ~ t2m:e + wind + tp, data = panel_data, family = binomial)

##### Print the summary of the model with coefficients rounded to 4 decimal points
summary_logit_reg_3 <- summary(logit_reg_3)
summary_logit_reg_3$coefficients <- round(summary_logit_reg_3$coefficients, 4)
print(summary_logit_reg_3)

logit_reg_4 <- glm(whether_outage ~ t2m:e + windsquare + tp10mm, data = panel_data_2, family = binomial)
summary_logit_reg_4 <- summary(logit_reg_4)
summary_logit_reg_4$coefficients <- round(summary_logit_reg_4$coefficients, 4)
print(summary_logit_reg_4)
#######################################################################################################################
##################################################### Part 4. AME #####################################################
#######################################################################################################################

AME <- margins(logit_reg)
summary(AME)

AME_2 <- margins(logit_reg_2)
summary(AME_2)

AME_3 <- margins(logit_reg_3)
summary(AME_3)

AME_4 <- margins(logit_reg_4)
summary(AME_4)



#######################################################################################################################
################################################ Part 5. Panel Data Analysis ##########################################
#######################################################################################################################

#######################################################################################################################
## 5.1. Pooled OLS ####################################################################################################
#######################################################################################################################

head(panel_data)

pooled_ols_model_1_gro_freq <- lm(outage_d_gro_freq ~ t2m + wind + tp, data = panel_data)
summary(pooled_ols_model_1_gro_freq)

pooled_ols_model_1_gro_dur <- lm(outage_d_gro_dur ~ t2m + wind + tp, data = panel_data)
summary(pooled_ols_model_1_gro_dur)

pooled_ols_model_1_ave_dur <- lm(outage_d_ave_dur ~ t2m + wind + tp, data = panel_data)
summary(pooled_ols_model_1_ave_dur)

###################

pooled_ols_model_2_gro_freq <- lm(outage_d_gro_freq ~ t2m:e + wind + tp, data = panel_data)
summary(pooled_ols_model_2_gro_freq)

pooled_ols_model_2_gro_dur <- lm(outage_d_gro_dur ~ t2m:e + wind + tp, data = panel_data)
summary(pooled_ols_model_2_gro_dur)

pooled_ols_model_2_ave_dur <- lm(outage_d_ave_dur ~ t2m:e + wind + tp, data = panel_data)
summary(pooled_ols_model_2_ave_dur)

###################

summary(panel_data_2)

pooled_ols_model_3_gro_freq <- lm(outage_d_gro_freq ~ t2m + windsquare + tp10mm, data = panel_data_2)
summary(pooled_ols_model_3_gro_freq)

pooled_ols_model_3_gro_dur <- lm(outage_d_gro_dur ~ t2m + windsquare + tp10mm, data = panel_data_2)
summary(pooled_ols_model_3_gro_dur)

pooled_ols_model_3_ave_dur <- lm(outage_d_ave_dur ~ t2m + windsquare + tp10mm, data = panel_data_2)
summary(pooled_ols_model_3_ave_dur)

###################

pooled_ols_model_4_gro_freq <- lm(outage_d_gro_freq ~ t2m:e + windsquare + tp10mm, data = panel_data_2)
summary(pooled_ols_model_4_gro_freq)

pooled_ols_model_4_gro_dur <- lm(outage_d_gro_dur ~ t2m:e + windsquare + tp10mm, data = panel_data_2)
summary(pooled_ols_model_4_gro_dur)

pooled_ols_model_4_ave_dur <- lm(outage_d_ave_dur ~ t2m:e + windsquare + tp10mm, data = panel_data_2)
summary(pooled_ols_model_4_ave_dur)

#######################################################################################################################
## 5.2. Panel Data Analysis - Daily Gross Frequency ##################################################################
#######################################################################################################################      

# Run the fixed effects panel data analysis

fe_model_1_1 <- plm(outage_freq ~ t2m + wind + tp,
                  data = panel_data,
                  model = "twoways",
                  index = c("station_id", "date")

summary(panel_data)

fe_model_1_heat_index <- plm(outage_freq ~ heat_index + wind + tp,
                             data = panel_data,
                             model = "within",
                             index = c("station_id", "date")
)
                    
summary(fe_model_1_heat_index)
                    
# Define temperature ranges
temperature_ranges <- c(-15, -14, 0, 15, 25, 30, 35, 40)

# Create dummy variable for temperature
panel_data$dummy_temp <- cut(panel_data$t2m, breaks = temperature_ranges, labels = c("negative_15_to_negative_14", "negative_14_to_0", "0_to_15", "15_to_25", "25_to_30", "30_to_35", "35_to_40"), include.lowest = TRUE)

fe_model_1_1_dummy <- plm(outage_freq ~ t2m + wind + tp + dummy_temp,
                          data = panel_data,
                          model = "within",
                          index = c("station_id", "date"))

summary(fe_model_1_1_dummy)                

summary(panel_data)

# Create dummy variable for tp

tp_ranges <- c(0, 0.1, 5, 20, 50, 255)
panel_data$dummy_tp <- cut(panel_data$tp, breaks = tp_ranges, labels = c("negative", "Light_rain(0-5)", "Moderate_rain(5-20)", "Heavy_rain(20-50)", "Violent_rain(50>)"), include.lowest = TRUE)

fe_model_1_1_dummy_tp <- plm(outage_freq ~ t2m + wind + tp + dummy_tp,
                          data = panel_data,
                          model = "within",
                          index = c("station_id", "date"))


wind_ranges <- c(0, 0.2, 3, 7, 12)
panel_data$dummy_w <- cut(panel_data$wind, breaks = wind_ranges, labels = c("0", "Light_air(0-3)", "Light_breeze(3-7)", "Gentle_breeze(7-12)"), include.lowest = TRUE)

fe_model_1_1_dummy_w <- plm(outage_freq ~ t2m + wind + tp + dummy_w,
                            data = panel_data,
                            model = "within",
                            index = c("station_id", "date"))

summary(fe_model_1_1_dummy_w)



summary_fe_1_1 <- summary(fe_model_1_1)


pFtest(fe_model_1_1, pooled_ols_model_1_gro_freq)

#################################

# Run the random effects panel data analysis

re_model_1_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp,
                  data = panel_data,
                  model = "random")

summary(re_model_1_1)

# Perform the Hausman test
hausman_test_1_1 <- phtest(fe_model_1_1, re_model_1_1)

# Print the Hausman test results
print(hausman_test_1_1)

##################

fe_model_1_2 <- plm(outage_dur ~ t2m + wind + tp,
                    data = panel_data,
                    model = "within")

summary_fe_1_2 <- summary(fe_model_1_2)

fe_model_1_2_heat_index <- plm(outage_dur ~ heat_index + wind + tp,
                               data = panel_data,
                               model = "within")

summary(fe_model_1_2_heat_index)

summary_fe_1_2 <- summary(fe_model_1_2)

summary_fe_1_2$coefficients <- round(summary_fe_1_2$coefficients, 4)

print(summary_fe_1_2)

fe_model_1_2_dummy <- plm(outage_dur ~ t2m + wind + tp + dummy_temp,
                      data = panel_data,
                      model = "within")

summary(fe_model_1_2_dummy)

fe_model_1_2_dummy_tp <- plm(outage_dur ~ t2m + wind + tp + dummy_tp,
                          data = panel_data,
                          model = "within")

summary(fe_model_1_2_dummy_tp)

fe_model_1_2_dummy_w <- plm(outage_dur ~ t2m + wind + tp + dummy_w,
                            data = panel_data,
                            model = "within",
                            index = c("station_id", "date"))

summary(fe_model_1_2_dummy_w)

summary_fe_1_2 <- summary(fe_model_1_2)

# Run the random effects panel data analysis

re_model_1_2 <- plm(outage_d_gro_dur ~ t2m + wind + tp,
                    data = panel_data,
                    model = "random")

summary(re_model_1_2)

# Perform the Hausman test
hausman_test_1_2 <- phtest(fe_model_1_2, re_model_1_2)

# Print the Hausman test results
print(hausman_test_1_2)

##################

fe_model_1_3 <- plm(outage_d_ave_dur ~ t2m + wind + tp,
                    data = panel_data,
                    model = "within")

summary_fe_1_3 <- summary(fe_model_1_3)

summary_fe_1_3$coefficients <- round(summary_fe_1_3$coefficients, 4)

print(summary_fe_1_3)

# Run the random effects panel data analysis

re_model_1_3 <- plm(outage_d_ave_dur ~ t2m + wind + tp,
                    data = panel_data,
                    model = "random")

summary(re_model_1_3)

# Perform the Hausman test
hausman_test_1_3 <- phtest(fe_model_1_3, re_model_1_3)

# Print the Hausman test results
print(hausman_test_1_3)

#######################################################################################################################
## 5.3. Panel Data Analysis - original model + interaction ############################################################
#######################################################################################################################

# Run the fixed effects panel data analysis

fe_model_2_1 <- plm(outage_freq ~ t2m:e + wind + tp,
                    data = panel_data,
                    model = "within")

summary_fe_2_1 <- summary(fe_model_2_1)

summary_fe_2_1$coefficients <- round(summary_fe_2_1$coefficients, 4)

print(summary_fe_2_1)

# Run the random effects panel data analysis

re_model_2_1 <- plm(outage_d_gro_freq ~ t2m:e + wind + tp,
                    data = panel_data,
                    model = "random")

summary(re_model_2_1)

# Perform the Hausman test
hausman_test_2_1 <- phtest(fe_model_2_1, re_model_2_1)

# Print the Hausman test results
print(hausman_test_2_1)

##################

summary(panel_data)

fe_model_2_2 <- plm(outage_d_gro_dur ~ t2m:e + wind + tp,
                    data = panel_data,
                    model = "within")

summary_fe_2_2 <- summary(fe_model_2_2)

summary_fe_2_2$coefficients <- round(summary_fe_2_2$coefficients, 4)

print(summary_fe_2_2)

# Run the random effects panel data analysis

re_model_2_2 <- plm(outage_d_gro_dur ~ t2m:e + wind + tp,
                    data = panel_data,
                    model = "random")

summary(re_model_2_2)

# Perform the Hausman test
hausman_test_2_2 <- phtest(fe_model_2_2, re_model_2_2)

# Print the Hausman test results
print(hausman_test_2_2)

##################

fe_model_2_3 <- plm(outage_d_ave_dur ~ t2m:e + wind + tp,
                    data = panel_data,
                    model = "within")

summary_fe_2_3 <- summary(fe_model_2_3)

summary_fe_2_3$coefficients <- round(summary_fe_2_3$coefficients, 4)

print(summary_fe_2_3)

# Run the random effects panel data analysis

re_model_2_3 <- plm(outage_d_ave_dur ~ t2m:e + wind + tp,
                    data = panel_data,
                    model = "random")

summary(re_model_2_3)

# Perform the Hausman test
hausman_test_2_3 <- phtest(fe_model_2_3, re_model_2_3)

# Print the Hausman test results
print(hausman_test_2_3)

#######################################################################################################################
## 5.4. Panel Data Analysis - model 2 #################################################################################
#######################################################################################################################

# Run the fixed effects panel data analysis

summary(panel_data_2)

fe_model_3_1 <- plm(outage_d_gro_freq ~ t2m + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "within")

summary_fe_3_1 <- summary(fe_model_3_1)

summary_fe_3_1$coefficients <- round(summary_fe_3_1$coefficients, 4)

print(summary_fe_3_1)

# Run the random effects panel data analysis

re_model_3_1 <- plm(outage_d_gro_freq ~ t2m + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "random")

summary(re_model_3_1)

# Perform the Hausman test
hausman_test_3_1 <- phtest(fe_model_3_1, re_model_3_1)

# Print the Hausman test results
print(hausman_test_3_1)

##################

fe_model_3_2 <- plm(outage_d_gro_dur ~ t2m + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "within")

summary_fe_3_2 <- summary(fe_model_3_2)

summary_fe_3_2$coefficients <- round(summary_fe_3_2$coefficients, 4)

print(summary_fe_3_2)

# Run the random effects panel data analysis

re_model_3_2 <- plm(outage_d_gro_dur ~ t2m + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "random")

summary(re_model_3_2)

# Perform the Hausman test
hausman_test_3_2 <- phtest(fe_model_3_2, re_model_3_2)

# Print the Hausman test results
print(hausman_test_3_2)

##################

fe_model_3_3 <- plm(outage_d_ave_dur ~ t2m + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "within")

summary_fe_3_3 <- summary(fe_model_3_3)

summary_fe_3_3$coefficients <- round(summary_fe_3_3$coefficients, 4)

print(summary_fe_3_3)

# Run the random effects panel data analysis

re_model_3_3 <- plm(outage_d_ave_dur ~ t2m + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "random")

summary(re_model_3_3)

# Perform the Hausman test
hausman_test_3_3 <- phtest(fe_model_3_3, re_model_3_3)

# Print the Hausman test results
print(hausman_test_3_3)

#######################################################################################################################
## 5.4. Panel Data Analysis - model 2 + interaction ###################################################################
#######################################################################################################################

# Run the fixed effects panel data analysis

summary(panel_data_2)

fe_model_4_1 <- plm(outage_d_gro_freq ~ t2m:e + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "within")

summary_fe_4_1 <- summary(fe_model_4_1)

summary_fe_4_1$coefficients <- round(summary_fe_4_1$coefficients, 4)

print(summary_fe_4_1)

# Run the random effects panel data analysis

re_model_4_1 <- plm(outage_d_gro_freq ~ t2m:e + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "random")

summary(re_model_4_1)

# Perform the Hausman test
hausman_test_4_1 <- phtest(fe_model_4_1, re_model_4_1)

# Print the Hausman test results
print(hausman_test_4_1)

##################

fe_model_4_2 <- plm(outage_d_gro_dur ~ t2m:e + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "within")

summary_fe_4_2 <- summary(fe_model_4_2)

summary_fe_4_2$coefficients <- round(summary_fe_4_2$coefficients, 4)

print(summary_fe_4_2)

# Run the random effects panel data analysis

re_model_4_2 <- plm(outage_d_gro_dur ~ t2m:e + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "random")

summary(re_model_4_2)

# Perform the Hausman test
hausman_test_4_2 <- phtest(fe_model_4_2, re_model_4_2)

# Print the Hausman test results
print(hausman_test_4_2)

##################

fe_model_4_3 <- plm(outage_d_ave_dur ~ t2m:e + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "within")

summary_fe_4_3 <- summary(fe_model_4_3)

summary_fe_4_3$coefficients <- round(summary_fe_4_3$coefficients, 4)

print(summary_fe_4_3)

# Run the random effects panel data analysis

re_model_4_3 <- plm(outage_d_ave_dur ~ t2m:e + windsquare + tp10mm,
                    data = panel_data_2,
                    model = "random")

summary(re_model_4_3)

# Perform the Hausman test
hausman_test_4_3 <- phtest(fe_model_4_3, re_model_4_3)

# Print the Hausman test results
print(hausman_test_4_3)


#######################################################################################################################
## 5.3. Breusch-Pagan Test ############################################################################################
####################################################################################################################### 

# Perform the Breusch-Pagan test
bp_test_pols1 <- bptest(pooled_ols_model_1)
print(bp_test_pols1)

bp_test_pols2 <- bptest(pooled_ols_model_2)
print(bp_test_pols2)

bp_test_fe1 <- bptest(fe_model_1)
print(bp_test_fe1)

bp_test_fe2 <- bptest(fe_model_2)
print(bp_test_fe2)







#######################################################################################################################
########################################### Part 6. Climate-zone wise analysis ########################################
#######################################################################################################################

panel_data_Am <- subset(panel_data, gridcode == "Am")
panel_data_Aw <- subset(panel_data, gridcode == "Aw")
panel_data_BSh <- subset(panel_data, gridcode == "BSh")
panel_data_Cwa <- subset(panel_data, gridcode == "Cwa")
panel_data_Cwb <- subset(panel_data, gridcode == "Cwb")
panel_data_Dwb <- subset(panel_data, gridcode == "Dwb")

# Install and load required packages
install.packages("kableExtra")
library(kableExtra)

# Load the openxlsx package
library(openxlsx)

summary(panel_data_Am)
count_result <- panel_data_Am %>% 
  count(whether_outage)

count_result

summary(panel_data_Aw)

count_result <- panel_data_Aw %>% 
  count(whether_outage)

count_result

summary(panel_data_BSh)

count_result <- panel_data_BSh %>% 
  count(whether_outage)

count_result

summary(panel_data_Cwa)

count_result <- panel_data_Cwa %>% 
  count(whether_outage)

count_result

summary(panel_data_Cwb)
summary(panel_data_Dwb)

summary_Am <- summary(panel_data_Am)
summary_Aw <- summary(panel_data_Aw)
summary_BSh <- summary(panel_data_BSh)
summary_Cwa <- summary(panel_data_Cwa)
summary_Cwb <- summary(panel_data_Cwb)
summary_Dwb <- summary(panel_data_Dwb)

# Define the file path and name for the Excel file
excel_file <- "summary.xlsx"

# Write the summary statistics to an Excel file
write.xlsx(summary_Dwb, file = excel_file)

# Message to confirm the export
cat("Summary statistics exported to", excel_file, "\n")




nrow(panel_data_Am)
nrow(panel_data_Aw)
nrow(panel_data_BSh)
nrow(panel_data_Cwa)
nrow(panel_data_Cwb)
nrow(panel_data_Dwb)
nrow(panel_data)

# Assuming 'panel_data' is your pdata.frame containing panel data
for (col in names(panel_data_Am)) {
  adf_Am_result <- adf.test(panel_data_Am[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_Am_result)
}

for (col in names(panel_data_Aw)) {
  adf_Aw_result <- adf.test(panel_data_Aw[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_Aw_result)
}

for (col in names(panel_data_BSh)) {
  adf_BSh_result <- adf.test(panel_data_BSh[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_BSh_result)
}

for (col in names(panel_data_Cwa)) {
  adf_Cwa_result <- adf.test(panel_data_Cwa[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_Cwa_result)
}

###############################

##### Logit regression
logit_reg_Am <- glm(whether_outage ~ t2m + wind + tp + e + ro, data = panel_data_Am, family = binomial)
summary_logit_reg_Am <- summary(logit_reg_Am)
summary_logit_reg_Am$coefficients <- round(summary_logit_reg_Am$coefficients, 4)
print(summary_logit_reg_Am)

logit_reg_Aw <- glm(whether_outage ~ t2m + wind + tp + e + ro, data = panel_data_Aw, family = binomial)
summary_logit_reg_Aw <- summary(logit_reg_Aw)
summary_logit_reg_Aw$coefficients <- round(summary_logit_reg_Aw$coefficients, 4)
print(summary_logit_reg_Aw)

logit_reg_BSh <- glm(whether_outage ~ t2m + wind + tp + e + ro, data = panel_data_BSh, family = binomial)
summary_logit_reg_BSh <- summary(logit_reg_BSh)
summary_logit_reg_BSh$coefficients <- round(summary_logit_reg_BSh$coefficients, 4)
print(summary_logit_reg_BSh)

logit_reg_Cwa <- glm(whether_outage ~ t2m + wind + tp + e + ro, data = panel_data_Cwa, family = binomial)
summary_logit_reg_Cwa <- summary(logit_reg_Cwa)
summary_logit_reg_Cwa$coefficients <- round(summary_logit_reg_Cwa$coefficients, 4)
print(summary_logit_reg_Cwa)

##### AME 

AME_Am <- margins(logit_reg_Am)
summary(AME_Am)

AME_Aw <- margins(logit_reg_Aw)
summary(AME_Aw)

AME_BSh <- margins(logit_reg_BSh)
summary(AME_BSh)

AME_Cwa <- margins(logit_reg_Cwa)
summary(AME_Cwa)

###############################
bp_test_pols1_Am <- bptest(pols_1_Am)
print(bp_test_pols1_Am)

bp_test_pols1_Aw <- bptest(pols_1_Aw)
print(bp_test_pols1_Aw)

bp_test_pols1_BSh <- bptest(pols_1_BSh)
print(bp_test_pols1_BSh)

bp_test_pols1_Cwa <- bptest(pols_1_Cwa)
print(bp_test_pols1_Cwa)

bp_test_pols2_Am <- bptest(pols_2_Am)
print(bp_test_pols2_Am)

bp_test_pols2_Aw <- bptest(pols_2_Aw)
print(bp_test_pols2_Aw)

bp_test_pols2_BSh <- bptest(pols_2_BSh)
print(bp_test_pols2_BSh)

bp_test_pols2_Cwa <- bptest(pols_2_Cwa)
print(bp_test_pols2_Cwa)

######

bp_test_fe_Am_1 <- bptest(fe_model_Am_1)
print(bp_test_fe_Am_1)

bp_test_fe_Aw_1 <- bptest(fe_model_Aw_1)
print(bp_test_fe_Aw_1)

bp_test_fe_BSh_1 <- bptest(fe_model_BSh_1)
print(bp_test_fe_BSh_1)

bp_test_fe_Cwa_1 <- bptest(fe_model_Cwa_1)
print(bp_test_fe_Cwa_1)

bp_test_fe_Am_2 <- bptest(fe_model_Am_2)
print(bp_test_fe_Am_2)

bp_test_fe_Aw_2 <- bptest(fe_model_Aw_2)
print(bp_test_fe_Aw_2)

bp_test_fe_BSh_2 <- bptest(fe_model_BSh_2)
print(bp_test_fe_BSh_2)

bp_test_fe_Cwa_2 <- bptest(fe_model_Cwa_2)
print(bp_test_fe_Cwa_2)

####

bp_test_re_Am_1 <- bptest(re_model_Am_1)
print(bp_test_re_Am_1)

bp_test_re_Aw_1 <- bptest(re_model_Aw_1)
print(bp_test_re_Aw_1)

bp_test_re_BSh_1 <- bptest(re_model_BSh_1)
print(bp_test_re_BSh_1)

bp_test_re_Cwa_1 <- bptest(re_model_Cwa_1)
print(bp_test_re_Cwa_1)

bp_test_re_Am_2 <- bptest(re_model_Am_2)
print(bp_test_re_Am_2)

bp_test_re_Aw_2 <- bptest(re_model_Aw_2)
print(bp_test_re_Aw_2)

bp_test_re_BSh_2 <- bptest(re_model_BSh_2)
print(bp_test_re_BSh_2)

bp_test_re_Cwa_2 <- bptest(re_model_Cwa_2)
print(bp_test_re_Cwa_2)

#######################################################################################################################
## 6.1. Pooled OLS for each group #####################################################################################
####################################################################################################################### 
head(panel_data)

pols_1_Am <- lm(outage_d_gro_freq ~ t2m + wind + tp + e + ro, data = panel_data_Am)
pols_1_Aw <- lm(outage_d_gro_freq ~ t2m + wind + tp + e + ro, data = panel_data_Aw)
pols_1_BSh <- lm(outage_d_gro_freq ~ t2m + wind + tp + e + ro, data = panel_data_BSh)
pols_1_Cwa <- lm(outage_d_gro_freq ~ t2m + wind + tp + e + ro, data = panel_data_Cwa)

library(openxlsx)

summary_pols_1_Am <- summary(pols_1_Am)
summary_pols_1_Aw <- summary(pols_1_Aw)
summary_pols_1_BSh <- summary(pols_1_BSh)
summary_pols_1_CWa <- summary(pols_1_Cwa)

summary_pols_1_Am
summary_pols_1_Aw
summary_pols_1_BSh
summary_pols_1_CWa

# Tidy the regression output
tidy_pols_1_Am <- tidy(pols_1_Am)
tidy_pols_1_Aw <- tidy(pols_1_Aw)
tidy_pols_1_BSh <- tidy(pols_1_BSh)
tidy_pols_1_Cwa <- tidy(pols_1_Cwa)

write.xlsx(tidy_pols_1_Am, "Am_results.xlsx")
write.xlsx(tidy_pols_1_Aw, "Aw_results.xlsx")
write.xlsx(tidy_pols_1_BSh, "BSh_results.xlsx")
write.xlsx(tidy_pols_1_Cwa, "Cwa_results.xlsx")

excel_file_2 <- "summary2.xlsx"
write.xlsx(summary_pols_1_Am, file = excel_file_2)

pols_1_climate_zone

pols_1_climate_zone_1 <- update(pols_1_climate_zone, coefs = list(digits = 4))

# Display the updated table

pols_2_Am <- lm(outage_d_ave_dur ~ t2m + wind + tp + e + ro, data = panel_data_Am)
pols_2_Aw <- lm(outage_d_ave_dur ~ t2m + wind + tp + e + ro, data = panel_data_Aw)
pols_2_BSh <- lm(outage_d_ave_dur ~ t2m + wind + tp + e + ro, data = panel_data_BSh)
pols_2_Cwa <- lm(outage_d_ave_dur ~ t2m + wind + tp + e + ro, data = panel_data_Cwa)

summary_pols_2_Am <- summary(pols_2_Am)
summary_pols_2_Aw <- summary(pols_2_Aw)
summary_pols_2_BSh <- summary(pols_2_BSh)
summary_pols_2_CWa <- summary(pols_2_Cwa)


summary_pols_2_Am
summary_pols_2_Aw
summary_pols_2_BSh
summary_pols_2_CWa

# Tidy the regression output
tidy_pols_2_Am <- tidy(pols_2_Am)
tidy_pols_2_Aw <- tidy(pols_2_Aw)
tidy_pols_2_BSh <- tidy(pols_2_BSh)
tidy_pols_2_Cwa <- tidy(pols_2_Cwa)

write.xlsx(tidy_pols_2_Am, "2Am_results.xlsx")
write.xlsx(tidy_pols_2_Aw, "2Aw_results.xlsx")
write.xlsx(tidy_pols_2_BSh, "2BSh_results.xlsx")
write.xlsx(tidy_pols_2_Cwa, "2Cwa_results.xlsx")

tab_model(pols_2_Am, pols_2_Aw, pols_2_BSh, pols_2_Cwa, # You can compare multiple models in one table as well.
          show.ci = 0.95, # alpha-level for confidence interval
          show.se = TRUE, # Whether to show standard errors of coefficient estimates
          show.stat = TRUE, # Whether to show t value for coefficient estimates
          dv.labels = c("Am Group: Daily Average Duration", "Aw Group: Daily Average Duration", "BSh Group: Daily Average Duration", "Cwa Group: Daily Average Duration"))

#######################################################################################################################
## 6.1. Panel Data Analysis - Gross Frequency for each group ##########################################################
####################################################################################################################### 

## Daily Gross Frequency - FE, RE #####################################################################################

## Am - FE

fe_model_Am_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                  data = panel_data_Am,
                  model = "within")

summary(fe_model_Am_1)

## Am - RE

re_model_Am_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                  data = panel_data_Am,
                  model = "random")

summary(re_model_Am_1)

## Aw - FE

fe_model_Aw_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                     data = panel_data_Aw,
                     model = "within")

summary(fe_model_Aw_1)

## Aw - RE

re_model_Aw_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                     data = panel_data_Aw,
                     model = "random")

summary(re_model_Aw_1)

## BSh - FE

fe_model_BSh_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                      data = panel_data_BSh,
                      model = "within")

summary(fe_model_BSh_1)

## BSh - RE

re_model_BSh_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                      data = panel_data_BSh,
                      model = "random")

summary(re_model_BSh_1)

## Cwa - FE

fe_model_Cwa_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                      data = panel_data_Cwa,
                      model = "within")

summary(fe_model_Cwa_1)

## Cwa - RE

re_model_Cwa_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                      data = panel_data_Cwa,
                      model = "random")

summary(re_model_Cwa_1)

## Daily Gross Frequency - FE, RE Hausman Test ##############################################################################

# Perform the Hausman test
hausman_test_Am_1 <- phtest(fe_model_Am_1, re_model_Am_1)

# Print the Hausman test results
print(hausman_test_Am_1)

# Perform the Hausman test
hausman_test_Aw_1 <- phtest(fe_model_Aw_1, re_model_Aw_1)

# Print the Hausman test results
print(hausman_test_Aw_1)

# Perform the Hausman test
hausman_test_BSh_1 <- phtest(fe_model_BSh_1, re_model_BSh_1)

# Print the Hausman test results
print(hausman_test_BSh_1)

# Perform the Hausman test
hausman_test_Cwa_1 <- phtest(fe_model_Cwa_1, re_model_Cwa_1)

# Print the Hausman test results
print(hausman_test_Cwa_1)

## Daily Average Duration - FE, RE ##########################################################################################

## Am - FE

fe_model_Am_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                     data = panel_data_Am,
                     model = "within")

summary(fe_model_Am_2)

## Am - RE

re_model_Am_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                     data = panel_data_Am,
                     model = "random")

summary(re_model_Am_2)

## Aw - FE

fe_model_Aw_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                     data = panel_data_Aw,
                     model = "within")

summary(fe_model_Aw_2)

## Aw - RE

re_model_Aw_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                     data = panel_data_Aw,
                     model = "random")

summary(re_model_Aw_2)

## BSh - FE

fe_model_BSh_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                      data = panel_data_BSh,
                      model = "within")

summary(fe_model_BSh_2)

## BSh - RE

re_model_BSh_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                      data = panel_data_BSh,
                      model = "random")

summary(re_model_BSh_2)

## Cwa - FE

fe_model_Cwa_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                      data = panel_data_Cwa,
                      model = "within")

summary(fe_model_Cwa_2)

## Cwa - RE

re_model_Cwa_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                      data = panel_data_Cwa,
                      model = "random")

summary(re_model_Cwa_2)

## Daily Average Duration - FE, RE Hausman Test ##############################################################################

# Perform the Hausman test
hausman_test_Am_2 <- phtest(fe_model_Am_2, re_model_Am_2)

# Print the Hausman test results
print(hausman_test_Am_2)

# Perform the Hausman test
hausman_test_Aw_2 <- phtest(fe_model_Aw_2, re_model_Aw_2)

# Print the Hausman test results
print(hausman_test_Aw_2)

# Perform the Hausman test
hausman_test_BSh_2 <- phtest(fe_model_BSh_2, re_model_BSh_2)

# Print the Hausman test results
print(hausman_test_BSh_2)

# Perform the Hausman test
hausman_test_Cwa_2 <- phtest(fe_model_Cwa_2, re_model_Cwa_2)

# Print the Hausman test results
print(hausman_test_Cwa_2)

################################################################################

panel_data_coastal <- subset(panel_data, Distance_10km_Y_N == "Y")
panel_data_inland <- subset(panel_data, Distance_10km_Y_N == "N")

summary_coastal <- summary(panel_data_coastal)
summary_inland <- summary(panel_data_inland)

count_result <- panel_data_inland %>% 
  count(whether_outage)

count_result

# Define the file path and name for the Excel file
excel_file <- "summary2.xlsx"

# Write the summary statistics to an Excel file
write.xlsx(summary_coastal, file = excel_file)

# Message to confirm the export
cat("Summary statistics exported to", excel_file, "\n")






# Assuming 'panel_data' is your pdata.frame containing panel data
for (col in names(panel_data_coastal)) {
  adf_coastal_result <- adf.test(panel_data_coastal[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_coastal_result)
}

# Assuming 'panel_data' is your pdata.frame containing panel data
for (col in names(panel_data_inland)) {
  adf_inland_result <- adf.test(panel_data_inland[[col]], alternative = "stationary", k = trunc((length(panel_data[[col]]) - 1)^(1/3)))
  print(paste("Variable:", col))
  print(adf_inland_result)
}

############################################################################

bp_test_pols1_coastal <- bptest(pols_1_coastal)
print(bp_test_pols1_Am)

bp_test_pols1_inland <- bptest(pols_1_inland)
print(bp_test_pols1_inland)

bp_test_pols2_coastal <- bptest(pols_2_coastal)
print(bp_test_pols2_coastal)

bp_test_pols2_inland <- bptest(pols_2_inland)
print(bp_test_pols2_inland)

######

bp_test_fe_coastal_1 <- bptest(fe_model_coastal_1)
print(bp_test_fe_coastal_1)

bp_test_fe_inland_1 <- bptest(fe_model_inland_1)
print(bp_test_fe_inland_1)

bp_test_fe_coastal_2 <- bptest(fe_model_coastal_2)
print(bp_test_fe_coastal_2)

bp_test_fe_inland_2 <- bptest(fe_model_inland_2)
print(bp_test_fe_inland_2)

####

bp_test_re_coastal_1 <- bptest(re_model_coastal_1)
print(bp_test_re_coastal_1)

bp_test_re_inland_1 <- bptest(re_model_inland_1)
print(bp_test_re_inland_1)

bp_test_re_coastal_2 <- bptest(re_model_coastal_2)
print(bp_test_re_coastal_2)

bp_test_re_inland_2 <- bptest(re_model_inland_2)
print(bp_test_re_inland_2)

########################## Logit Regression ################
logit_reg_coastal <- glm(whether_outage ~ t2m + wind + tp + e + ro, data = panel_data_coastal, family = binomial)
summary_logit_reg_coastal <- summary(logit_reg_coastal)
summary_logit_reg_coastal$coefficients <- round(summary_logit_reg_coastal$coefficients, 4)
print(summary_logit_reg_coastal)

logit_reg_inland <- glm(whether_outage ~ t2m + wind + tp + e + ro, data = panel_data_inland, family = binomial)
summary_logit_reg_inland <- summary(logit_reg_inland)
summary_logit_reg_inland$coefficients <- round(summary_logit_reg_inland$coefficients, 4)
print(summary_logit_reg_inland)

AME_coastal <- margins(logit_reg_coastal)
summary(AME_coastal)

AME_inland <- margins(logit_reg_inland)
summary(AME_inland)

#######################################################################################################################
## 6.1. Pooled OLS for each group #####################################################################################
####################################################################################################################### 


pols_1_coastal <- lm(outage_d_gro_freq ~ t2m + wind + tp + e + ro, data = panel_data_coastal)
pols_1_inland <- lm(outage_d_gro_freq ~ t2m + wind + tp + e + ro, data = panel_data_inland)

summary(pols_1_coastal)
summary(pols_1_inland)


tab_model(pols_1_coastal, pols_1_inland, # You can compare multiple models in one table as well.
          show.ci = 0.95, # alpha-level for confidence interval
          show.se = TRUE, # Whether to show standard errors of coefficient estimates
          show.stat = TRUE, # Whether to show t value for coefficient estimates
          dv.labels = c("Coastal: Daily Gross Frequency", "Inland: Daily Gross Frequency"))

head(panel_data)

pols_2_coastal <- lm(outage_d_ave_dur ~ t2m + wind + tp + e + ro, data = panel_data_coastal)
pols_2_inland <- lm(outage_d_ave_dur ~ t2m + wind + tp + e + ro, data = panel_data_inland)

summary(pols_2_coastal)
summary(pols_2_inland)
tab_model(pols_2_coastal, pols_2_inland, # You can compare multiple models in one table as well.
          show.ci = 0.95, # alpha-level for confidence interval
          show.se = TRUE, # Whether to show standard errors of coefficient estimates
          show.stat = TRUE, # Whether to show t value for coefficient estimates
          dv.labels = c("Coastal Group: Daily Average Duration", "Coastal Group: Daily Average Duration"))

#######################################################################################################################
## 6.1. Panel Data Analysis - Gross Frequency for each group ##########################################################
####################################################################################################################### 

## Daily Gross Frequency - FE, RE #####################################################################################

## coastal - FE

fe_model_coastal_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                     data = panel_data_coastal,
                     model = "within")

summary(fe_model_coastal_1)

## inland - FE

fe_model_inland_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                     data = panel_data_inland,
                     model = "within")

summary(fe_model_inland_1)

summary_fe_model_inland_1 <- summary(fe_model_inland_1)
summary_fe_model_inland_1$coefficients <- round(summary_fe_model_inland_1$coefficients, 4)
print(summary_fe_model_inland_1)



## coastal - RE

re_model_coastal_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                          data = panel_data_coastal,
                          model = "random")

summary(re_model_coastal_1)

## inland - RE

re_model_inland_1 <- plm(outage_d_gro_freq ~ t2m + wind + tp + e + ro,
                     data = panel_data_inland,
                     model = "random")

summary(re_model_inland_1)


## Daily Gross Frequency - FE, RE Hausman Test ##############################################################################

# Perform the Hausman test
hausman_test_coastal_1 <- phtest(fe_model_coastal_1, re_model_coastal_1)

# Print the Hausman test results
print(hausman_test_coastal_1)

# Perform the Hausman test
hausman_test_inland_1 <- phtest(fe_model_inland_1, re_model_inland_1)

# Print the Hausman test results
print(hausman_test_inland_1)

## Daily Gross Duration - FE, RE ##########################################################################################

## coastal - FE

fe_model_coastal_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                     data = panel_data_coastal,
                     model = "within")

summary(fe_model_coastal_2)

## coastal - FE

fe_model_inland_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                          data = panel_data_inland,
                          model = "within")

summary(fe_model_inland_2)

## coastal - RE

re_model_coastal_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                     data = panel_data_coastal,
                     model = "random")

summary(re_model_coastal_2)

## inland - RE

re_model_inland_2 <- plm(outage_d_ave_dur ~ t2m + wind + tp + e + ro,
                          data = panel_data_inland,
                          model = "random")

summary(re_model_inland_2)

## Daily Average Duration - FE, RE Hausman Test ##############################################################################

# Perform the Hausman test
hausman_test_coastal_2 <- phtest(fe_model_coastal_2, re_model_coastal_2)

# Print the Hausman test results
print(hausman_test_coastal_2)

# Perform the Hausman test
hausman_test_inland_2 <- phtest(fe_model_inland_2, re_model_inland_2)

# Print the Hausman test results
print(hausman_test_inland_2)


# Assuming your panel data frame is named panel_data with variables y, t2m, ro, e, tp, wind, individual_id, and date
# Perform Granger causality test
result <- pgrangertest(y ~ lag(y, 1) + lag(t2m, 1) + lag(ro, 1) + lag(e, 1) + lag(tp, 1) + lag(wind, 1) | individual_id, data = panel_data)

# Print the result
print(result)


######################################################################################
## 7. DiD Analysis ###################################################################
######################################################################################

str(panel_data)

# Treatment Group: Station-days with t2m higher than 30 celsius
panel_data$treatment_t2m_1 <- ifelse(panel_data$t2m > 30, 1, 0)

# Specify the DiD regression model
did_t2m_1 <- plm(outage_d_gro_freq ~ t2m + tp + treatment_t2m_1 + t2m:treatment_t2m_1 + tp:treatment_t2m_1,
               data = panel_data,
               index = c("station_id", "date"),
               model = "within")

# Estimate the DiD coefficients
coef(did_t2m_1)

# Print the DiD coefficients
print(did_coefficients)

# Perform hypothesis tests or calculate confidence intervals for the coefficients if needed
# For example, you can use the summary() function to obtain summary statistics for the model
summary(did_model)

# Interpret the coefficients to assess the relationship between weather variables and power outage duration

# Visualize the results if needed
# For example, you can plot the coefficient estimates using the coefplot() function from the coefplot package
# install.packages("coefplot")
# library(coefplot)
# coefplot(did_model)

# Additional steps may include robustness checks, sensitivity analyses, and reporting of results

#########################################################
#### Finding best lag length and ########################
#########################################################

