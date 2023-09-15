# import os
# import sqlite3

# db_filename = os.path.join('dbs', 'rss_sum.db')  # Replace with your actual database filename

# def print_table_info(conn):
#     cursor = conn.cursor()
#     cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
#     table_names = cursor.fetchall()
    
#     for table in table_names:
#         table_name = table[0]
#         print(f"Table: {table_name}")
        
#         cursor.execute(f"PRAGMA table_info({table_name});")
#         columns = cursor.fetchall()
#         for column in columns:
#             column_name = column[1]
#             print(f"    Column: {column_name}")
    
#     print("\n")

# try:
#     conn = sqlite3.connect(db_filename)
#     print("Connected to the database.")
    
#     print_table_info(conn)
    
# except sqlite3.Error as e:
#     print("Error connecting to the database:", e)
# finally:
#     if conn:
#         conn.close()
#         print("Connection to the database closed.")

# from datetime import datetime
import os
import feedparser
import sqlite3
# from urllib.parse import urlparse
# from xml.etree import ElementTree as ET
import json
# import xml.dom.minidom
# import time

class GetArticlesMetadata:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        # self.output_filename = output_filename
        self.articles_count = []
        self.entries = []
        self.dict_entries = []
        self.create_metadata_table()

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
                updated TEXT,
                author TEXT,
                content_exists INTEGER DEFAULT 0,
                summary_exists INTEGER DEFAULT 0
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

    def fetch_feed_entries_and_store_to_json(self, attributes_to_keep):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute("SELECT id, feed FROM LINKS")
        feed_data = cursor.fetchall()

        print("Fetching feed entries from the database...")
        for idx_feed, (feed_id, url) in enumerate(feed_data[:3], start=1):
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
                # if updated not in
                if 'updated' not in selected_attributes:
                    selected_attributes['updated'] = 'None'
                
                json_entries.append(selected_attributes)
                
                # Check if a specific attribute exists in the entry dictionary
                if 'content' in entry:
                    print(f"Content exists for id: {idx_feed}, id_article: {article_idx}")
                    self.update_content_exists(idx_feed, article_idx)
                else:
                    print(f"No content found for feed: {idx_feed}, article #: {article_idx}")

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

        print("All feed entries completed.\n---------------------")


if __name__ == "__main__":
    generator = GetArticlesMetadata(db_filename='dbs/rss_sum.db')
    attributes_to_keep = ['title', 'guid', 'published', 'updated', 'author', 'content']
    generator.fetch_feed_entries_and_store_to_json(attributes_to_keep)


















    # Old code stored for reference of feed output type

    # # Create a dictionary of default values for missing attributes
    # default_values = {
    #     'id': '',
    #     'id_article': '',  # Not from entry, for-loop index
    #     'guid': '',
    #     'published': '',
    #     'published_parsed': '',
    #     'updated': '',
    #     'updated_parsed': '',
    #     'title': '',
    #     'title_detail': {'type': 'text/plain', 'language': None, 'base': '', 'value': ''},
    #     'summary': '',
    #     'summary_detail': {'type': 'text/html', 'language': None, 'base': '', 'value': ''},
    #     'links': [],
    #     'link': '',
    #     'authors': [],
    #     'author': '',
    #     'author_detail': {'name': '', 'email': ''},
    #     'content': None
    #     # 'content': [{
    #     #     'type': '',
    #     #     'language': '',
    #     #     'base': '',
    #     #     'value': ''}]
    # }

    # # Add default values to missing attributes
    # for attr, default_value in default_values.items():
    #     entry[attr] = entry.get(attr, default_value)
    
    # # Create XML elements for the current entry
    # article_element = ET.SubElement(root, 'article')

    # # First 2 are not from entry, they are from the for loops
    # ET.SubElement(article_element, 'id').text = str(idx_feed)  
    # ET.SubElement(article_element, 'id_article').text = str(article_idx) 

    # # Following are from entry
    # ET.SubElement(article_element, 'guid').text = entry['id'] # string
    # ET.SubElement(article_element, 'published').text = entry['published'] # string
    # # ET.SubElement(article_element, 'published_parsed').text = time.strftime('%Y-%m-%d %H:%M:%S', entry['published_parsed']) # Convert struct_time to string
    # ET.SubElement(article_element, 'updated').text = entry['updated'] # string
    # # ET.SubElement(article_element, 'updated_parsed').text = time.strftime('%Y-%m-%d %H:%M:%S', entry['updated_parsed']) # Convert struct_time to string
    # ET.SubElement(article_element, 'title').text = entry['title'] # string
    # # ET.SubElement(article_element, 'title_detail').text = entry['title_detail'] # dict
    # # ET.SubElement(article_element, 'summary').text = entry['summary'] #string
    # # ET.SubElement(article_element, 'summary_detail').text = entry['summary_detail'] # dict
    # # ET.SubElement(article_element, 'links').text = entry['links'] # list
    # ET.SubElement(article_element, 'link').text = entry['link'] # string
    # # ET.SubElement(article_element, 'authors').text = entry['authors'] # list
    # ET.SubElement(article_element, 'author').text = entry['author'] # string
    # # ET.SubElement(article_element, 'author_detail').text = entry['author_detail'] # dict
    # # ET.SubElement(article_element, 'media_thumbnail').text = entry['media_thumbnail'] # list