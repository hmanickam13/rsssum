import os
import feedparser
import sqlite3
import json
from datetime import datetime

class GetArticlesMetadata:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        # self.output_filename = output_filename
        self.articles_count = []
        self.entries = []
        self.dict_entries = []
        self.create_metadata_table()
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()

    def create_metadata_table(self):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Metadata (
                id INTEGER,
                id_article INTEGER,
                title TEXT,
                guid TEXT,
                published TEXT,
                published_date TEXT,
                published_within_10_days INTEGER DEFAULT 0,
                updated TEXT,
                updated_date TEXT,
                updated_within_10_days INTEGER DEFAULT 0,
                author TEXT,
                content_exists INTEGER DEFAULT 0,
                summarize_status INTEGER DEFAULT 0,
                summarized_date TEXT,
                summary_attempts INTEGER DEFAULT 0,
                generated_html INTEGER DEFAULT 0
            )
        ''')

        # Check if the column already exists before adding it
        cursor.execute('PRAGMA table_info(LINKS)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'total_articles' not in columns:
            cursor.execute('''
                ALTER TABLE LINKS
                ADD COLUMN total_articles INTEGER DEFAULT 0
            ''')

        conn.commit()
        conn.close()

    def update_total_articles(self, feed_id, total_articles):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE LINKS
            SET total_articles = ?
            WHERE id = ?
        ''', (total_articles, feed_id))
        conn.commit()
        conn.close()
    
    def populate_metadata_table(self, dict_article):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()

        # Check if a row with the same id and id_article exists
        cursor.execute('''
            SELECT title
            FROM Metadata
            WHERE id = ? AND id_article = ?
        ''', (dict_article['id'], dict_article['id_article']))

        existing_title = cursor.fetchone()

        if existing_title and existing_title[0] == dict_article['title']:
            print(f"Title already exists. Skipping..\n---------------------")
            # return 1
        else:
            # Insert the new row
            cursor.execute('''
                INSERT INTO Metadata (id, id_article, title, guid, published, updated, author)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                dict_article['id'], dict_article['id_article'], dict_article['title'],
                dict_article['guid'], dict_article['published'], dict_article['updated'], dict_article['author']
            ))
            conn.commit()
            print("Metadata inserted successfully.\n---------------------")

        conn.close()
        # return 0

    def extract_date(self, feed_id, article_id, published, updated):
        print(f"Extracting date for id: {feed_id}, id_article: {article_id}...")
        date_formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # For 'Mon, 11 Sep 2023 16:03:00 +0000'
            '%a, %d %b %Y %H:%M:%S GMT' # For 'Mon, 11 Jul 2022 12:03:33 GMT'
        ]

        def parse_date(date_str):
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Date string {date_str} doesn't match any known format")

        try:
            conn = sqlite3.connect(self.db_filename)
            cursor = conn.cursor()
            
            if published:
                published_date = parse_date(published)
                published_date_only = published_date.date()
                value = 1 if self.is_date_within_last_10_days(published_date_only) else 0
                print(f"Within last 10 days: {value}")
                cursor.execute('''
                    UPDATE Metadata
                    SET published_date = ?, published_within_10_days = ?
                    WHERE id = ? AND id_article = ?
                ''', (str(published_date_only), value, feed_id, article_id))
                conn.commit()
            
            if updated and updated.lower() != 'none':
                updated_date = parse_date(updated)
                updated_date_only = updated_date.date()
                value = 1 if self.is_date_within_last_10_days(updated_date_only) else 0
                cursor.execute('''
                    UPDATE Metadata
                    SET updated_date = ?, updated_within_10_days = ?
                    WHERE id = ? AND id_article = ?
                ''', (str(updated_date_only), value, feed_id, article_id))
                conn.commit()

            conn.close()

        except Exception as e:
            print(f"An error occurred: {e}")

    def update_content_exists(self, feed_id, article_id):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Metadata
            SET content_exists = ?
            WHERE id = ? AND id_article = ?
            ''', (1, feed_id, article_id))
        conn.commit()
        conn.close()

    def is_date_within_last_10_days(self, date):
        # Convert the published date from a string to a datetime object
        # published_date = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z').date()

        # Calculate the difference between today's date and the published date
        difference = datetime.now().date() - date

        # Check if the difference is less than or equal to 10 days
        if difference.days <= 10:
            return True
        else:
            return False

    def does_content_exist(self):
        print("Checking if content exists for each article...")
        # Extract unique feed IDs from the LINKS table
        self.c.execute('SELECT DISTINCT id FROM LINKS')
        feed_ids = self.c.fetchall()
        # For each feed ID
        for feed_id in feed_ids[:]:
            feed_id = feed_id[0]  # Extract the integer value from the tuple

            # Read the JSON file
            feed_folder = os.path.join('dbs/raw_feeds', str(feed_id))
            feed_json_path = os.path.join(feed_folder, 'feed.json')
            # print(f"Reading {feed_json_path}...")

            try:
                # Read the JSON file
                with open(feed_json_path, 'r', encoding='utf-8') as json_file:
                    json_data = json.load(json_file)

                # Iterate through each article in the JSON data
                for entry in json_data:
                    article_id = entry.get('id_article')
                    content = entry.get('content')
                    published = entry.get('published')
                    updated = entry.get('updated')
                    # print(f"published: {published}")
                    if content is not None:
                        # print(f"Content exists for feed_id {feed_id} and article_id {article_id}")
                        self.update_content_exists(feed_id, article_id)
                        self.extract_date(feed_id, article_id, published, updated)
            
            except FileNotFoundError:
                print(f"JSON file not found for feed_id {feed_id}. Skipping...")

    def fetch_feed_entries_and_store_to_json(self, attributes_to_keep):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute("SELECT id, feed FROM LINKS")
        feed_data = cursor.fetchall()

        print("Fetching feed entries from the database...")
        for idx_feed, (feed_id, url) in enumerate(feed_data[:], start=1):
            print(f"\n#{idx_feed}: Fetching entries from {url}")
            try:
                feed = feedparser.parse(url)
            except Exception as e:
                print(f"Error parsing feed for {url}: {e}")
                continue

            articles_count = len(feed.entries)  # Count of articles for this feed
            print(f"Total Articles: {articles_count}")
            self.articles_count.append(articles_count)  # Store for later use
            # print(f"\nself.articles_count: {self.articles_count}")

            # Update total articles in LINKS table
            self.update_total_articles(idx_feed, articles_count)

            # Create a list to store JSON entries
            json_entries = []

            for article_idx, entry in enumerate(feed.entries, start=1):
                # Create a new dictionary with only the desired attributes
                selected_attributes = {attr: entry[attr] for attr in attributes_to_keep if attr in entry}
                selected_attributes['id'] = idx_feed
                selected_attributes['id_article'] = article_idx

                if 'updated' not in selected_attributes:
                    selected_attributes['updated'] = 'None'
                if 'author' not in selected_attributes:
                    selected_attributes['author'] = 'None'
                
                json_entries.append(selected_attributes)
                
                # Populate the Metadata table with the selected attributes
                self.populate_metadata_table(selected_attributes)

            # Write the JSON data to a file
            feed_folder = os.path.join('dbs/raw_feeds', str(feed_id))
            os.makedirs(feed_folder, exist_ok=True)
            feed_json_path = os.path.join(feed_folder, 'feed.json')
            with open(feed_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(json_entries, json_file, indent=4)

            print(f"{feed_json_path} saved successfully.")

        # Close the database connection
        conn.close()

        print("\n---------------------\nAll feed entries completed.\n---------------------\n")

if __name__ == "__main__":
    generator = GetArticlesMetadata(db_filename='dbs/rss_sum.db')
    attributes_to_keep = ['title', 'guid', 'published', 'updated', 'author', 'content']
    generator.fetch_feed_entries_and_store_to_json(attributes_to_keep)
    generator.does_content_exist()