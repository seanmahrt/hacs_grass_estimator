"""Constants for the Grass Growth Predictor integration."""

DOMAIN = "grass_growth_predictor"

# ----- Storage -----
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

# ----- Config entry keys -----
CONF_OWM_API_KEY = "owm_api_key"
CONF_MOWED_TO_HEIGHT = "mowed_to_height"
CONF_BASE_GROWTH_RATE = "base_growth_rate"
CONF_ENABLE_SEASONAL = "enable_seasonal"
CONF_ENABLE_GDD = "enable_gdd"
CONF_ENABLE_RAIN = "enable_rain"
CONF_ENABLE_SOIL_MOISTURE = "enable_soil_moisture"
CONF_ENABLE_SOIL_TEMP = "enable_soil_temp"

# ----- Defaults -----
DEFAULT_MOWED_TO_HEIGHT = 3.0       # inches
DEFAULT_BASE_GROWTH_RATE = 0.15     # inches per day
DEFAULT_ENABLE_SEASONAL = True
DEFAULT_ENABLE_GDD = True
DEFAULT_ENABLE_RAIN = True
DEFAULT_ENABLE_SOIL_MOISTURE = True
DEFAULT_ENABLE_SOIL_TEMP = True

# ----- Update intervals (seconds) -----
WEATHER_UPDATE_INTERVAL = 43_200    # 12 h
SOIL_UPDATE_INTERVAL = 43_200       # 12 h
HEIGHT_UPDATE_INTERVAL = 43_200     # 12 h

# ----- API base URLs -----
OWM_BASE_URL = "https://api.openweathermap.org/data/3.0/onecall"
NSM_BASE_URL = "https://nationalsoilmoisture.com/test/data_api/"
SCAN_STATIONS_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/stations"
SCAN_DATA_URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"

# ----- Growth model constants -----
GDD_BASE_TEMP_F = 50.0
OPTIMAL_GDD_DAILY = 20.0
OPTIMAL_SOIL_MOISTURE_PCT = 45.0
OPTIMAL_SOIL_TEMP_F = 65.0

# Season growth multiplier by month (Northern Hemisphere turf)
SEASON_FACTORS: dict[int, float] = {
    1: 0.30,
    2: 0.40,
    3: 0.70,
    4: 1.20,
    5: 1.50,
    6: 1.30,
    7: 1.00,
    8: 0.90,
    9: 1.10,
    10: 0.80,
    11: 0.50,
    12: 0.30,
}

# ----- Service names -----
SERVICE_MARK_MOWED = "mark_mowed"

# ----- Persistent store keys -----
STORE_LAST_MOW_TIMESTAMP = "last_mow_timestamp"
STORE_MOWED_TO_HEIGHT = "mowed_to_height"
STORE_WEATHER_FETCHED_AT = "weather_fetched_at"
STORE_WEATHER_DATA = "weather_data"

# ----- Sensor / attribute names -----
SENSOR_CURRENT_GRASS_HEIGHT = "current_grass_height"

# ----- Button names -----
BUTTON_MARK_MOWED = "mark_mowed"

ATTR_LAST_MOW_TIMESTAMP = "last_mow_timestamp"
ATTR_DAILY_GROWTH_RATE = "daily_growth_rate"
ATTR_DAYS_SINCE_MOW = "days_since_last_mow"
ATTR_GDD = "gdd"
ATTR_RAINFALL = "rainfall"
ATTR_SOIL_MOISTURE = "soil_moisture"
ATTR_SOIL_TEMPERATURE = "soil_temperature"
ATTR_SEASON_FACTOR = "season_factor"
ATTR_ENABLED_MULTIPLIERS = "enabled_multipliers"
ATTR_SOIL_MOISTURE = "soil_moisture"
ATTR_SOIL_TEMPERATURE = "soil_temperature"
ATTR_SEASON_FACTOR = "season_factor"
ATTR_ENABLED_MULTIPLIERS = "enabled_multipliers"
