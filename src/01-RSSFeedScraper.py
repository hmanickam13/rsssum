import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urlparse, urlunparse
from util import get_filepath
import datetime
import json
import os

class RSSFeedScraper:
    def __init__(self, webpage_links_filename, feed_links_filename, db_filename):
        self.webpage_links_filename = webpage_links_filename
        self.feed_links_filename = feed_links_filename
        self.db_filename = db_filename
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()
        self.rss_feeds = []
        self.direct_feeds = []

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
        content_str = response_content.decode() if isinstance(response_content, bytes) else response_content
        return content_str.startswith('<?xml') and ('<rss' in content_str or '<feed' in content_str)

    def scrape_rss_feeds(self):
        print("Scraping RSS feeds from URLs...")
        # Read the list of URLs from the file
        with open(self.webpage_links_filename) as file:
            urls = [link.strip() for link in file.readlines()]

        # Create tables to store the main URLs, RSS feed URLs, and failed URLs
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS LINKS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main TEXT,
                feed TEXT,
                type TEXT,
                total_articles INTEGER DEFAULT 0
            )
        ''')
        self.c.execute('CREATE TABLE IF NOT EXISTS FAILED_LINKS (main TEXT)')
        self.c.execute('CREATE TABLE IF NOT EXISTS FAILED_PARSE (main TEXT)')

        normalized_urls = []
        for url in urls:
            # print(f"Feed link: {url}")
            normalized_url = self.normalize_url(url)
            normalized_urls.append(normalized_url)

            # Check if the URL exists in LINKS or FAILED_LINKS table
            self.c.execute('SELECT * FROM LINKS WHERE main = ?', (normalized_url,))
            existing_link = self.c.fetchone()
            self.c.execute('SELECT * FROM FAILED_LINKS WHERE main = ?', (normalized_url,))
            existing_failed_link = self.c.fetchone()

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
            except:
                self.c.execute('INSERT INTO FAILED_PARSE VALUES (?)', (normalized_url,))
                self.conn.commit()
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
                        print(f"Added {normalized_url} to LINKS table")
                    elif 'html' in response.text[:20]:
                        self.rss_feeds.append((normalized_url, rss_link['href'], 'html'))
                        print(f"Added {normalized_url} to LINKS table")
                except requests.exceptions.RequestException:
                    continue

        # Insert main URLs and corresponding RSS feed URLs into the database
        self.c.executemany('INSERT INTO LINKS VALUES (NULL, ?, ?, ?, NULL)', self.rss_feeds)
        self.conn.commit()
        # self.conn.close()
        print(f"Done. Added {len(self.rss_feeds)} RSS feeds to LINKS table.")

        # Write back the normalized URLs to the file
        with open(self.webpage_links_filename, 'w') as file:
            for n_url in normalized_urls:
                file.write(n_url + '\n')

        return len(self.rss_feeds)

    def add_direct_feeds(self):
        print("Adding RSS feeds from Feed URLs...")
        with open(self.feed_links_filename, 'r') as file:
            feed_links = [link.strip() for link in file.readlines()]

        for feed_link in feed_links:
            # Check existence in LINKS or FAILED_LINKS table
            self.c.execute('SELECT * FROM LINKS WHERE main = ?', (feed_link,))
            existing_link = self.c.fetchone()
            self.c.execute('SELECT * FROM FAILED_LINKS WHERE main = ?', (feed_link,))
            existing_failed_link = self.c.fetchone()

            if existing_link or existing_failed_link:
                continue

            try:
                response = requests.get(feed_link, timeout=5)
                content_type = response.headers.get('Content-Type', '').split(';')[0]
                # print(f"First 20 characters of response for {feed_link}:\n{response.text[:20]}")

                if 'xml' in content_type:
                    feed_type = 'xml'
                    self.direct_feeds.append((feed_link, feed_link, feed_type))
                    print(f"Added {feed_link} to LINKS table")
                elif 'html' in content_type and self.is_valid_rss(response.content):
                    feed_type = 'html'
                    self.direct_feeds.append((feed_link, feed_link, feed_type))
                    print(f"Added {feed_link} to LINKS table")
                else:
                    self.c.execute('INSERT INTO FAILED_LINKS VALUES (?)', (feed_link,))
                    self.conn.commit()
            except requests.exceptions.RequestException:
                self.c.execute('INSERT INTO FAILED_LINKS VALUES (?)', (feed_link,))
                self.conn.commit()
                continue

        self.c.executemany('INSERT INTO LINKS VALUES (NULL, ?, ?, ?, NULL)', self.direct_feeds)
        self.conn.commit()
        # self.conn.close()
        print(f"Done. Added {len(self.direct_feeds)} RSS feeds to LINKS table.")

    def delete_links(self):
        print("Deleting RSS feeds not present in the provided file lists...")

        # Load the links from webpage_links_filepath
        with open(self.webpage_links_filename, 'r') as file:
            webpage_links_links = [link.strip() for link in file.readlines()]

        # Load the links from feed_links_filepath
        with open(self.feed_links_filename, 'r') as file:
            feed_links_links = [link.strip() for link in file.readlines()]

        combined_links = set(webpage_links_links + feed_links_links)  # Convert to set for faster lookups

        # print(f"Total links in webpage_links: {len(webpage_links_links)}")
        # print(f"Total links in direct_feed: {len(feed_links_links)}")
        # print(f"Total links in combined_links: {len(combined_links)}")

        # Fetch all links from LINKS table
        self.c.execute('SELECT main FROM LINKS')
        all_db_links = [row[0] for row in self.c.fetchall()]

        counter = 0
        for db_link in all_db_links:
            if db_link not in combined_links:
                counter += 1
                print(f"Deleting {db_link} from LINKS table...")

                self.c.execute('DELETE FROM LINKS WHERE main = ?', (db_link,))
                self.conn.commit()
        
        print(f"Done. Deleted {counter} RSS feeds from LINKS table.")

if __name__ == "__main__":

    today_date = datetime.datetime.today().strftime('%Y-%m-%d')
    # two_days_ago = datetime.datetime.today() - datetime.timedelta(days=1)
    # two_days_ago_date = two_days_ago.strftime('%Y-%m-%d')

    json_status_file_name = get_filepath('status.json')
    print(f"Current working directory: {os.getcwd()}")

    try:    
        with open(json_status_file_name, 'r') as f:
            existing_status = json.load(f)
    except FileNotFoundError:
        existing_status = {} # If file doesn't exist, create an empty dict

    status_data ={}
    try:
        webpage_links_filepath = get_filepath('dbs/links/webpage_links.txt')
        feed_links_filepath = get_filepath('dbs/links/feed_links.txt')
        db_path = get_filepath('dbs/rss_sum.db')
        rss_scraper = RSSFeedScraper(webpage_links_filename=webpage_links_filepath, feed_links_filename=feed_links_filepath, db_filename=db_path)
        rss_scraper.scrape_rss_feeds()
        rss_scraper.add_direct_feeds()
        rss_scraper.delete_links()
        rss_scraper.conn.close()
        status_data['RSSFeedScraper'] = {
            'status': 'Success',
            'links_or_feeds_added': len(rss_scraper.rss_feeds) + len(rss_scraper.direct_feeds),
            'links_or_feeds_deleted': rss_scraper.deleted_links_count
        }
    except Exception as e:
        status_data['RSSFeedScraper'] = {
            'status': 'Failed',
            'message': str(e)
        }

    existing_status = {today_date: status_data, **existing_status}

    with open(json_status_file_name, 'w') as f:
        json.dump(existing_status, f, indent=4)


