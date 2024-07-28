
# Vudu Library List

This project retrieves a list of purchased movies and TV shows from the Vudu website. It uses Selenium to automate browser interactions and BeautifulSoup to parse the HTML content.

Vudu is a great service, but the web interface leaves something to be desired.  There is no search functionality for only your purchased content, and no way to jump to a position in the list (e.g. jump to movies starting with S).  Scrolling through the list is slow because it only loads a few titles at a time.

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

3. Rename the `sample_creds.py` file to `creds.py` and update with your Vudu login credentials:

    ```python
    VUDU_LOGIN = 'your_email@example.com'
    VUDU_PASSWD = 'your_password'
    ```

## Usage

1. Run the script:
   1. Poetry

        ```bash
        poetry run python vudu_library_list/vudu_library_list.py
        #   --or--
        poetry shell 
        python vudu_library_list/vudu_library_list.py
        ```
    2. venv
        ```bash
        #  Activate virtual environment if necessary
        python vudu_library_list/vudu_library_list.py
        ```


2. The script will log in to Vudu, navigate to the "My Movies" and "My TV" pages, and retrieve the list of purchased content. The movies and TV shows will be saved to separate JSON files named `vudu_movies.json` and `vudu_tv_shows.json`.

## Logging

Logs are saved to `vudu_library_list.log` file.

## Error Handling

If the script encounters an error during execution, it captures the page source for debugging purposes and logs the error details.

## License

This project is licensed under the GNU General Public License 3.0.
