# rsssummary

Clone the repository.

Ensure you are in the correct branch after cloning

### Initial setup
Create a virtual env with python & pip. I used conda package manager. Any package manager should work.
```sh
$ conda create --name rsssum python=3.10 pip
```

Activate the virtual env.
```sh
$ conda activate rsssum
```

Install all required dependencies for this project
```sh
$ ./scripts/setup.sh
```

**Make sure to add your OPENAI_API_KEY in your environment variable located inside src**

### Workflow
Please execute python scripts from inside src. 
```sh
cd src
```
##### 1. RSSFeedScraper
```sh
python 01-rssfeedscraper.py
```
- Takes in as input list of webpage URLs
- Fetches rss feed URLs for each webpage
- Stores both URLs for successful & failed fetches in a sqlite db
- Does not process a link if it has failed once
- ID column created. This is the feed number and the PRIMARY_KEY

##### 2. RawFeedsFolderCreator
```sh
python 02-rawfeedsfoldercreator.py
```
- Refers to PRIMARY_KEY in sqlite db to create directories to store our files.

##### 3. GetArticles
```sh
python 03-GetArticles.py
```
- Fetches json feed and stores select attributes to a unique json file for each feed
- Extracts metadata and stores in sqlite db

##### 4. SummarizeArticle
```sh
python 04-SummarizeArticle.py
```
- Use metadata to select the articles which have content to summarize
- API Call
- Store response in same json file
- Adds a number to the end of the reponse which helps to classify the content: 0 - No relevant article; 1 - Successfully summarized; 2 - Too lengthy to be summarized; 3 - Error during summarizing.
- Does not resummarize articles if they were already summarized
- Limits the number of attempts to summarize an article to 2
- Checks if the article was published within the last 10 days (could be extended to updated date also)

##### 5. Newsletter - In Progress
- Uses sqlite db to itereate through feed sources
- Extracts articles & their summaries from json files directly to html (bypassed markdown)
- Marks 'generated_html' in the metadata for the respective articles
- SendGrid API call
-----


Tasks completed: 
- Limits the number of attempts to summarize an article to 2
- Checks if the article was published within the last 10 days (could be extended to updated date also)
- Fetch articles/summaries from last 10 days (For now I have not enforced this but all the code is ready)
- date check can be extended to updated_date also (metadata ready, just need to write an if condition)
- automatically runs task and sends an email.
- change prompt to print "No summary available"
- Remove number at the end of summary
- added article link to html
- Can run everything as Github action
- Github action set to automatically run every day at 1PM from sunday to thursday


Later:
- timeout for openai call (Sometimes the openai never responds and that just causes the whole thing to get stuck)
- Should print No summary is available ?? (Currently, if no summary will not be added in html)
- github pages
- pull it into wordpress