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
import glob

load_dotenv()
SENDGRID_API_KEY  = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL')
TO_EMAIL = os.getenv('TO_EMAIL')

class GenerateHTML:
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
        self.new_summaries_today_counter = 0
        self.last_10_days_summaries_counter = 0

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

    def truncate_summary(self, summary, word_limit=50):
        words = summary.split()
        if len(words) > word_limit:
            return ' '.join(words[:word_limit]) + '...'
        else:
            return summary

    def generate_html(self):
        index_html_content = ""  # Initialize html_content outside the loop
        today_html_content = ""
        base_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Feed Summary</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.5;
                    padding: 20px;
                }}

                .articles-container {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 20px;
                    max-width: 1200px;
                    margin: 0 auto;
                }}

                .article {{
                    margin-bottom: 20px;
                    padding: 15px;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                    box-sizing: border-box;
                }}

                .article p {{
                    margin-bottom: 10px;
                }}

                .article .link {{
                    color: #0077cc;
                    text-decoration: none;
                }}

                .article .link:hover, .article .link.more:hover {{
                    text-decoration: underline;
                }}

                .article .more {{
                    font-style: italic;
                    font-weight: normal;
                }}

                hr {{
                    border: 0;
                    height: 1px;
                    background: #ccc;
                    margin: 20px 0;
                }}

                @media (max-width: 768px) {{
                    .articles-container {{
                        grid-template-columns: 1fr;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="articles-container">
                {content}
            </div>
        </body>
        </html>
        """

        summary_path = os.path.join('docs', 'summaries.json') 
        # pwd = os.getcwd()
        # print(pwd)
        # print(f"summary_path: {summary_path}")
        if not os.path.exists(summary_path):
            print(f"Summary file not found...")

        with open(summary_path, 'r', encoding='utf-8') as json_file:
            json_data = json.load(json_file)

        current_date = datetime.datetime.today().date()
        ten_days_ago = current_date - datetime.timedelta(days=10)

        for entry in json_data:
            summarized_date = (datetime.datetime.strptime(entry["summarized_date"], '%Y-%m-%d')).date()
            # if summary attribute exists in entry
            if entry.get('summary'):
                # print(f"Adding feed {entry['feed_id']}, article {entry['article_id']} to HTML...")
                truncated_summary = self.truncate_summary(entry['summary'])
                article_html = """
                <div class="article">
                    <p>{summary} <a href="{guid}" class="link more" target="_blank">more »</a></p>
                    <hr>
                </div>
                """.format(guid=entry['guid'], summary=truncated_summary)

                if current_date >= summarized_date >= ten_days_ago:
                    self.last_10_days_summaries_counter += 1
                    index_html_content += article_html
                if summarized_date == current_date:
                    self.new_summaries_today_counter += 1
                    today_html_content += article_html

        # Inject the accumulated content into the base HTML
        index_html = base_html.format(content=index_html_content)
        today_html = base_html.format(content=today_html_content)

        # Create directories if they don't exist
        if not os.path.exists('docs'):
            os.mkdir('docs')
        if not os.path.exists('docs/oldhtmls'):
            os.mkdir('docs/oldhtmls')

        # Define paths for 'index.html' and the backup file with today's date
        index_html_path = os.path.join('docs', 'index.html')
        today = current_date.strftime('%Y-%m-%d')
        today_html_path = os.path.join('docs', 'oldhtmls', f'{today}.html')
        backup_html_path = os.path.join('docs', 'oldhtmls', f'last_10_days.html')

        # print(f"Last 10 days summaries: {self.last_10_days_summaries_counter}")
        # Write the new data to 'index.html'
        with open(index_html_path, 'w', encoding='utf-8') as html_file:
            html_file.write(index_html)
            print(f"\nindex.html created: {index_html_path}")

        # Make a copy of the new 'index.html' with today's date
        shutil.copy2(index_html_path, backup_html_path)
        print(f"\nindex.html backed up inside oldhtmls")

        # print(f"New summaries today: {self.new_summaries_today_counter}")
        if self.new_summaries_today_counter > 0:
            with open(today_html_path, 'w', encoding='utf-8') as html_file:
                html_file.write(today_html)
                print(f"\nToday's HTML file created inside oldhtmls: {today_html_path}")

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
                SELECT id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days, summarized_date
                FROM Metadata
                WHERE id = ?
            ''', (feed_id,))
            rows = self.c.fetchall()
            for row in rows[:]:
                id_article, content_exists, summarize_status, summary_attempts, published_within_10_days, updated_within_10_days, summarized_date = row
                today_date = str(datetime.datetime.today().strftime('%Y-%m-%d'))
                if summarized_date == today_date:
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

        # self.conn.close()

        # print(f"articles to extract: {self.articles_to_extract}\n")
        
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
        # self.gpost(message_text)

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
    # generator.generate_markdown(output_directory)
    # generator.find_statistics()
    # generator.generate_html()
    # generator.send_email()
    # generator.conn.close()

    # print(f"\nNew summaries today: {generator.new_summaries_today_counter}")
    # print(f"\nLast 10 days summaries: {generator.last_10_days_summaries_counter}\n")
    
    today_date = datetime.datetime.today().strftime('%Y-%m-%d')
    json_status_file_name = get_filepath('status.json')

    # two_days_ago = datetime.datetime.today() - datetime.timedelta(days=1)
    # two_days_ago_date = two_days_ago.strftime('%Y-%m-%d')

    try:
        with open(json_status_file_name, 'r') as f:
            existing_status = json.load(f)
    
        # default status
        status_data = {
                'status': 'Did not run',
                'message': 'if elif conditions not met, check code'
            }
            
        if today_date in existing_status and 'SummarizeArticles' in existing_status and existing_status[today_date]['SummarizeArticles']['status'] == 'Failed':
            status_data = {
                'status': 'Failed',
                'message': 'SummarizeArticles failed so this has not run'
            }
        elif today_date in existing_status and 'SummarizeArticles' in existing_status and existing_status[today_date]['SummarizeArticles']['status'] == 'Failed':
            try:
                db_path = get_filepath('dbs/rss_sum.db')
                generator = GenerateHTML(db_filename=db_path)
                generator.generate_html()
                generator.conn.close()
                status_data = {
                    'status': 'Success',
                    'new_summaries_today': generator.new_summaries_today_counter,
                    'last_10_days_summaries_counter': generator.last_10_days_summaries_counter
                }
            except Exception as e:
                status_data = {
                    'status': 'Failed',
                    'message': str(e)
                }

            existing_status[today_date]['GenerateHTML'] = status_data

        with open(json_status_file_name, 'w') as f:
            # print(f"Opened file")
            json.dump(existing_status, f, indent=4)
    
    except FileNotFoundError:
        print(f"FileNotFoundError: {json_status_file_name} not found.")