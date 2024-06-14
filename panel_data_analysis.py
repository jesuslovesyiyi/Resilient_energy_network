#######################################################################################################################
###################### Panel Data Analysis: Power Outage Frequency/Duration v. Weather variables ######################
#######################################################################################################################

#######################################################################################################################
############################################# PART 0. Pre-task. Library Setup #########################################
#######################################################################################################################

import statsmodels
import pandas as pd
import os

#######################################################################################################################
############################################# Part 1. Data Cleaning ###################################################
#######################################################################################################################

power = pd.read_csv("D:/ESMI_Dataset/Final_Data/Panel_Data/panel_data_240406.csv")

# Set the directory containing the CSV files
csv_folder = "D:/ESMI_Dataset/Final_Data/Panel_Data/daily_weather"

# Get the list of CSV files in the folder
csv_files = [(os.join(csv_folder, x)) for x in os.listdir(csv_folder) if x.endswith('.csv')]

# Initialize an empty list to store the data frames
data_frames = []

# Loop through each CSV file, read it, and store it in the list
for file in csv_files:
    data_frames.append(pd.read_csv(file))

# # Merge all data frames in the list into a single data frame
# merged_data <- do.call(rbind, data_frames)

# # Optionally, write the merged data frame to a new CSV file
# write.csv(merged_data, "D:/ESMI_Dataset/Final_Data/Panel_Data/daily_weather/new/new.csv", row.names = FALSE)

# # Load the dplyr package
# library(dplyr)

# # Read CSV files A and B

# # Merge files A and B on station_id and date
# merged_df <- inner_join(power, merged_data, by = c("station_id", "date"))

# merged_df

# # Subset all columns except specified ones
# subset_df <- merged_df[, !(names(merged_df) %in% c("station_lat.y", "station_lon.y", "t2m.y", "tp.y", "wind_speed", "Distance_10km_Y_N", "Distance_km", "outage_d_ave_dur"))]

# summary(subset_df)
# # Print the subsetted data frame
# print(subset_df)

# # Assuming your data frame is named df

# # Rename columns
# names(subset_df)[names(subset_df) == "station_lon.x"] <- "station_lon"
# names(subset_df)[names(subset_df) == "station_lat.x"] <- "station_lat"
# names(subset_df)[names(subset_df) == "t2m.x"] <- "t2m"
# names(subset_df)[names(subset_df) == "tp.x"] <- "tp"

# # Print the updated column names
# print(names(subset_df))



# # Save the merged DataFrame to a new CSV file
# write.csv(subset_df, "panel_data_240417.csv", row.names = FALSE)

# print("Merged data saved to: merged_file.csv")


# view(dfready)
# dfready <- read.csv("D:/ESMI_Dataset/Final_Data/Panel_Data/panel_data_240419_test_rh_heat_index.csv")

# summary(dfready)

# # Panel data declaration
# panel_data <- pdata.frame(dfready, index = c("station_id", "date"))
# head(panel_data)
# summary(panel_data)



# dfready <- dfready %>%
#   mutate(whether_outage = ifelse(outage_d_gro_freq == 0, 0, 1))

# # Assuming dfready is your data frame
# dfready <- dfready %>%
#   mutate(outage_d_ave_dur = ifelse(outage_d_gro_freq == 0, 0, outage_d_gro_dur / outage_d_gro_freq))

# write.csv(dfready, file = "output_file_240405.csv", row.names = FALSE)


# # Create histogram
# ggplot(dfready, aes(x = outage_d_gro_freq)) +
#   geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
#   labs(title = "Distribution of Power Outage Frequency",
#        x = "Power Outage Frequency (Nos.)",
#        y = "Frequency") +
#   theme_minimal() +
#   xlim(0, 500)


# # Create summary table
# summary_table <- dfready %>%
#   group_by(Frequency_Category) %>%
#   summarise(Count = n())

# # Add a row for total count
# summary_table <- bind_rows(summary_table, data.frame(Frequency_Category = "Total", Count = sum(summary_table$Count)))

# # Print summary table
# print(summary_table)

# dfready <- dfready %>%
#   mutate(
#     Duration_Category = case_when(
#       outage_d_gro_dur == 0 ~ "0",
#       between(outage_d_gro_dur, 1, 14.999) ~ "[1,15)",
#       between(outage_d_gro_dur, 15, 59.999) ~ "[15, 60)",
#       between(outage_d_gro_dur, 60, 179.999) ~ "[60, 180)",
#       outage_d_gro_dur >= 180 ~ "180 or more"
#     )
#   )

# # Create summary table
# summary_table_2 <- dfready %>%
#   group_by(Duration_Category) %>%
#   summarise(Count = n())

# # Add a row for total count
# summary_table_2 <- bind_rows(summary_table_2, data.frame(Duration_Category = "Total", Count = sum(summary_table_2$Count)))

# # Print summary table
# print(summary_table_2)

# # Create histogram
# ggplot(dfready, aes(x = outage_d_gro_dur)) +
#   geom_histogram(binwidth = 15, fill = "skyblue", color = "black") +
#   labs(title = "Distribution of Power Outage Duration",
#        x = "Power Outage Duration (minutes)",
#        y = "Frequency") +
#   theme_minimal() +
#   xlim(0, 1440) +
#   ylim(0, 50000)

# view(panel_data)

# dfready <- dfready %>%
#   mutate(
#     t2m_category = case_when(
#       between(t2m, -15, -0.00000001) ~ "[-15, 0]",
#       between(t2m, 0, 14.99999999) ~ "[0, 15)",
#       between(t2m, 15, 24.9999999) ~ "[15, 25)",
#       between(t2m, 25, 29.9999999) ~ "[25, 30)",
#       between(t2m, 30, 34.9999999) ~ "[30, 35)",
#       between(t2m, 35, 39.9999999) ~ "[35, 40)",
#     )
#   )

# # Create summary table
# summary_table_3 <- dfready %>%
#   group_by(t2m_category) %>%
#   summarise(Count = n())

# # Add a row for total count
# summary_table_3 <- bind_rows(summary_table_3, data.frame(t2m_category = "Total", Count = sum(summary_table_3$Count)))

# # Print summary table
# print(summary_table_3)

# # Create histogram
# ggplot(dfready, aes(x = t2m)) +
#   geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
#   labs(title = "distribution of daily 2m temperature",
#        x = "daily 2m temperature (celsius)",
#        y = "Frequency") +
#   theme_minimal()

# dfready <- dfready %>%
#   mutate(
#     wind_category = case_when(
#       between(wind, 0, 2.9999999999) ~ "[0, 3)",
#       between(wind, 3, 6.9999999999) ~ "[3, 7)",
#       between(wind, 7, 12) ~ "[7, 12)",
#     )
#   )

# # Create summary table
# summary_table_4 <- dfready %>%
#   group_by(wind_category) %>%
#   summarise(Count = n())

# # Add a row for total count
# summary_table_4 <- bind_rows(summary_table_4, data.frame(wind_category = "Total", Count = sum(summary_table_4$Count)))

# # Print summary table
# print(summary_table_4)

# # Create histogram
# ggplot(dfready, aes(x = wind)) +
#   geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
#   labs(title = "distribution of daily wind speed",
#        x = "daily wind speed (m/s))",
#        y = "Frequency") +
#   theme_minimal()

# summary(panel_data)

# dfready$tp[dfready$tp < 0] <- 0

# panel_data$tp[panel_data$tp < 0] <- 0
# summary(dfready)

# write.csv(dfready, file = "panel_data_240404.csv", row.names = FALSE)

# summary(panel_data)

# dfready <- dfready %>%
#   mutate(
#     tp_category = case_when(
#       tp == 0 ~ "No Rain",
#       between(tp, 0.000000000000000001, 4.999999999999999999999999999) ~ "Light Rain (0, 5)",
#       between(tp, 5, 19.99999999999999999999999) ~ "Moderate Rain [5, 20)",
#       between(tp, 20, 49.999999999999999999999999) ~ "Heavy Rain [20, 50)",
#       between(tp, 50, 99.99999999999999999999999) ~ "Violent Rain: 1 [50,100)",
#       tp >= 100 ~ "Violent Rain: 2(100 or more)"
#     )
#   )

# # Create summary table
# summary_table_5 <- dfready %>%
#   group_by(tp_category) %>%
#   summarise(Count = n())

# # Add a row for total count
# summary_table_5 <- bind_rows(summary_table_5, data.frame(tp_category = "Total", Count = sum(summary_table_5$Count)))

# # Print summary table
# print(summary_table_5)

# # Filter out the "Total" category
# summary_table_plot <- summary_table_5 %>%
#   filter(tp_category != "Total")

# # Create a bar plot
# ggplot(summary_table_plot, aes(x = factor(tp_category, levels = category_order), y = Count)) +
#   geom_bar(stat = "identity", fill = "skyblue") +
#   geom_text(aes(label = Count), vjust = -0.5, color = "black", size = 3) +  # Add count labels above the bars
#   labs(x = "Precipitation Category", y = "Count", title = "Summary of Precipitation Categories") +
#   theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1, lineheight = 0.5)) +  # Adjust x-axis text appearance
#   scale_y_continuous(labels = scales::comma)  # Ensures that numbers on the y-axis are properly formatted

# library(ggplot2)

# ggplot(dfready, aes(x = tp)) +
#   geom_histogram(binwidth = 1, fill = "skyblue", color = "black") +
#   labs(title = "distribution of daily total precipitation",
#        x = "Daily Total Precipitation (mm)",
#        y = "Frequency") +
#   theme_minimal()


# panel_data <- panel_data %>%
#   mutate(tp10mm = tp / 10,
#          windsquare = wind^2)

# summary(panel_data)

# summary(dfready)


# # Assuming your data frame is named combined_data and you want to count values in the 'date' column
# count_result <- dfready %>% 
#   count(whether_outage)

# summary(panel_data)
# summary(dfready)
# count_result

# # pair-wise visual inspection
# ggpairs(dfready[, c("outage_d_gro_freq", "outage_d_gro_dur", "t2m", "tp", "wind_speed", "RH")])


# ggpairs(dfready[, c("outage_freq", "outage_dur", "t2m_c", "tp", "wind", "rh", "heat_index")])

# ####################################### OPTIONAL INSPECTION ########################################

# ## Panel Data inspection
# th_300 <- panel_data[panel_data$tp > 300, ]
# th_500 <- panel_data[panel_data$tp > 500, ]
# th_1000 <- panel_data[panel_data$tp > 1000, ]
# th_2000 <- panel_data[panel_data$tp > 2000, ]

# nrow(th_300)
# nrow(th_500)
# nrow(th_1000)
# nrow(th_2000)
# above_threshold

# master_file <- read.csv("D:/ESMI_Dataset/Final_Data/ESMI_India_538_locations_final_climate_zone.csv")
# ab_th_data <- merge(above_threshold, master_file, by = "station_id", all.x = TRUE)
# ab_th_data

# ab_th_data_1 <- ab_th_data[, c("station_id", "date", "tp", "Lat", "Lon")]
# ab_th_data_1


# lat_lon_data <- ab_th_data_1[, c("Lat", "Lon")]

# south_asia_map_data <- map_data("world") %>% 
#   filter(region %in% c("India","Bangladesh", "Nepal", "Bhutan", "Sri Lanka"))

# # Create a new variable for tp ranges
# ab_th_data_1$tp_range <- cut(ab_th_data_1$tp, breaks = seq(0, max(ab_th_data_1$tp), by = 500), include.lowest = TRUE)

# # Plot latitude and longitude points on a map of South Asia with colored points based on tp ranges
# ggplot() +
#   geom_polygon(data = south_asia_map_data, aes(x = long, y = lat, group = group), fill = "lightgray", color = "black") +
#   geom_point(data = ab_th_data_1, aes(x = Lon, y = Lat, color = tp_range), size = 1.2) +
#   labs(x = "Longitude", y = "Latitude", title = "Location on Map of South Asia", color = "TP Range") +
#   scale_color_brewer(name = "TP Range", palette = "Set1")  # Adjust color palette as needed

# review_data <- merge(panel_data, master_file, by = "station_id", all.x = TRUE)

# lat_lon_review_data <- review_data[, c("Lat", "Lon")]

# south_asia_map_data <- map_data("world") %>% 
#   filter(region %in% c("India","Bangladesh", "Nepal", "Bhutan", "Sri Lanka"))

# head(review_data)

# summary(daily_a)
# # Create a new variable for tp ranges
# lat_long_review_data$daily_average_duration_of_event <- cut(ab_th_data_1$tp, breaks = seq(0, max(ab_th_data_1$tp), by = 500), include.lowest = TRUE)

# # Plot latitude and longitude points on a map of South Asia with colored points based on tp ranges
# ggplot() +
#   geom_polygon(data = south_asia_map_data, aes(x = long, y = lat, group = group), fill = "lightgray", color = "black") +
#   geom_point(data = ab_th_data_1, aes(x = Lon, y = Lat, color = tp_range), size = 1.2) +
#   labs(x = "Longitude", y = "Latitude", title = "Location on Map of South Asia", color = "TP Range") +
#   scale_color_brewer(name = "TP Range", palette = "Set1")  # Adjust color palette as needed

# summary(dfready)