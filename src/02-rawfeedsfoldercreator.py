import os
import sqlite3
from util import get_filepath

class RawFeedsFolderCreator:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.output_folder = 'src/dbs/raw_feeds'
        self.conn = sqlite3.connect(self.db_filename)
        self.c = self.conn.cursor()

    def create_folders(self):
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        self.c.execute("SELECT id FROM LINKS")
        ids = self.c.fetchall()

        for row in ids:
            unique_id = row[0]
            folder_path = os.path.join(self.output_folder, str(unique_id))

            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            #     print(f"Created folder: {folder_path}")
            # else:
            #     print(f"Folder already exists: {folder_path}")

        self.conn.close()

if __name__ == "__main__":
    db_path = get_filepath('dbs/rss_sum.db')
    folder_creator = RawFeedsFolderCreator(db_filename=db_path)
    folder_creator.create_folders()



