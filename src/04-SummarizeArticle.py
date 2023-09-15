import sqlite3
import os
from dotenv import load_dotenv # to load env variables
import json
import openai
from datetime import datetime

load_dotenv()
openai.api_key  = os.getenv('OPENAI_API_KEY')

class SummarizeArticles:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()
    
    def update_summarize_status(self, feed_id, article_id, number):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Metadata
            SET summarize_status = ?
            WHERE id = ? AND id_article = ?
            ''', (number, feed_id, article_id))
        conn.commit()
        conn.close()

    def update_summarized_date(self, feed_id, article_id):
        today_date = str(datetime.today().strftime('%Y-%m-%d'))
        # print(f"Today's date: {today_date}")
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Metadata
            SET summarized_date = ?
            WHERE id = ? AND id_article = ? AND summarize_status = ?
            ''', (str(today_date), feed_id, article_id, 1))
        conn.commit()
        conn.close()

    def api_call(self, content):
        # API call to summarize the content
        MODEL = "gpt-3.5-turbo"
        timeout = 15  # in seconds
        # use the model with longer context window
        try:
            response = openai.ChatCompletion.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a friendly and helpful assistant. Your job is to parse the input html content and summarize it and give it back in plain human readable text. When you summarize, make sure to not repeat yourself. Be concise and to the point. Always maintain the overall context of the article when summarizing. I want a maximum of 4-5 sentences as the summary."},
                    {"role": "system", "content": "When you process the content, you will probably have one of the following outcomes: 0 - No relevant article in the content given. 1 - successfully summarized given content. You have to attach a 0 or 1 at the end of your response depending on which case it is."},
                    # {"role": "system", "content": "For case 0, you need not summarize anything. For case 1, you have to summarize in the requested manner. For case 2, you have to return the hyperlink with the attached number. "},
                    {"role": "system", "content": "I will extract this number by using str(response['choices'][0]['message']['content'])[-1]."},
                    {"role": "system", "content": "You also have to double check your response because sometimes the relevant article may contain a link, you should not wrongly classify the case."},
                    {"role": "system", "content": "Example on how to attach the number at the end of the response for 2 cases: Case 0 - 'No relevant article. 0'; Case 1 - '<full summary>. 1"},
                    {"role": "system", "content": "Ensure there are no extra characters after the number by verifying if the following code extracts the number: number = str(response['choices'][0]['message']['content'])[-1]"},
                    {"role": "user", "content": f"This is the article that you have to summarize {content}"}
                ],
                temperature=0,
            )
            summary = response["choices"][0]["message"]["content"]
        except openai.error.InvalidRequestError as e:
            if "maximum context length" in str(e):
                summary = "The article is too lengthy to be summarized. 2"
            else:
                summary = "An error occurred while summarizing the article. 3"
        except openai.error.TimeoutError as e:
            summary = "The API call timed out. Handle this as needed. 4"
        
        return summary

    def process_content(self, feed_id, id_article):
        # Read the JSON file
        feed_folder = os.path.join('dbs/raw_feeds', str(feed_id))
        feed_json_path = os.path.join(feed_folder, 'feed.json')
        # In json file,
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

            print(f"Processing content for id: {feed_id}, id_article: {id_article}")
            # print(f"Title: {title}")
            # print(f"Content: \n{content}")

            # Call the API to summarize the content
            summary = self.api_call(content)
            # print(f"Summary: \n{summary}\n------------------\n")

            number = str(summary)[-1]
            # print(f"number: {number}")
            # Update the Metadata table with the summary
            self.update_summarize_status(feed_id, id_article, number)
            # if number == '1':
            # If this date exists, it means that the article was attempted to be summarized today
            self.update_summarized_date(feed_id, id_article)

            # Find the last occurrence of a full stop in the summary
            last_full_stop_index = summary.rfind('.')

            # Check if a full stop was found
            if last_full_stop_index != -1:
                # Remove everything after the last full stop
                summary = summary[:last_full_stop_index+1]

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

        for feed_id in feed_ids[:]:
            feed_id = feed_id[0]  # Extract the integer value from the tuple
            # Select all articles for that specific feed
            self.c.execute('''
                SELECT id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days
                FROM Metadata
                WHERE id = ?
            ''', (feed_id,))
            rows = self.c.fetchall()
            # for each feed, for each article, check if content exists
            # if content exists, check if summary exists before summarizing
            # if summary exists, skip
            # if summary does not exist, summarize
            for row in rows[:]:
                id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days = row
                # print(f"summary_status: {summarize_status}")
                # check if content exists
                if content_exists == 0:
                    print(f"No content for id: {feed_id}, id_article: {id_article}, skipping...")
                elif content_exists == 1:
                    # Uncomment this to filter last 10 days
                    if published_within_10_days == 1 or updated_within_10_days == 1:

                        # check if summary exists
                        if summarize_status == 0 or summarize_status == 3:       
                            # print(f"Summary status {summarize_status} for id: {feed_id}, id_article: {id_article}, processing...")

                            if summary_attempts <= 2:
                                self.process_content(feed_id, id_article)
                            else:
                                print(f"Summary attempts exceeded for id: {feed_id}, id_article: {id_article}, skipping...")
                        elif summarize_status == 1:
                            print(f"Summary exists for id: {feed_id}, id_article: {id_article}, skipping...")
                            # print(f"Checking if it was updated today...")
                            # self.check_date(published, updated, summarized_date)
                            # if result == 1:
                            #     print(f"Yes, it was updated. Processing...")
                            #     self.process_content(feed_id, id_article)
                            # else:
                            #     print(f"No, it was not updated. Skipping...")

        self.c.close()

if __name__ == '__main__':
    db_filename = 'dbs/rss_sum.db'
    get_articles_metadata = SummarizeArticles(db_filename)
    get_articles_metadata.check_if_content_exists()
