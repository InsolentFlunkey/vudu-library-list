
# Vudu Library List

This project retrieves a list of purchased movies and TV shows from the Vudu website. It uses Selenium to automate browser interactions and BeautifulSoup to parse the HTML content.

Vudu is a great service, but the web interface leaves something to be desired.  There is no way to search only your purchased content, and no way to jump to a position in the list (e.g. jump to movies starting with S).  Scrolling through the list is slow because it only loads a few titles at a time.

## Requirements

- Python 3.x (Developed with Python 3.12)
- Selenium
- BeautifulSoup4
- Webdriver Manager
- Chrome browser

## Setup

1. Clone the repository:

    ```bash
    git clone https://github.com/InsolentFlunkey/vudu-library-list.git
    cd vudu-library-list
    ```

2. Create your environment
   1. Using Poetry (recommended)
      1. Install Poetry if you haven't already:
          ```bash
          pip install poetry
          ```
      2. Install the project dependencies:
          ```bash
          poetry install
          ```
    2. Using venv and requirements.txt
       1. Create a virtual environment and activate it:
            ```bash
            python -m venv venv
            source venv/bin/activate #  Linux
            venv\Scripts\activate #  Windows
            ```
        2. Install the required packages:
            ```bash
            pip install -r requirements.txt
            ```

3. Rename the `vudu_library_list/sample_creds.py` file to `vudu_library_list/creds.py` and update with your Vudu login credentials:

    ```python
    VUDU_LOGIN = 'your_email@example.com'
    VUDU_PASSWD = 'your_password'
    ```

## Usage

1. Run the script:
   1. Poetry

        ```bash
        cd vudu_library_list
        poetry run python vudu_library_list.py
        ```

        -- or using Poetry shell --

        ```bash
        poetry shell 
        cd vudu_library_list
        python vudu_library_list.py
        ```
    2. venv
        ```bash
        #  Activate virtual environment if necessary
        cd vudu_library_list
        python vudu_library_list.py
        ```


2. The script will log in to Vudu, navigate to the "My Movies" and "My TV" pages, and retrieve the list of purchased content. The movies and TV shows will be saved to separate JSON files named `lists/vudu_movies.json` and `lists/vudu_tv_shows.json`.  (NOTE: output directory name is configurable in the `constants.py` file.)

_**Caution**_: The Vudu website does not load properly in headless mode, so the script must launch an instance of Chrome in windowed mode.  Interacting with the browser window may interfere with retrieving the content lists.  The Chrome window will close automatically at the end of the run.

## Logging

Logs are saved to `logs/vudu_library_list.log` file.

## Error Handling

If the script encounters an error during execution, it captures the page source for debugging purposes and logs the error details.

## Planned Updates

1. Expand Bundle Collections to retrieve included item titles.
2. Add a display method for the retrieved lists, perhaps with Streamlit or Flask.  Suggestions?

## License

This project is licensed under the GNU General Public License 3.0.
