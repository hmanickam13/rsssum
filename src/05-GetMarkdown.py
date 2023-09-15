import os
from dotenv import load_dotenv # to load env variables
import json
import sqlite3
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import datetime

load_dotenv()
SENDGRID_API_KEY  = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL')
TO_EMAIL = os.getenv('TO_EMAIL')

class GenerateMarkdown:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.create_newsletter_table()

    def create_newsletter_table(self):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Newsletter (
                id INTEGER,
                id_article INTEGER,
                published TEXT,
                updated TEXT,
                latest_mailing_timestamp TEXT              
           )
        ''')

        conn.commit()
        conn.close()

    def populate_newsletter_table(self, dict_article):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()

        # Check if a row with the same id and id_article exists
        cursor.execute('''
            SELECT title
            FROM Newsletter
            WHERE id = ? AND id_article = ?
        ''', (dict_article['id'], dict_article['id_article']))

        current_tmsp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing_row = cursor.fetchone()

        if existing_row:
            print("Row already exists. Skipping...\n---------------------")
        else:
            # Insert the new row
            cursor.execute('''
                INSERT INTO Newsletter (id, id_article, published, updated, latest_mailing_timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dict_article['id'], dict_article['id_article'], dict_article['published'],
                dict_article['updated'], current_tmsp
            ))
            conn.commit()
            print("Newsletter data inserted successfully.\n---------------------")

        conn.close()
        # return 0

    def update_generated_html(self, feed_id, article_id, number):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Metadata
            SET generated_html = ?
            WHERE id = ? AND id_article = ?
            ''', (number, feed_id, article_id))
        conn.commit()
        conn.close()

    def generate_markdown(self, output_dir):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM LINKS")
        feed_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

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
                conn = sqlite3.connect(self.db_filename)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT summarize_status
                    FROM Metadata
                    WHERE id = ? AND id_article = ?
                ''', (entry['id'], entry['id_article']))
                summary_status = cursor.fetchone()
                print(f"summary_status: {summary_status}")
                conn.close()

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

    def generate_html(self, output_dir):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM LINKS")
        feed_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        for feed_id in feed_ids:
            feed_folder = os.path.join(output_dir, 'dbs/raw_feeds', str(feed_id))
            feed_json_path = os.path.join(feed_folder, 'feed.json')

            if not os.path.exists(feed_json_path):
                print(f"JSON file not found for feed {feed_id}. Skipping...")
                continue

            with open(feed_json_path, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)

            html_content = ""
            for entry in json_data:
                conn = sqlite3.connect(self.db_filename)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT summarize_status
                    FROM Metadata
                    WHERE id = ? AND id_article = ?
                ''', (entry['id'], entry['id_article']))
                summary_status = cursor.fetchone()
                print(f"summary_status: {summary_status}")
                conn.close()

                if summary_status[0] == 0 or summary_status[0] == 2:
                    print(f"Summary does not exist for feed {feed_id}, article {entry['id_article']}. Skipping...")
                elif summary_status[0] == 1:
                    print(f"Summary exists for feed {feed_id}, article {entry['id_article']}. Converting to HTML...")
                    # Customize the HTML format here
                    html_content += f"<h1>{entry['title']}</h1>"
                    # html_content += f"<p><strong>Published:</strong> {entry['published']}</p>"
                    html_content += f"<p><strong>Author:</strong> {entry['author']}</p>"
                    html_content += f"<p><strong>Link:</strong> {entry['guid']}</p>"
                    html_content += f"<p><strong>Summary:</strong> {entry['summary']}</p>"
                    html_content += "<hr>"

                    self.update_generated_html(feed_id, entry['id_article'], 1)

            html_file_path = os.path.join(feed_folder, 'feed.html')
            with open(html_file_path, 'w', encoding='utf-8') as html_file:
                html_file.write(html_content)

            print(f"HTML file for feed {feed_id} created: {html_file_path}")
    
    def send_email(self, output_dir):
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM LINKS")
        feed_ids = [row[0] for row in cursor.fetchall()]

        for feed_id in feed_ids[:2]:
            
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
    generator = GenerateMarkdown(db_filename='src/dbs/rss_sum.db')
    output_directory = '.'  # Change this to the desired output directory
    # generator.generate_markdown(output_directory)
    generator.generate_html(output_directory)
    generator.send_email(output_directory)
