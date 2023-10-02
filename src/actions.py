import subprocess

# Define the Python scripts you want to run
scripts_to_run = ["src/01-rssfeedscraper.py", "src/02-rawfeedsfoldercreator.py", "src/03-GetArticles.py", "src/04-SummarizeArticle.py", "src/05-GetMarkdown.py"]
# scripts_to_run = ["src/02-rawfeedsfoldercreator.py", "src/03-GetArticles.py", "src/04-SummarizeArticle.py", "src/05-GetMarkdown.py"]
# Loop through and run each script
for script in scripts_to_run:
    try:
        subprocess.run(["python", script], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {script}: {e}")