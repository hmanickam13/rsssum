import requests
import feedparser
from bs4 import BeautifulSoup as bs
import sqlite3

print("\n-----------------\nChecking if all the required packages are installed...\n")
try:
    import requests
    print("requests library is installed.")
except ImportError:
    print("requests library is not installed.")
print("----")
try:
    import feedparser
    print("feedparser library is installed.")
except ImportError:
    print("feedparser library is not installed.")
print("----")
try:
    import bs4
    print("bs4 library is installed.")
except ImportError:
    print("bs4 library is not installed.")

print("\n-----------------\n")