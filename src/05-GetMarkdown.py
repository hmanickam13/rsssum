import os
from dotenv import load_dotenv # to load env variables
import json
import sqlite3
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import datetime
import requests
# from datetime import datetime
import shutil
from util import get_filepath

load_dotenv()
SENDGRID_API_KEY  = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL')
TO_EMAIL = os.getenv('TO_EMAIL')

class GenerateMarkdown:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()
        # self.create_newsletter_table()
        self.articles_to_extract = []
        self.summary_status_1 = 0
        self.summary_status_2 = 0
        self.summary_status_3 = 0
        self.summary_status_4 = 0
        self.summary_status_5 = 0

    def create_newsletter_table(self):
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS Newsletter (
                id INTEGER,
                id_article INTEGER,
                published TEXT,
                updated TEXT,
                latest_mailing_timestamp TEXT              
           )
        ''')
        self.conn.commit()

    def populate_newsletter_table(self, dict_article):
        # Check if a row with the same id and id_article exists
        self.c.execute('''
            SELECT title
            FROM Newsletter
            WHERE id = ? AND id_article = ?
        ''', (dict_article['id'], dict_article['id_article']))

        current_tmsp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing_row = self.c.fetchone()

        if existing_row:
            print("Row already exists. Skipping...\n---------------------")
        else:
            # Insert the new row
            self.c.execute('''
                INSERT INTO Newsletter (id, id_article, published, updated, latest_mailing_timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dict_article['id'], dict_article['id_article'], dict_article['published'],
                dict_article['updated'], current_tmsp
            ))
            self.conn.commit()
            print("Newsletter data inserted successfully.\n---------------------")

    def update_generated_html(self, feed_id, article_id, number):
        self.c.execute('''
            UPDATE Metadata
            SET generated_html = ?
            WHERE id = ? AND id_article = ?
            ''', (number, feed_id, article_id))
        self.conn.commit()

    def generate_markdown(self, output_dir):
        self.c.execute("SELECT id FROM LINKS")
        feed_ids = [row[0] for row in self.c.fetchall()]

        for feed_id in feed_ids:
            feed_folder = os.path.join(output_dir, 'dbs/raw_feeds', str(feed_id))
            feed_json_path = os.path.join(feed_folder, 'feed.json')

            if not os.path.exists(feed_json_path):
                print(f"JSON file not found for feed {feed_id}. Skipping...")
                continue

            with open(feed_json_path, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)

            markdown_content = ""
            for entry in json_data:
                self.c.execute('''
                    SELECT summarize_status
                    FROM Metadata
                    WHERE id = ? AND id_article = ?
                ''', (entry['id'], entry['id_article']))
                summary_status = self.c.fetchone()
                print(f"summary_status: {summary_status}")

                if summary_status[0] == 0 or summary_status[0] == 2:
                    print(f"Summary does not exist for feed {feed_id}, article {entry['id_article']}. Skipping...")
                elif summary_status[0] == 1:
                    print(f"Summary exists for feed {feed_id}, article {entry['id_article']}. Adding to Markdown...")
                    # Customize the subset of variables you want in the Markdown
                    markdown_content += f"# {entry['title']}\n\n"
                    markdown_content += f"**Published:** {entry['published']}\n"
                    markdown_content += f"**Author:** {entry['author']}\n\n"
                    # markdown_content += f"**Content:** {entry['Content']}\n\n"
                    markdown_content += f"**Summary:** {entry['summary']}\n\n"
                    # markdown_content += f"{metadata[0]}\n\n"
                    markdown_content += "---\n\n"
                
            markdown_file_path = os.path.join(feed_folder, 'feed.md')
            with open(markdown_file_path, 'w', encoding='utf-8') as markdown_file:
                markdown_file.write(markdown_content)

            print(f"Markdown file for feed {feed_id} created: {markdown_file_path}")

    def generate_html(self):
        # Specific feed and article pairs to be extracted
        specific_articles = self.articles_to_extract

        html_content = ""  # Initialize html_content outside the loop
        base_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Feed Summary</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333366; }}
                p {{ margin: 10px 0; }}
                hr {{ border: 0; height: 1px; background-color: #ddd; margin: 20px 0; }}
                .article {{ margin-bottom: 20px; }}
                .link {{ color: #0066cc; text-decoration: none; }}
            </style>
        </head>
        <body>
            {content}
        </body>
        </html>
        """

        for feed_id, article_id in specific_articles[:]:
            feed_folder = os.path.join('dbs/raw_feeds', str(feed_id))
            feed_json_path = os.path.join(feed_folder, 'feed.json')

            if not os.path.exists(feed_json_path):
                print(f"JSON file not found for feed {feed_id}. Skipping...")
                continue

            with open(feed_json_path, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)

            for entry in json_data:
                if entry['id'] == feed_id and entry['id_article'] == article_id:
                    print(f"entry attributes: {entry.keys()} for feed {feed_id}, article {article_id}")
                    article_html = """
                    <div class="article">
                        <h1>{title}</h1>
                        <p><strong>Link:</strong> <a href="{guid}" class="link" target="_blank">{guid}</a></p>
                        <p><strong>Summary:</strong> {summary}</p>
                        <hr>
                    </div>
                    """.format(title=entry['title'], guid=entry['guid'], summary=entry['summary'])
                    
                    html_content += article_html

        # Inject the accumulated content into the base HTML
        final_html = base_html.format(content=html_content)

        # current_directory = os.getcwd()
        # parent_directory = os.path.dirname(current_directory)
        # os.chdir(parent_directory)

        # Create directories if they don't exist
        if not os.path.exists('docs'):
            os.mkdir('docs')
        if not os.path.exists('docs/oldhtmls'):
            os.mkdir('docs/oldhtmls')

        # Before writing the new file, check and move the old one if it exists
        today = datetime.datetime.today().strftime('%Y-%m-%d')
        combined_html_file_path = os.path.join('docs', f'{today}.html')
        if os.path.exists(combined_html_file_path):
            old_html_destination = os.path.join('docs', 'oldhtmls', f'{today}.html')
            shutil.move(combined_html_file_path, old_html_destination)
            print(f"Old HTML file moved to: {old_html_destination}")

        with open(combined_html_file_path, 'w', encoding='utf-8') as html_file:
            html_file.write(final_html)

        print(f"HTML file with combined articles created: {combined_html_file_path}")
        # print full path of combined html file
        print("Combined html file path:", os.path.abspath(combined_html_file_path))
        # print full cwd path
        print("Current working directory:", os.getcwd())

    def gpost(self,txt):
        chat_url = "https://chat.googleapis.com/v1/spaces/AAAA96mzfGA/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=Vw0dOFogbncJTJhKf8rhvI6KVqAVRw0z_bEYSZRaxmY"
        data = {
                'text': txt
               }
        headers = {
                    'Content-Type': 'application/json'
                  }

        response = requests.post(chat_url, json=data, headers=headers)

        # Check for successful response
        if response.status_code == 200:
            print("Message sent successfully")
        else:
            print(f"Error sending message: {response.status_code} - {response.text}")

    def find_statistics(self):
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
            for row in rows[:]:
                id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days = row
                if published_within_10_days == 1 and content_exists == 1: # change published_within_10_days to 0 to test
                    if summarize_status == 1:
                        self.summary_status_1 += 1
                        self.articles_to_extract.append((feed_id, id_article))
                        # print(f"Set: {feed_id}, {id_article}")
                    elif summarize_status == 2:
                        self.summary_status_2 += 1
                    elif summarize_status == 3:
                        self.summary_status_3 += 1
                    elif summarize_status == 4:
                        self.summary_status_4 += 1
                    elif summarize_status == 5:
                        self.summary_status_5 += 1

        self.c.close()

        print(f"articles to extract: {self.articles_to_extract}\n")
        
        print(f"Summary status 1: {self.summary_status_1}")
        print(f"Summary status 2: {self.summary_status_2}")
        print(f"Summary status 3: {self.summary_status_3}")
        print(f"Summary status 4: {self.summary_status_4}")
        print(f"Summary status 5: {self.summary_status_5}")
        print(f"Sending summary statistics to google chat...")
        message_text = f"""Summary Stats for today, {datetime.datetime.now().strftime("%Y-%m-%d")} :

Successfully summarized : {self.summary_status_1}
Not relevant            : {self.summary_status_2}
Exceeded token limit    : {self.summary_status_3}
Failed to summarize     : {self.summary_status_4}
API Request timeout     : {self.summary_status_5}
Link to combined html feed: <link will be inserted>"""
        self.gpost(message_text)

    def send_email(self, output_dir):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM LINKS")
        feed_ids = [row[0] for row in cursor.fetchall()]

        for feed_id in feed_ids[5:7]:
            
            feed_folder = os.path.join(output_dir, 'dbs/raw_feeds', str(feed_id))
            html_file_path = os.path.join(feed_folder, 'feed.html')
            
            if html_file_path:
                print(f"HTML file for feed {feed_id} exists: {html_file_path}")
                with open(html_file_path, 'r', encoding='utf-8') as html_file:
                    html_content = html_file.read()
                    # Create an HTML email message
                    message = Mail(
                        from_email=FROM_EMAIL,
                        to_emails=TO_EMAIL,
                        subject='Test email from Sendgrid API',
                        html_content=html_content)
                    
                    try:
                        sg = SendGridAPIClient(SENDGRID_API_KEY)
                        response = sg.send(message)
                        print(response.status_code)
                        print(response.body)
                        print(response.headers)
                    except Exception as e:
                        if hasattr(e, 'response') and hasattr(e.response, 'body'):
                            error_message = e.response.body
                        else:
                            error_message = str(e)
                        print("Error sending email:", error_message)

if __name__ == "__main__":
    db_path = get_filepath('dbs/rss_sum.db')
    generator = GenerateMarkdown(db_filename=db_path)
    # generator.generate_markdown(output_directory)
    generator.find_statistics()
    generator.generate_html()
    # generator.send_email()