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
import base64

load_dotenv()
SENDGRID_API_KEY  = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL')
TO_EMAIL = os.getenv('TO_EMAIL')

WORDPRESS_USER = os.getenv('WORDPRESS_USER')
WP_USER_PASS = os.getenv('WP_USER_PASS')
WP_CREDENTIALS = WORDPRESS_USER + ':' + WP_USER_PASS
WP_TOKEN = base64.b64encode(WP_CREDENTIALS.encode())
WP_HEADER = {'Authorization': 'Basic ' + WP_TOKEN.decode('utf-8')}
WP_API_URL = os.getenv('WP_API_URL')

class GenerateHTML:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()
        self.articles_to_extract = []
        self.summary_status_1 = 0
        self.summary_status_2 = 0
        self.summary_status_3 = 0
        self.summary_status_4 = 0
        self.summary_status_5 = 0
        self.new_summaries_today_counter = 0
        self.last_10_days_summaries_counter = 0
        self.added_to_wordpress = 0
        self.could_not_add_to_wordpress = 0
        self.deleted_from_wordpress = 0
        self.could_not_delete_from_wordpress = 0

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
        eleven_days_ago = current_date - datetime.timedelta(days=11)
        twelve_days_ago = current_date - datetime.timedelta(days=12)
        twelve_days_counter = 0

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
                    if not entry.get('unique_WP_id'):
                        unique_WP_id = self.create_wordpress_post(entry['feed_id'], entry['article_id'], entry['title'], entry['guid'], entry['published_date'], entry['summary'])
                        if unique_WP_id:
                            self.added_to_wordpress += 1
                            entry['unique_WP_id'] = unique_WP_id
                        else:
                            self.could_not_add_to_wordpress += 1
                if summarized_date == current_date:
                    self.new_summaries_today_counter += 1
                    today_html_content += article_html
                # if eleven_days_ago == summarized_date:
                #     if entry.get('unique_WP_id'):
                #         if(self.delete_wordpress_post(entry['unique_WP_id'])):
                #             self.deleted_from_wordpress += 1
                #         else:
                #             self.could_not_delete_from_wordpress += 1
                if twelve_days_ago >= summarized_date:
                    twelve_days_counter += 1
                    if twelve_days_counter > 10:
                        break # no more articles to check

        # adding the unique_WP_id to the json file
        with open(summary_path, 'w', encoding='utf-8') as json_file:
            json.dump(json_data, json_file, indent=4)

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

    def create_wordpress_post(self, feed_id, article_id, title, guid, published_date, summary):

        str_feed_id = str(feed_id)
        str_article_id = str(article_id)
        str_published_date = str(published_date).replace("-", "")
        post_id_str = str_feed_id + str_published_date + str_article_id
        
        post_id = int(post_id_str)
        data = {
        'title' : title,
        'status': 'publish',
        'slug' : 'daily-reflections',
        'content': summary
        }

        response = requests.post(WP_API_URL,headers=WP_HEADER, json=data)
        if response.status_code == 201:
            return response.json()['id']
        else:
            return None

    def delete_wordpress_post(self, unique_WP_id):
        # unique_WP_id = "<" + str(unique_WP_id) + ">"
        unique_WP_id = str(unique_WP_id)
        # print(f"Deleting post with id: {unique_WP_id}")
        response = requests.delete(WP_API_URL + unique_WP_id,headers=WP_HEADER)
        print(response)
        if response.status_code == 201:
        #     print(response.json())
            return True
        else:
        #     # print(f"Error: {response.status_code}")
        #     # print(response.text)
            return False

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

    def gpost(self,txt):
        chat_url = "Webhook link"
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

        if today_date in existing_status and 'SummarizeArticles' in existing_status[today_date] and existing_status[today_date]['SummarizeArticles']['status'] == 'Failed':
            print(f"SummarizeArticles failed so this has not run")
            status_data = {
                'status': 'Failed',
                'message': 'SummarizeArticles failed so this has not run'
            }
        elif today_date in existing_status and 'SummarizeArticles' in existing_status[today_date] and existing_status[today_date]['SummarizeArticles']['status'] == 'Success':
            try:
                print(f"Generating HTML...")
                db_path = get_filepath('dbs/rss_sum.db')
                generator = GenerateHTML(db_filename=db_path)
                generator.generate_html()
                generator.conn.close()
                status_data = {
                    'status': 'Success',
                    'new_summaries_today': generator.new_summaries_today_counter,
                    'last_10_days_summaries_counter': generator.last_10_days_summaries_counter,
                    'added_to_wordpress': generator.added_to_wordpress,
                    'could_not_add_to_wordpress': generator.could_not_add_to_wordpress,
                    'deleted_from_wordpress': generator.deleted_from_wordpress,
                    'could_not_delete_from_wordpress': generator.could_not_delete_from_wordpress
                }
            except Exception as e:
                status_data = {
                    'status': 'Failed',
                    'message': str(e)
                }

            existing_status[today_date]['GenerateHTML'] = status_data

        with open(json_status_file_name, 'w') as f:
            json.dump(existing_status, f, indent=4)
    
    except FileNotFoundError:
        print(f"FileNotFoundError: {json_status_file_name} not found.")