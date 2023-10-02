import sqlite3
import os
from dotenv import load_dotenv # to load env variables
import json
import openai
from datetime import datetime
from bs4 import BeautifulSoup
from util import get_filepath

load_dotenv()
openai.api_key  = os.getenv('OPENAI_API_KEY')
# openai.Model.list()
class SummarizeArticles:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()
    
    def update_summarize_status(self, feed_id, article_id, number):
        self.c.execute('''
            UPDATE Metadata
            SET summarize_status = ?
            WHERE id = ? AND id_article = ?
            ''', (number, feed_id, article_id))
        self.conn.commit()

    def update_summarized_date(self, feed_id, article_id):
        today_date = str(datetime.today().strftime('%Y-%m-%d'))
        # print(f"Today's date: {today_date}")
        self.c.execute('''
            UPDATE Metadata
            SET summarized_date = ?
            WHERE id = ? AND id_article = ? AND summarize_status = ?
            ''', (str(today_date), feed_id, article_id, 1))
        self.conn.commit()

    def api_call(self, content):
        # API call to summarize the content
        # MODEL = "gpt-3.5-turbo"
        MODEL = "gpt-3.5-turbo-16k"
        # MODEL = "gpt-4"
        # MODEL = "gpt-4-32k"
        openai.Model.list()
        try:
            response = openai.ChatCompletion.create(
                model=MODEL,
                messages=[
                            {
                                "role": "system", 
                                "content": """
                                Generate a concise, entity-dense summary of the given article, following these steps:
                                1. Read the article and identify the most important entities.
                                2. Write a dense summary, keeping it approximately 200 words long.

                                Guidelines & Characteristics of the summary:
                                - Relevant to the main article.
                                - True to the article's content.
                                - Make sure your summaries are self-contained and clear without needing the article.
                                - Ensure the summary does not contain any irrelevant content, information or characters.
                                """
                            },
                            {"role": "user", "content": f"This is the article that you have to summarize: {content}"}
                        ],
                temperature=0,
                request_timeout=30
            )
                                # 3. If the content I feed to you is not an article and is instead an update on logistics, DO NOT SUMMARIZE IT. Just print "Not relevant".
                                # 4. Double check that you don't wrongly misclassify an article as an update on logistics.
            summary = response["choices"][0]["message"]["content"]
            # print(f"Summary: \n{summary}\n")
            number = 1
            if "not relevant" in summary.lower():
                number = 2
        except openai.error.InvalidRequestError as e:
            if "maximum context length" in str(e):
                summary = "The article is too lengthy to be summarized."
                number = 3
            else:
                summary = "An error occurred while summarizing the article."
                number = 4
        except openai.error.Timeout as e:
            summary = "The API call timed out. Handle this as needed."
            number = 5
        return summary, number

    def add_summary_to_json(self, feed_id, article_id, summary, file_path):
        
        # Check if the file already exists
        if os.path.exists(file_path):
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)
        else:
            data = []

        # Append the new summary data to the list
        data.append({
            "feed_id": feed_id,
            "article_id": article_id,
            "summary": summary
        })

        # Save the updated list back to the file
        with open(file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)

    def process_content(self, feed_id, id_article):
        # Read the JSON file
        feed_folder = os.path.join('dbs/raw_feeds', str(feed_id))
        feed_json_path = os.path.join(feed_folder, 'feed.json')
        # In json file,im 
        with open(feed_json_path, 'r', encoding='utf-8') as json_file:
            json_data = json.load(json_file)

        article_entry = None
        # For each entry (article) in the json file
        for entry in json_data:
            if entry.get('id_article') == id_article:
                article_entry = entry
                break
        
        # If article entry exists
        if article_entry is not None:

            # Extract information from the article entry
            title = article_entry['title']
            content = article_entry['content'][0]['value']

            # Use BeautifulSoup to parse HTML and extract text
            # soup = BeautifulSoup(content, 'html.parser')
            # parsed_content = soup.get_text()
            # print(f"Content: \n{parsed_content}\n------------------\n")
            
            # print(f"Processing content for id: {feed_id}, id_article: {id_article}")
            # print(f"Title: {title}")
            # print(f"Content: \n{content}")
            
            # Call the API to summarize the content
            summary, number = self.api_call(content)
            # print(f"Summary: \n{summary}\n------------------\n")
            # print(f"Summary status: {number}\n------------------\n")
            # Update the Metadata table with the summary
            self.update_summarize_status(feed_id, id_article, number)
            self.update_summarized_date(feed_id, id_article)

            # Find the last occurrence of a full stop in the summary
            # last_full_stop_index = summary.rfind('.')
            # if last_full_stop_index != -1:
            #     # Remove everything after the last full stop
            #     summary = summary[:last_full_stop_index+1]

            # Create directories if they don't exist
            if not os.path.exists('docs'):
                os.mkdir('docs')
            summary_path = os.path.join('docs', 'summaries.json')
            self.add_summary_to_json(feed_id, id_article, summary, summary_path)

            # Update the JSON with the summary
            article_entry['summary'] = summary

            self.c.execute('''
                UPDATE Metadata
                SET summary_attempts = summary_attempts + 1
                WHERE id = ? AND id_article = ?
            ''', (feed_id, id_article))
            self.conn.commit()

            # Extract published_date from sqlite db into json
            self.c.execute('''
                SELECT published
                FROM Metadata
                WHERE id = ? AND id_article = ?
            ''', (feed_id, id_article))
            published_date = self.c.fetchone()
            article_entry['published'] = published_date[0]

            with open(feed_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)

        else:
            print(f"No matching article found for id: {feed_id}, id_article: {id_article}")

    def check_if_content_exists(self):
        # For each unique feed
        self.c.execute('SELECT DISTINCT id FROM LINKS')
        feed_ids = self.c.fetchall()

        for feed_id in feed_ids[:75]:
            feed_id = feed_id[0]  # Extract the integer value from the tuple
            # Select all articles for that specific feed
            self.c.execute('''
                SELECT id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days
                FROM Metadata
                WHERE id = ?
            ''', (feed_id,))
            rows = self.c.fetchall()
            for row in rows[:]:
                id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days = row
                # print(f"summary_status: {summarize_status}")
                # check if content exists
                if content_exists == 0:
                    # print(f"No content for id: {feed_id}, id_article: {id_article}, skipping...")
                    continue
                elif content_exists == 1:
                    # If published within 10 days
                    if published_within_10_days == 1: # add check with or 0 to test
                        # If summary doesn't exist, or failed previously (status 4 or 5)
                        if summarize_status == 0 or summarize_status == 4 or summarize_status == 5:
                            # If summary_attempts is less than 2
                            if summary_attempts <= 3:
                                print(f"Parsing content for id: {feed_id}, id_article: {id_article}")
                                self.process_content(feed_id, id_article)
                            else:
                                print(f"Summary attempts exceeded for id: {feed_id}, id_article: {id_article}, skipping...")
                        elif summarize_status == 1:
                            print(f"Summary exists for id: {feed_id}, id_article: {id_article}, skipping...")
                        elif summarize_status == 2:
                            print(f"Summary is not relevant for id: {feed_id}, id_article: {id_article}, skipping...")
                        elif summarize_status == 3:
                            print(f"Summary is too long for id: {feed_id}, id_article: {id_article}, skipping...")
        self.c.close()

if __name__ == '__main__':
    db_path = get_filepath('dbs/rss_sum.db')
    get_articles_metadata = SummarizeArticles(db_path)
    get_articles_metadata.check_if_content_exists()