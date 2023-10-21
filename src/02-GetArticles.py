import os
import feedparser
import sqlite3
import json
import datetime
from util import get_filepath
class GetArticles:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()
        self.feed_parse_counter = 0
        self.articles_count = 0
        self.content_exist_counter = 0
        self.entries = []
        self.dict_entries = []
        self.create_metadata_table()
        self.has_printed = False

    def create_metadata_table(self):
        self.c.execute('''
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
        self.c.execute('PRAGMA table_info(LINKS)')
        columns = [column[1] for column in self.c.fetchall()]
        if 'total_articles' not in columns:
            self.c.execute('''
                ALTER TABLE LINKS
                ADD COLUMN total_articles INTEGER DEFAULT 0
            ''')
        self.conn.commit()

    def update_total_articles(self, feed_id, total_articles):
        self.c.execute('''
            UPDATE LINKS
            SET total_articles = ?
            WHERE id = ?
        ''', (total_articles, feed_id))
        self.conn.commit()

    def populate_metadata_table(self, dict_article, published_date, updated_date):
        # Check if a row with the same id and title exists
        # we do not compare article_id because articles might repeat with a different article_id
        self.c.execute('''
            SELECT title
            FROM Metadata
            WHERE id = ? AND title = ?
        ''', (dict_article['id'], dict_article['title']))

        existing_article_id = self.c.fetchone()

        if existing_article_id:
            # print(f"Article with id {dict_article['id']} and title {dict_article['title']} already exists.")
            pass
        else:
            # Insert the new row
            self.c.execute('''
                INSERT INTO Metadata (id, id_article, title, guid, published, updated, author, published_date, updated_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                dict_article['id'], dict_article['id_article'], dict_article['title'],
                dict_article['guid'], dict_article['published'], dict_article['updated'], dict_article['author'],
                str(published_date), str(updated_date)
            ))
            self.conn.commit()
            # print(f"dict_article feed id: {dict_article['id']}, article id: {dict_article['id_article']}")
            # print(f"\nMetadata inserted successfully.")

    def extract_date(self, published, updated):
        if not self.has_printed:
            print(f"\nExtracting dates and filtering...")
            self.has_printed = True
        date_formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # For 'Mon, 11 Sep 2023 16:03:00 +0000'
            '%a, %d %b %Y %H:%M:%S GMT' # For 'Mon, 11 Jul 2022 12:03:33 GMT'
        ]

        def parse_date(date_str):
            for fmt in date_formats:
                try:
                    return datetime.datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Date string {date_str} doesn't match any known format")

        published_value, updated_value = 0, 0
        published_date_only, updated_date_only = None, None
        if published:
            published_date = parse_date(published)
            published_date_only = published_date.date()
            # print(f"published_date_only: {published_date_only}")
            published_value = 1 if self.is_date_within_last_10_days(published_date_only) else 0
            # print(f"Within last 10 days: {value}")
        
        if updated and updated.lower() != 'none':
            updated_date = parse_date(updated)
            updated_date_only = updated_date.date()
            # print(f"updated_date_only: {updated_date_only}")
            updated_value = 1 if self.is_date_within_last_10_days(updated_date_only) else 0

        # print(f"Extracted dates for feed_id {feed_id} and article_id {article_id}")
        return published_value, updated_value, published_date_only, updated_date_only

    def update_content_exists(self, feed_id, article_id):
        self.c.execute('''
            UPDATE Metadata
            SET content_exists = ?
            WHERE id = ? AND id_article = ?
            ''', (1, feed_id, article_id))
        self.conn.commit()

    def is_date_within_last_10_days(self, date):
        # Convert the published date from a string to a datetime object
        # published_date = datetime.datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z').date()

        # Calculate the difference between today's date and the published date
        difference = datetime.datetime.now().date() - date

        # Check if the difference is less than or equal to 10 days
        if difference.days <= 10:
            return True
        else:
            return False

    def fetch_and_filter(self, attributes_to_keep):
        self.c.execute("SELECT id, feed FROM LINKS")
        feed_data = self.c.fetchall()

        counter = 0
        print("\nFetching feed entries for the feeds in the database...")
        for feed_id, url in feed_data:
            # if counter >= 3:
            #     break 
            folder_counter = 0
            # print(f"\n#{feed_id}: Fetching entries from {url}")
            try:
                feed = feedparser.parse(url)
                self.feed_parse_counter += 1
            except Exception as e:
                # print(f"Error parsing feed for {url}: {e}")
                continue

            articles_count = len(feed.entries)  # Count of articles for this feed
            # print(f"Total Articles: {articles_count}")
            self.articles_count += articles_count
            # print(f"\nself.articles_count: {self.articles_count}")

            # Update total articles fetched for today in LINKS table
            self.update_total_articles(feed_id, articles_count)

            # Create a list to store JSON entries
            json_entries = []

            # Execute an SQL query to select distinct article_id values for the specified feed_id
            self.c.execute('''
                SELECT DISTINCT id_article
                FROM Metadata
                WHERE id = ?
            ''', (feed_id,))

            # Fetch the distinct article_id values as a list
            distinct_article_ids = [row[0] for row in self.c.fetchall()]

            if len(distinct_article_ids) == 0:
                # print(f"No articles found for feed_id {feed_id}.")
                new_unique_article_id = 1
            else:
                # print(f"Found {len(distinct_article_ids)} articles for feed_id {feed_id}.")
                new_unique_article_id = distinct_article_ids[-1] + 1 # this ensures that the new article_id is unique

            for entry in feed.entries:
                # print(f"Processing article #{new_unique_article_id}...")
                # Create a new dictionary with only the desired attributes
                selected_attributes = {attr: entry[attr] for attr in attributes_to_keep if attr in entry}
                selected_attributes['id'] = feed_id
                selected_attributes['id_article'] = new_unique_article_id 
                # print(f"Selected attributes feed id: {selected_attributes['id']}, article id: {selected_attributes['id_article']} -------")
                

                if 'content' not in selected_attributes:
                    continue
                if 'published' not in selected_attributes:
                    continue
                if 'updated' not in selected_attributes:
                    selected_attributes['updated'] = 'None'
                if 'author' not in selected_attributes:
                    selected_attributes['author'] = 'None'

                published_value, updated_value, published_date, updated_date = self.extract_date(selected_attributes['published'], selected_attributes['updated'])    
                if published_value == 0:
                    # print(f"Skipping article #{selected_attributes['id_article']} because it is not within the last 10 days.")
                    continue

                new_unique_article_id += 1
                # if selected_attributes['content']:
                self.content_exist_counter += 1
                folder_counter += 1
                # print(f"Content exists within the last 10 days for feed_id {feed_id} and article_id {new_unique_article_id} --  article id: {selected_attributes['id_article']}")
                json_entries.append(selected_attributes)
                # print(f"Selected attributes feed id: {selected_attributes['id']}, article id: {selected_attributes['id_article']} XXXXXXXX")
                self.populate_metadata_table(selected_attributes, published_date, updated_date)
                # self.update_content_exists(selected_attributes['id'], selected_attributes['id_article'])

            if folder_counter > 0:
                # Write the JSON data to a file
                feed_folder = os.path.join('dbs/raw_feeds', str(feed_id))
                os.makedirs(feed_folder, exist_ok=True)
                feed_json_path = os.path.join(feed_folder, 'feed.json')
                with open(feed_json_path, 'w', encoding='utf-8') as json_file:
                    json.dump(json_entries, json_file, indent=4)

                # print(f"{feed_json_path} saved successfully.")

        print("\nAll feeds completed.\n")

if __name__ == "__main__":

    today_date = datetime.datetime.today().strftime('%Y-%m-%d')
    json_status_file_name = get_filepath('status.json')

    try:
        with open(json_status_file_name, 'r') as f:
            existing_status = json.load(f)

        # default status
        status_data = {
                'status': 'Did not run',
                'message': 'if elif conditions not met, check code'
            }
        
        if today_date in existing_status and 'RSSFeedScraper' in existing_status[today_date] and existing_status[today_date]['RSSFeedScraper']['status'] == 'Failed':
            status_data = {
                'status': 'Failed',
                'message': 'RSSFeedScraper failed so this has not run'
            }

        elif today_date in existing_status and 'RSSFeedScraper' in existing_status[today_date] and existing_status[today_date]['RSSFeedScraper']['status'] == 'Success':
            try:
                db_path = get_filepath('dbs/rss_sum.db')
                generator = GetArticles(db_filename=db_path)
                attributes_to_keep = ['title', 'guid', 'published', 'updated', 'author', 'content']
                generator.fetch_and_filter(attributes_to_keep)
                generator.conn.close()
                status_data = {
                    'status': 'Success',
                    'feeds_processed': generator.feed_parse_counter,
                    'articles_processed': generator.articles_count,
                    'articles_with_content_within_last_10_days': generator.content_exist_counter
                }
            except Exception as e:
                status_data = {
                    'status': 'Failed',
                    'message': str(e)
                }

        existing_status[today_date]['GetArticles'] = status_data

        with open(json_status_file_name, 'w') as f:
            json.dump(existing_status, f, indent=4)
    
    except FileNotFoundError:
        print(f"FileNotFoundError: {json_status_file_name} not found.")