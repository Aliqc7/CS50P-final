import dateutil.parser
import datetime
import pytz

from project import create_url
from project import url_to_channel_id
from project import clean_text
from project import assign_sentiment
from project import results_item_to_mongodoc
from project import make_datetime_tz_aware


def test_create_url():
    assert create_url("https://www.youtube.com/","@StoriesBehindStamps") == "https://www.youtube.com/@StoriesBehindStamps"

def test_url_to_channel_id():
    assert url_to_channel_id("https://www.youtube.com/@StoriesBehindStamps") == "UCHGHlvoXTTM0rpyd3zW3IQQ"

def test_make_datetime_tz_aware():
    assert make_datetime_tz_aware("01-01-2020","10-10-2022") ==(datetime.datetime(2020, 1, 1, 0, 0, tzinfo=pytz.UTC), datetime.datetime(2022, 10, 10, 0, 0, tzinfo=pytz.UTC))

def test_clean_text():
    assert clean_text("&quot;Hello&quot;") == '"Hello"'
    assert clean_text("&#39;The truth hurts&#39;") == "'The truth hurts'"
    assert clean_text("<a href=""https://www.youtube.com/watch?v=EKVVhBoo13w&amp;t=38m58s"">38:58</a>") == "38:58"

def test_results_item_to_mongodoc():
    assert  results_item_to_mongodoc({'kind': 'youtube#commentThread', 'etag': 'OzjmZ2nn9GplZbvwLaboXPEV__0',
    'id': 'UgwtxDRxJNyAnjdRrr14AaABAg', 'snippet': {'channelId': 'UCHGHlvoXTTM0rpyd3zW3IQQ', 'videoId': '_6q1qEUQxEo',
    'topLevelComment': {'kind': 'youtube#comment', 'etag': 'uEoUTpLpM6Z_2yqwi8Np5d3vEN8', 'id': 'UgwtxDRxJNyAnjdRrr14AaABAg',
    'snippet': {'channelId': 'UCHGHlvoXTTM0rpyd3zW3IQQ', 'videoId': '_6q1qEUQxEo',
    'textDisplay': 'Great first video, Lawrence.  Well done 👍', 'textOriginal': 'Great first video, Lawrence.  Well done 👍',
    'authorDisplayName': 'Exploring Stamps', 'authorProfileImageUrl': 'https://yt3.ggpht.com/ytc/AMLnZu_2B3ROi7w35lsHVlJilgedwqCizrAeoymljZZDGw=s48-c-k-c0x00ffffff-no-rj',
    'authorChannelUrl': 'http://www.youtube.com/channel/UCkeSM6aOWfaUPIGb5rPOGyA', 'authorChannelId': {'value': 'UCkeSM6aOWfaUPIGb5rPOGyA'},
    'canRate': True, 'viewerRating': 'none', 'likeCount': 4, 'publishedAt': '2021-10-13T01:52:09Z',
    'updatedAt': '2021-10-13T01:52:09Z'}}, 'canReply': True, 'totalReplyCount': 1, 'isPublic': True}}) == {'_id': 'UgwtxDRxJNyAnjdRrr14AaABAg',
    'comment_text': 'Great first video, Lawrence.  Well done 👍', 'author': 'Exploring Stamps',
    'channel_id': 'UCHGHlvoXTTM0rpyd3zW3IQQ', 'thread_id': 'UgwtxDRxJNyAnjdRrr14AaABAg', 'video_id': '_6q1qEUQxEo',
    'publish_date': dateutil.parser.isoparse("2021-10-13T01:52:09Z"), 'sentiment_polarity': 0.525,
    'sentiment_subjectivity': 0.5416666666666666}

def test_assing_sentiment():
    assert assign_sentiment("Great job!")== (1.0, 0.75)