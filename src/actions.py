import subprocess


# print current wd using os
import os
print(os.getcwd())

# Define the Python scripts you want to run
scripts_to_run = ["src/01-RSSFeedScraper.py",
                  "src/02-GetArticles.py"]
                #   "src/03-SummarizeArticles.py",
                #   "src/04-GetHTML.py"]

# Loop through and run each script
for script in scripts_to_run:
    try:
        subprocess.run(["python", script], check=True)
        print(f"Successfully ran {script}")
    except subprocess.CalledProcessError as e:
        print(f"Error running {script}: {e}")