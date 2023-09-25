# This file should be run manually

# import re

# # Read from the input file
# with open('dbs/links/substackstory.txt', 'r') as file:
#     content = file.readlines()

# # Extract links using regex
# links = [re.search(r'"(http.*?)"', line).group(1) for line in content if re.search(r'"(http.*?)"', line)]

# # Write the extracted links to a new file
# with open('output_links.txt', 'w') as file:
#     for link in links:
#         file.write(link + '\n')

# print("Links have been extracted to output_links.txt.")


from collections import Counter

# Read the links from a file (assuming each link is on a separate line)
with open('dbs/links/feed_links.txt', 'r') as file:
    links = [line.strip() for line in file]

# Count occurrences of each link
link_counts = Counter(links)

# Determine number of unique links
unique_count = len(link_counts)

# Count redundant links (occurrences > 1)
redundant_count = sum(count - 1 for count in link_counts.values() if count > 1)

print("Number of Unique Links:", unique_count)
print("Number of Redundant Links:", redundant_count)

# Remove redundant links by converting the list to a set and then back to a list
unique_links = list(set(links))

# Write the unique links back to the file or to a new file
with open('dbs/links/unique_feed_links.txt', 'w') as file:
    for link in unique_links:
        file.write(link + '\n')

print("Redundant links have been removed.")


