import os
import re
import requests
import sys
import dateutil.parser
import pytz
import argparse


from urllib.parse import urlencode
from urllib.parse import urljoin
from pymongo import MongoClient
from textblob import TextBlob
from bs4 import BeautifulSoup
from datetime import datetime
from matplotlib import pyplot as plt


def main():
    parser = argparse.ArgumentParser(description = """"
                                                    Retreive all comments from a YouTube channel and plot daily...
                                                    average sentiment polarities in the period between 'start time' and 'end time'
                                                    """
                                                    )
    parser.add_argument("-s", help = "The start date for sentiment polarity plot as dd-mm-yyyy", type = str)
    parser.add_argument("-e", help = "The end date for sentiment polarity plot as dd-mm-yyyy", type = str)
    parser.add_argument("--name", help = "The name of the YouTube Channel as @<ChannelName>", type = str)


    args = parser.parse_args()
    base_url = "https://www.youtube.com/"
    channel_name = args.name
    s_date_str = args.s
    e_date_str =args.e

    s_date, e_date =make_datetime_tz_aware(s_date_str, e_date_str)
    youtube_api_key = get_api_key()
    mongodb_username, mongodb_password = get_mongodb_userpass()
    url = create_url(base_url, channel_name)
    channel_id = url_to_channel_id(url)

    api_parameters = {
        "key":youtube_api_key,
        "part":"snippet",
        "allThreadsRelatedToChannelId":channel_id,
        "maxResults":100,
    }

    client = get_mongodb_client(mongodb_username, mongodb_password)
    db = client.youtube
    collection_comments = db.comments
    collection_channels = db.channels
    existing_channel = check_channel_existence(collection_channels, channel_id)

    if existing_channel:
        last_page_token = existing_channel["last_page_token"]
        api_parameters['pageToken'] = last_page_token
    else:
        last_page_token = ""

    documents, last_page_token = create_docs(api_parameters, last_page_token)
    insert_to_mongo(collection_comments, documents, existing_channel)
    mongo_update_channel_info (collection_channels, channel_id, last_page_token)


    data = get_data_from_mongodb(client, channel_id, s_date, e_date)
    plot_avg_sentiment_polarity(data)

    client.close()

def make_datetime_tz_aware(s_date_str, e_date_str):
    try:
        s_date_dt = datetime.strptime(s_date_str, "%d-%m-%Y")
        e_date_dt = datetime.strptime(e_date_str, "%d-%m-%Y")
        s_date_dt_aware = s_date_dt.replace(tzinfo = pytz.UTC)
        e_date_dt_aware = e_date_dt.replace(tzinfo = pytz.UTC)
    except ValueError:
        sys.exit("Enter start and end time as dd-mm-yyy")
    if s_date_dt_aware >= e_date_dt_aware:
       sys.exit("End date must be later than start date")
    return s_date_dt_aware, e_date_dt_aware

def create_url(base_url, channel_name):
    url = urljoin(base_url, channel_name)
    return url


def url_to_channel_id(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        channel_id = soup.select_one('meta[property="og:url"]')['content'].strip('/').split('/')[-1]
    except TypeError:
        sys.exit("YouTube channel does not exist! Please check the channel name.")
    return channel_id


def check_channel_existence(collection, channel_id):
    existing_channel = collection.find_one({"channel_id":channel_id})
    return existing_channel

def mongo_update_channel_info (collection, channel_id, last_page_token):
    collection.update_one({"channel_id":channel_id, "last_page_token":last_page_token},
                            {"$set":{"channel_id":channel_id, "last_page_token":last_page_token}},
                            upsert = True)


def insert_to_mongo(collection, documents, existing_channel):
    if existing_channel:
        mongo_insert_nonexistent_docs(collection, documents)
    else:

        collection.insert_many(documents)


def mongo_insert_nonexistent_docs(collection, documents):

    ids = []
    existing_ids_list =set()
    new_documents =[]
    for doc in documents:
        ids.append(doc["_id"])
    existing_ids = list(collection.find({ "_id" : { "$in" : ids } }, {"_id":1}))
    for id in existing_ids:
        existing_ids_list.add(id["_id"])

    for doc in documents:
        if doc["_id"] not in existing_ids_list:
            new_documents.append(doc)

    if new_documents:
        collection.insert_many(new_documents)




def get_data_from_mongodb(client, channel_id, s_date, e_date):
    db = client.youtube
    collection = db.comments
    data = collection.aggregate(
        [
            {"$match":{
                "channel_id":channel_id,
                "publish_date":{
                    "$lte":e_date,
                    "$gte":s_date
                }
            }},

              {"$group":{
                  "_id":{"$dateToString": {"format": "%Y-%m-%d", "date": "$publish_date"}},
                  "average_sentiment":{"$avg":"$sentiment_polarity"}
              }},
              {"$sort": {"_id": 1}}
        ]
    )
    return data


def plot_avg_sentiment_polarity(data):
    dates_list=[]
    sentiment_list=[]
    data_list = list(data)
    for point in data_list:
        dates_list.append(datetime.strptime(point["_id"], "%Y-%m-%d"))
        sentiment_list.append(point["average_sentiment"])

    plt.style.use("ggplot")
    plt.plot(dates_list, sentiment_list)
    plt.xlabel("Date ")
    plt.ylabel("Sentiment Polarity")
    plt.title(f"Avg Sentiment polarity")
    plt.tight_layout()
    plt.savefig("sentiment_fig.png")


def get_mongodb_client(mongodb_username, mongobd_password):
    mongodb_connection_string = f"mongodb+srv://{mongodb_username}:{mongobd_password}@cluster0.qevjead.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(mongodb_connection_string)
    return client

def get_api_key():
    try:
        return os.environ["YOUTUBE_API_KEY"]
    except KeyError:
        sys.exit("Provide the YOUTUBE_API_KEY as an environment variable")

def get_mongodb_userpass():
    try:
        return os.environ["MONGODB_USERNAME"], os.environ["MONGODB_PASSWORD"]
    except KeyError:
        sys.exit("Provide MONGODB_USERNAME and MONGODB_PASSWORD as environment variables")

def results_item_to_mongodoc(item):
    comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
    comment_text = clean_text(comment_text)
    sentiment_polarity, sentiment_subjectivity = assign_sentiment(comment_text)
    author = item["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"]
    video_id = item["snippet"]["topLevelComment"]["snippet"]["videoId"]
    channel_id = item["snippet"]["topLevelComment"]["snippet"]["channelId"]
    thread_id = item["id"]
    publish_date = item["snippet"]["topLevelComment"]["snippet"]["publishedAt"]
    comment_id = item["snippet"]["topLevelComment"]["id"]

    document = {
        "_id" : comment_id,
        "comment_text":comment_text,
        "author":author,
        "channel_id":channel_id,
        "thread_id":thread_id,
        "video_id":video_id,
        "publish_date":dateutil.parser.isoparse(publish_date),
        "sentiment_polarity":sentiment_polarity,
        "sentiment_subjectivity": sentiment_subjectivity
    }
    return document

def get_results(api_parameters):
    uri = "https://www.googleapis.com/youtube/v3/commentThreads"
    encoded_parameters = urlencode(api_parameters)
    request_string = f"{uri}?{encoded_parameters}"
    response = requests.get(request_string)
    api_results = response.json()
    return api_results


def create_docs(api_parameters, last_page_token):
    documents =[]
    while True:
        results = get_results(api_parameters)

        for item in results["items"]:
            documents.append(results_item_to_mongodoc(item))

        if "nextPageToken" in results:
            next_page_token = results["nextPageToken"]
            last_page_token = results["nextPageToken"]
        else:
            next_page_token = ""
        if not next_page_token:
            break
        api_parameters["pageToken"] = next_page_token

    return documents, last_page_token

def clean_text(str):
    str = re.sub(r"<.*?>", "", str)
    str = re.sub(r"&#39;", "'", str)
    str = re.sub(r'&quot;','"' , str)
    return str

def assign_sentiment(str):
    testimonial = TextBlob(str)
    pol = testimonial.sentiment.polarity
    sub = testimonial.sentiment.subjectivity
    return pol, sub



if __name__=="__main__":
    main()