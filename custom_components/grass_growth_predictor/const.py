"""Constants for the Grass Growth Predictor integration."""

DOMAIN = "grass_growth_predictor"

# ----- Storage -----
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

# ----- Config entry keys -----
CONF_WEATHER_ENTITY = "weather_entity_id"
CONF_MOWED_TO_HEIGHT = "mowed_to_height"
CONF_BASE_GROWTH_RATE = "base_growth_rate"
CONF_ENABLE_SEASONAL = "enable_seasonal"
CONF_ENABLE_GDD = "enable_gdd"
CONF_ENABLE_RAIN = "enable_rain"
CONF_ENABLE_SOIL_MOISTURE = "enable_soil_moisture"
CONF_ENABLE_SOIL_TEMP = "enable_soil_temp"

# ----- Defaults -----
DEFAULT_WEATHER_ENTITY = "weather.openweathermap"
DEFAULT_MOWED_TO_HEIGHT = 3.0       # inches
DEFAULT_BASE_GROWTH_RATE = 0.15     # inches per day
DEFAULT_ENABLE_SEASONAL = True
DEFAULT_ENABLE_GDD = True
DEFAULT_ENABLE_RAIN = True
DEFAULT_ENABLE_SOIL_MOISTURE = True
DEFAULT_ENABLE_SOIL_TEMP = True

# ----- Update intervals (seconds) -----
SOIL_UPDATE_INTERVAL = 43_200       # 12 h; coordinator poll is 2 h but soil data only re-fetched after this interval

# ----- API base URLs (soil services only; weather data comes via HA weather entity) -----
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

# ----- Mower control config keys -----
CONF_MIN_DAYS_BETWEEN_MOWS = "min_days_between_mows"
CONF_MAX_DAYS_BETWEEN_MOWS = "max_days_between_mows"
CONF_MAX_GROWTH_BETWEEN_MOWS = "max_growth_between_mows"
CONF_FORCE_MOW_GROWTH_THRESHOLD = "force_mow_growth_threshold"
CONF_MOW_CYCLE_DURATION_HOURS = "mow_cycle_duration_hours"
CONF_WET_RAIN_THRESHOLD_IN = "wet_rain_threshold_in"
CONF_WET_HUMIDITY_PCT = "wet_humidity_pct"
CONF_DRY_WINDOW_LOOKAHEAD_HOURS = "dry_window_lookahead_hours"

# ----- Mower control defaults -----
DEFAULT_MIN_DAYS_BETWEEN_MOWS = 3
DEFAULT_MAX_DAYS_BETWEEN_MOWS = 10
DEFAULT_MAX_GROWTH_BETWEEN_MOWS = 0.5    # inches — try to mow when grown ≥ this (prefer dry)
DEFAULT_FORCE_MOW_GROWTH_THRESHOLD = 1.0 # inches — mow regardless of wet when grown ≥ this
DEFAULT_MOW_CYCLE_DURATION_HOURS = 12.0  # hours the automated mower runs
DEFAULT_WET_RAIN_THRESHOLD_IN = 0.1      # inches today that classify grass as wet
DEFAULT_WET_HUMIDITY_PCT = 85            # % relative humidity above which grass is considered wet
DEFAULT_DRY_WINDOW_LOOKAHEAD_HOURS = 48  # hours ahead to scan for a dry mow window

# ----- Service names -----
SERVICE_MARK_MOWED = "mark_mowed"

# ----- Persistent store keys -----
STORE_LAST_MOW_TIMESTAMP = "last_mow_timestamp"
STORE_MOWED_TO_HEIGHT = "mowed_to_height"
STORE_MOW_SESSION_ACTIVE = "mow_session_active"

# ----- Sensor / attribute names -----
SENSOR_CURRENT_GRASS_HEIGHT = "current_grass_height"
SENSOR_DAILY_GROWTH_RATE = "daily_growth_rate"
SENSOR_DAYS_SINCE_MOW = "days_since_mow"
SENSOR_GROWTH_SINCE_MOW = "growth_since_mow"
SENSOR_NEXT_DRY_MOW_WINDOW = "next_dry_mow_window"
SENSOR_GDD = "gdd"
SENSOR_RAINFALL = "rainfall"
SENSOR_SOIL_MOISTURE = "soil_moisture"
SENSOR_SOIL_TEMPERATURE = "soil_temperature"
SENSOR_SEASON_FACTOR = "season_factor"

# ----- Button names -----
BUTTON_MARK_MOWED = "mark_mowed"
BUTTON_MOW_COMPLETE = "mow_complete"

# ----- Switch names -----
SWITCH_MOW_SESSION = "mow_session"

# ----- Binary sensor names -----
BINARY_SENSOR_MOW_RECOMMENDED = "mow_recommended"
BINARY_SENSOR_MOW_OVERDUE = "mow_overdue"
BINARY_SENSOR_GRASS_WET = "grass_wet"
BINARY_SENSOR_DRY_MOW_WINDOW_SOON = "dry_mow_window_soon"
BINARY_SENSOR_MOW_NOT_ADVISED = "mow_not_advised"

ATTR_LAST_MOW_TIMESTAMP = "last_mow_timestamp"
ATTR_DAILY_GROWTH_RATE = "daily_growth_rate"
ATTR_DAYS_SINCE_MOW = "days_since_last_mow"
ATTR_GDD = "gdd"
ATTR_RAINFALL = "rainfall"
ATTR_SOIL_MOISTURE = "soil_moisture"
ATTR_SOIL_TEMPERATURE = "soil_temperature"
ATTR_SEASON_FACTOR = "season_factor"
ATTR_ENABLED_MULTIPLIERS = "enabled_multipliers"
