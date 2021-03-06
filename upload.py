#! /usr/bin/env python3

# Standard packages
import argparse
import json
import re
import yaml

# Local imports
from discourse_api import DiscourseAPI
from helpers import (
    generate_nav_markdown,
    get_created_topics,
    save_created_topics,
)

# Arguments
parser = argparse.ArgumentParser(
    description=("Upload Markdown documents to a Discourse installation")
)

parser.add_argument("--api-key", required=True)
parser.add_argument("--api-url", required=True)
parser.add_argument("--api-username", default="system")
parser.add_argument("--title-map", default="title-map.json")
parser.add_argument(
    "--category", default="docs", help=("Category for created posts")
)

args = parser.parse_args()

api = DiscourseAPI(
    url=args.api_url.rstrip("/"),
    username=args.api_username,
    key=args.api_key,
    category_name=args.category,
)


with open(args.title_map) as title_map_file:
    paths = json.load(title_map_file)

# Get created topics
created_topics = get_created_topics()

# Create / update all topics
# ===
for file_path, title in paths.items():
    # Read file
    with open(file_path) as post_content_file:
        post_content = post_content_file.read()

    # Create or update topic
    if file_path in created_topics:
        topic_id = created_topics[file_path]["id"]
        print(f"- Updating topic {topic_id} with {file_path} ...")
        api.update_topic_content(topic_id, post_content)
    else:
        print(f"- Creating topic from {file_path} ...")
        response = api.create_topic(title, post_content)

        if response.ok:
            created_topics[file_path] = {
                "slug": response.json()["topic_slug"],
                "id": response.json()["topic_id"],
                "wiki": False,
                "links_updated": False,
            }
            save_created_topics(created_topics)

    # If success, convert to wiki
    if file_path in created_topics:
        topic_id = created_topics[file_path]["id"]

        if created_topics[file_path]["wiki"]:
            print(f"  > Topic {topic_id} already converted to wiki")
        else:
            if api.convert_topic_to_wiki(topic_id):
                created_topics[file_path]["wiki"] = True
                save_created_topics(created_topics)

# Update links in topics
# ===
for file_path, topic_info in created_topics.items():
    print(f"- Updating links in topic {topic_info['id']}")
    markdown = api.get_topic_markdown(topic_info["id"])

    # Iterate through all created posts again, to replace links for each
    for nested_file_path, nested_topic_info in created_topics.items():
        file_name = nested_file_path[:-3]

        nested_topic_url = (
            f"/t/{nested_topic_info['slug']}/{nested_topic_info['id']}"
        )
        markdown = re.sub(
            f'([ (]|href=")[\./]*{file_name}[.](md|html)',
            f"\\1{nested_topic_url}",
            markdown,
        )

    if api.update_topic_content(topic_info["id"], markdown):
        created_topics[file_path]["links_updated"] = True
        save_created_topics(created_topics)


# Create / update documentation index
# ===
metadata_filepath = "metadata.yaml"

with open(metadata_filepath) as data_file:
    metadata = yaml.load(data_file)

nav_markdown = generate_nav_markdown(
    sections=metadata["navigation"], topics=created_topics
)

if metadata_filepath in created_topics:
    topic_id = created_topics[metadata_filepath]["id"]

    api.update_topic_content(topic_id, nav_markdown)
    print(f"- Updated documentation index in {topic_id}")
else:
    print(f"- Creating documentation index from {metadata_filepath} ...")
    response = api.create_topic("Documentation index", nav_markdown)

    if response.ok:
        created_topics[metadata_filepath] = {
            "slug": response.json()["topic_slug"],
            "id": response.json()["topic_id"],
            "wiki": False,
            "links_updated": True,
        }
        save_created_topics(created_topics)

# Print out any errors
api.print_errors()
