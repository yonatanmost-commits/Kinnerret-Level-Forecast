# Project Description: Sea of Galilee (Kinneret) Level Forecast Model

## Project Goal
The primary objective of this project is to develop a predictive model for the water level of the Sea of Galilee (Kinneret). By leveraging historical hydrological and meteorological data alongside real-time weather forecasts, the model aims to provide accurate level forecasts.

## Data Sources
The project integrates data from three primary national authorities.

 Below is a summary of the data types and the specific source files used for development:

| Data Type | Source | Parameters | Example Filename |
| :--- | :--- | :--- | :--- |
| **Kinneret Level** | Israel Water Authority | Daily/Historical water level (meters below sea level) | `2de7b543-e13d-4e7e-b4c8-56071bc4d3c8.csv` |
| **Weather Data** | Israel Meteorological Service (IMS) | Temp, Humidity, Rain, Wind, and short-term forecasts | `data_202604112030.csv` |
| **River Flow Rates** | Hydrological Service | Inflow from the Jordan River and other streams; Outflows | `62cd157d-766d-4648-897d-50526f45abf9 (1).csv` |

## Project Methodology

### 1. Data Collection & Preprocessing
The foundation of the project involves aggregating historical records from the Water Authority, IMS, and the Hydrological Service. This includes cleaning time-series data, handling missing values, and synchronizing different measurement frequencies (hourly vs. daily).

### 2. Analysis and Model Development
Using historical patterns—such as the correlation between Jordan River flow spikes and subsequent level rises—a Machine Learning model will be trained. The model will account for:
* **Direct Precipitation:** Rainfall directly over the lake surface.
* **Inflow:** Surface runoff and river discharge from the catchment area.
* **Outflow & Evaporation:** Water pumped for the National Water Carrier and losses due to evaporation (calculated from temperature and humidity).

### 3. Forecasting and Evaluation
Once the base model is established, the project enters an iterative operational phase:
* **Scraping:** Automated retrieval of the latest 5-day weather forecasts and real-time station reports.
* **Prediction:** Running the forecast data through the model to estimate the Kinneret's level for the coming week.
* **Continuous Learning:** Comparing predicted levels against actual reported measurements. Using a Machine Learning approach, the model will be retrained with this new data to reduce error rates and improve accuracy over time (Reinforcement/Continuous Learning).
