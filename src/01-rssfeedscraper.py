import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urlparse, urlunparse, urljoin
import os
import re
import feedparser
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

    def is_valid_rss(self, response_content):
        """
        Checks if the given content is a valid RSS feed based on some heuristics.
        """
        content_str = response_content.decode() if isinstance(response_content, bytes) else response_content
        return content_str.startswith('<?xml') and ('<rss' in content_str or '<feed' in content_str)

    def scrape_rss_feeds(self):
        print("Scraping RSS feeds from URLs...")
        # Read the list of URLs from the file
        with open(self.url_list_filename) as file:
            urls = eval(file.read())

        conn = sqlite3.connect(self.output_db_filename)
        cursor = conn.cursor()

        # Create tables to store the main URLs, RSS feed URLs, and failed URLs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS LINKS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main TEXT,
                feed TEXT,
                type TEXT
            )
        ''')
        cursor.execute('CREATE TABLE IF NOT EXISTS FAILED_LINKS (main TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS FAILED_PARSE (main TEXT)')

        for url in urls:
            normalized_url = self.normalize_url(url)

            # Check if the URL exists in LINKS or FAILED_LINKS table
            cursor.execute('SELECT * FROM LINKS WHERE main = ?', (normalized_url,))
            existing_link = cursor.fetchone()
            cursor.execute('SELECT * FROM FAILED_LINKS WHERE main = ?', (normalized_url,))
            existing_failed_link = cursor.fetchone()

            if existing_link or existing_failed_link:
                continue

            try:
                response = requests.get(normalized_url, timeout=5)
                content_type = response.headers.get('Content-Type', '').split(';')[0]
                # print(f"content type: {content_type}")
                # If content is XML or validates as RSS
                if 'xml' in content_type or self.is_valid_rss(response.content):
                    self.rss_feeds.append((normalized_url, normalized_url))
                    continue
                else:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    # print(f"Soup: \n{soup}\n------------------\n")

            # except requests.exceptions.RequestException as e:
            #     cursor.execute('INSERT INTO FAILED_LINKS VALUES (?)', (normalized_url,))
            #     conn.commit()
            #     continue
            except:
                cursor.execute('INSERT INTO FAILED_PARSE VALUES (?)', (normalized_url,))
                conn.commit()
                continue

            # Find the RSS feed link in the website's HTML
            rss_link = soup.find("link", type="application/rss+xml")
            if rss_link:
                try:
                    response = requests.get(rss_link['href'], timeout=5)
                    # print(f"First 20 characters of response for {rss_link['href']}:\n{response.text[:20]}")
                    # if first 20 chars contain 'xml', add xml as the 3rd column
                    if 'xml' in response.text[:20]:
                        self.rss_feeds.append((normalized_url, rss_link['href'], 'xml'))
                        # print(f"Added {normalized_url} to LINKS table")
                    elif 'html' in response.text[:20]:
                        self.rss_feeds.append((normalized_url, rss_link['href'], 'html'))
                        # print(f"Added {normalized_url} to LINKS table")
                except requests.exceptions.RequestException:
                    continue

        # Insert main URLs and corresponding RSS feed URLs into the database
        cursor.executemany('INSERT INTO LINKS VALUES (NULL, ?, ?, ?)', self.rss_feeds)
        conn.commit()
        conn.close()
        print(f"Done. Added {len(self.rss_feeds)} RSS feeds to LINKS table.")

    def add_direct_feeds(self, direct_feed_filename):
        print("Adding RSS feeds from Feed URLs...")
        with open(direct_feed_filename, 'r') as file:
            feed_links = [link.strip() for link in file.readlines()]

        conn = sqlite3.connect(self.output_db_filename)
        cursor = conn.cursor()

        direct_feeds = []

        for feed_link in feed_links:
            # Check existence in LINKS or FAILED_LINKS table
            cursor.execute('SELECT * FROM LINKS WHERE main = ?', (feed_link,))
            existing_link = cursor.fetchone()
            cursor.execute('SELECT * FROM FAILED_LINKS WHERE main = ?', (feed_link,))
            existing_failed_link = cursor.fetchone()

            if existing_link or existing_failed_link:
                continue

            try:
                response = requests.get(feed_link, timeout=5)
                content_type = response.headers.get('Content-Type', '').split(';')[0]
                # print(f"First 20 characters of response for {feed_link}:\n{response.text[:20]}")

                if 'xml' in content_type:
                    feed_type = 'xml'
                    direct_feeds.append((feed_link, feed_link, feed_type))
                    # print(f"Added {feed_link} to LINKS table")
                elif 'html' in content_type and self.is_valid_rss(response.content):
                    feed_type = 'html'
                    direct_feeds.append((feed_link, feed_link, feed_type))
                    # print(f"Added {feed_link} to LINKS table")
                else:
                    cursor.execute('INSERT INTO FAILED_LINKS VALUES (?)', (feed_link,))
                    conn.commit()
            except requests.exceptions.RequestException:
                cursor.execute('INSERT INTO FAILED_LINKS VALUES (?)', (feed_link,))
                conn.commit()
                continue

        cursor.executemany('INSERT INTO LINKS VALUES (NULL, ?, ?, ?)', direct_feeds)
        conn.commit()
        conn.close()
        print(f"Done. Added {len(direct_feeds)} RSS feeds to LINKS table.")

    def clean_links(self):
        print("Adding RSS feeds from Feed URLs...")

        conn = sqlite3.connect(self.output_db_filename)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT main
            FROM FAILED_LINKS
        ''')
        rows = cursor.fetchall()

        cleaned_links = []

        for row in rows[:]:
            failed_link = row[0]
            print(f"Failed link: {failed_link}")
            # Remove everything after .com
            cleaned_link = re.sub(r'(\.com).*', r'\1', failed_link)
            cleaned_links.append(cleaned_link)  # Store the cleaned link in the list
            print(f"Cleaned link: {cleaned_link}")

        # Write cleaned links to file in list format
        with open('src/dbs/links/cleaned_links.txt', 'w') as file:
            file.write('[\n')
            for link in cleaned_links:
                file.write(f"    '{link}',\n")
            file.write(']\n')

    def is_github_action(self):
        """Detect if we are running in a GitHub Actions environment."""
        return os.environ.get('GITHUB_WORKSPACE') is not None

    def get_filepath(self,filename):
        """Return the appropriate filepath depending on the environment."""
        if self.is_github_action():
            base_path = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src')
        else:
            base_path = 'src'
        return os.path.join(base_path, filename)

# if __name__ == "__main__":
#     # current_directory = os.getcwd()
#     # parent_directory = os.path.dirname(current_directory)
#     # os.chdir(parent_directory)
#     # url_list_filepath = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src/dbs/links/urllist.txt')
#     # direct_feed_filepath = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src/dbs/links/unique_feed_links.txt')
#     # db_path = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src/dbs/rss_sum.db')
#     rss_scraper = RSSFeedScraper(url_list_filename='dbs/links/urllist.txt', output_db_filename='dbs/rss_sum.db')
#     # rss_scraper = RSSFeedScraper(url_list_filename='src/dbs/links/cleaned_links.txt', output_db_filename='src/dbs/rss_sum.db')
#     rss_scraper.scrape_rss_feeds()
#     rss_scraper.add_direct_feeds(direct_feed_filename='dbs/links/unique_feed_links.txt')
#     # rss_scraper.clean_links()

if __name__ == "__main__":
    
    def is_github_action():
        """Detect if we are running in a GitHub Actions environment."""
        return os.environ.get('GITHUB_WORKSPACE') is not None

    def get_filepath(filename):
        """Return the appropriate filepath depending on the environment."""
        if is_github_action():
            base_path = os.path.join(os.environ['GITHUB_WORKSPACE'], 'src')
        else:
            base_path = ''
        return os.path.join(base_path, filename)
    
    
    url_list_filepath = get_filepath('dbs/links/urllist.txt')
    direct_feed_filepath = get_filepath('dbs/links/unique_feed_links.txt')
    db_path = get_filepath('dbs/rss_sum.db')

    print(f"url_list_filepath: {url_list_filepath}")
    print(f"direct_feed_filepath: {direct_feed_filepath}")
    print(f"db_path: {db_path}")

    rss_scraper = RSSFeedScraper(url_list_filename=url_list_filepath, output_db_filename=db_path)


    rss_scraper.scrape_rss_feeds()
    # rss_scraper.add_direct_feeds(direct_feed_filename=direct_feed_filepath)
    # rss_scraper.clean_links()
