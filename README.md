### AI Summarizer

#### Configuration
- Add your API_KEYS in your secret variables for HitHub Actions
- Allow GitHub Actions to update the repo
- Allow Github Pages to read from the docs folder

#### Run Status
- GitHub Actions schedules actions.py to run once everyday.
- actions.py executes python scripts in the following order
- src/status.json is updated after every run.

##### 1. RSSFeedScraper
```sh
python 01-rssfeedscraper.py
```
- Reads webpage links from dbs/links/webpage_links.txt
- Reads feed links from dbs/links/feed_links.txt
- Fetches rss feed links for webpage links
- Stores all working links in sqlite DB in table LINKS
- If a webpage_link does not have an embedded feed_link or if feed_link does not work, it is stored in table FAILED_LINKS in the sqlite DB
- If a feed_link cannot be successfully parsed, it is stored in the FAILED_PARSE table
- ID column created. This is the feed number and the PRIMARY_KEY
- To delete a webpage_link or a feed_link, just remove it from the txt file

##### 2. GetArticles
```sh
python 02-GetArticles.py
```
- For all the feeds in the LINKS page, this fetches the articles
- If content exists for a feed, it stores specific attributes in a dedicated json file for each feed
- Extracts metadata and stores in sqlite db
- This process of creating folders and extracting metadata happens repeatedly since we do not store these json files anywhere when run as github actions
- However, the sqlite db is updated only for new feeds or articles


##### 3. SummarizeArticles
```sh
python 03-SummarizeArticles.py
```
- Use metadata to select the articles which have content and was published within the last 10 days to summarize
- OpenAI API Call
- Store response in feed JSON file
- Updates metadata table with summary results (1 - successful, 2 - not relevant , 3 - Too lengthy , 4 - Error during summarization , 5 - Timed out)
- Adds successful summarizations (case 1) to summaries.json (appends from the top)
- Does not resummarize articles if they were already summarized
- Limits the number of attempts to summarize an article to 3

##### 5. GetHTML
- Extracts articles & their summaries from JSON file to 3 HTML files.
- File 1: index.html - contains last 10 days articles. Overwritten daily.
- File 2: index.html - Copy placed inside oldhtmls. Overwritten daily.
- File 3: Today's summaried articles placed inside oldhtmls. New files accumulate if new articles summarized.
- SendGrid API call (not active)
- Gchat summary (not active)