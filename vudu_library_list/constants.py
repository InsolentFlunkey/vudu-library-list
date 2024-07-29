#  Logging level - ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
#    NOTE: Log file appends, so it will grow with every execution.  You also may see large Selenium log messages.
#          Remember to clean up your log files!
LOGGING_LEVEL_FILE = "INFO"
LOGGING_LEVEL_CONSOLE = "INFO"

#  URLs
VUDU_MAIN_URL = 'https://www.vudu.com'
VUDU_MYMOVIES_URL = 'https://www.vudu.com/content/movies/mymovies'
VUDU_MYTV_URL = 'https://www.vudu.com/content/movies/mytv'

#  CSS Selectors
SIGN_IN_ELEMENT = 'button[aria-label="Sign In"]'
MOVIE_ELEMENT = 'div'
MOVIE_ELEMENT_CLASS = 'contentPosterWrapper'

#  File locations
LOG_DIR = 'logs'
LOG_FILE = 'vudu_library_list.log'
OUTPUT_DIR = 'lists'
MOVIE_LIST_FILE = 'vudu_movies.json'
TV_LIST_FILE = 'vudu_tv_shows.json'