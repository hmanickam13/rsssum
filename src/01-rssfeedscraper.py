import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urlparse, urlunparse, urljoin
import os

class RSSFeedScraper:
    def __init__(self, url_list_filename, output_db_filename):
        self.url_list_filename = url_list_filename
        self.output_db_filename = output_db_filename
        self.rss_feeds = []

    def normalize_url(self, url):
        parsed_url = urlparse(url)
        normalized_path = parsed_url.path.rstrip('/') + '/'
        normalized_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            normalized_path,
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment
        ))
        return normalized_url

    def scrape_rss_feeds(self):
        # Read the list of URLs from the file
        with open(self.url_list_filename) as file:
            urls = file.read()

        # Evaluate the string as a Python list
        urls = eval(urls)

        # Create a connection to the SQLite database
        conn = sqlite3.connect(self.output_db_filename)
        cursor = conn.cursor()

        # Create tables to store the main URLs, RSS feed URLs, and failed URLs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS LINKS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main TEXT,
                feed TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS FAILED_LINKS (
                main TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS FAILED_PARSE (
                main TEXT
            )
        ''')

               # Iterate through the list of URLs
        for url in urls:
            normalized_url = self.normalize_url(url)
            # print(f'Parsed URL: {normalized_url}')

            # Check if the URL exists in LINKS or FAILED_LINKS table
            cursor.execute('SELECT * FROM LINKS WHERE main = ?', (normalized_url,))
            existing_link = cursor.fetchone()
            cursor.execute('SELECT * FROM FAILED_LINKS WHERE main = ?', (normalized_url,))
            existing_failed_link = cursor.fetchone()

            if existing_link:
                print(f'URL already exists in the LINKS table: {normalized_url}')
                continue
            elif existing_failed_link:
                print(f'URL already exists in the FAILED_LINKS table: {normalized_url}')
                continue

            request_successful = False
            parse_successful = False
            rss_found = False

            try:
                # Send a GET request to the website
                response = requests.get(normalized_url, timeout=5)
                request_successful = True
            except requests.exceptions.RequestException as e:
                print(f'Error: {e}')
                cursor.execute('INSERT INTO FAILED_LINKS VALUES (?)', (normalized_url,))
                conn.commit()
                continue

            if request_successful:
                print(f'Successful request for: {normalized_url}')

            try:
                # Parse the HTML content of the website
                soup = BeautifulSoup(response.content, 'html.parser')
                parse_successful = True
            except:
                print(f' Error parsing HTML content for {normalized_url}')
                cursor.execute('INSERT INTO FAILED_PARSE VALUES (?)', (normalized_url,))
                conn.commit()
                continue

            if parse_successful:
                print(f' Parsed HTML response for: {normalized_url}')

            # Find the RSS feed link in the website's HTML
            rss_link = soup.find("link", type="application/rss+xml")

            if rss_link:
                self.rss_feeds.append((normalized_url, rss_link['href']))
                rss_found = True
            else:
                print(f'  No RSS feed found for {normalized_url}')

            if rss_found:
                print(f'  RSS feed found for {normalized_url}')

        # Insert main URLs and corresponding RSS feed URLs into the database
        cursor.executemany('INSERT INTO LINKS VALUES (NULL, ?, ?)', self.rss_feeds)
        conn.commit()
        conn.close()
        print(f"\nMain URLs and RSS feeds written to {self.output_db_filename}")

if __name__ == "__main__":
    db_path = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src/dbs/rss_sum.db')
    rss_scraper = RSSFeedScraper(url_list_filename='src/dbs/links/urllist.txt', output_db_filename=db_path)
    rss_scraper.scrape_rss_feeds()