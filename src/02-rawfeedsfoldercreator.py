import os
import sqlite3

class RawFeedsFolderCreator:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.output_folder = 'dbs/raw_feeds'

    def create_folders(self):
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM LINKS")
        ids = cursor.fetchall()

        for row in ids:
            unique_id = row[0]
            folder_path = os.path.join(self.output_folder, str(unique_id))

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                print(f"Created folder: {folder_path}")
            else:
                print(f"Folder already exists: {folder_path}")

        conn.close()

if __name__ == "__main__":
    folder_creator = RawFeedsFolderCreator(db_filename='dbs/rss_sum.db')
    folder_creator.create_folders()
