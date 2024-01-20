import os
from typing import Union, Optional
from textwrap import dedent

import requests
from datetime import datetime, timedelta
from atproto import Client, models
from nanoatp.richtext import detectLinks

MANUAL = os.getenv("MANUAL", "")
IS_DEPLOYED = os.getenv("IS_DEPLOYED", "")
API_KEY = os.getenv("API_KEY", "")
BOT_HANDLE = os.getenv("BOT_HANDLE", "")
BOT_APP_PASSWORD = os.getenv("BOT_APP_PASSWORD", "")

MAX_POSTS_PER_RUN = 5

at_client = None

"""Example response body:
{
  "links": {
    "self": "string",
    "prev": "string",
    "next": "string",
    "last": "string",
    "first": "string"
  },
  "data": [ // Data key is a list of active alerts
    {
      "type": "string",
      "relationships": {
        "facility": {
          "links": {
            "self": "string",
            "related": "string"
          },
          "data": {
            "type": "string",
            "id": "string"
          }
        }
      },
      "links": {},
      "id": "string",
      "attributes": {
        "url": "http://www.mbta.com/uploadedfiles/Documents/Schedules_and_Maps/Commuter_Rail/fairmount.pdf?led=6/3/2017%201:22:09%20AM",
        "updated_at": "2017-08-14T14:54:01-04:00",
        "timeframe": "Ongoing",
        "short_header": "All weekend Fairmount Line trains will be bused between Morton St. & Readville due to construction of Blue Hill Ave Station.\n",
        "severity": 10,
        "service_effect": "Minor Route 216 delay",
        "lifecycle": "Ongoing",
        "informed_entity": [
          {
            "trip": "CR-Weekday-Spring-17-517",
            "stop": "Auburndale",
            "route_type": 2,
            "route": "CR-Worcester",
            "facility": "405",
            "direction_id": 0,
            "activities": [
              "BOARD",
              "EXIT"
            ]
          }
        ],
        "header": "Starting 6/3, all weekend Fairmount Line trains will be bused between Morton St. and Readville in both directions due to construction of the new Blue Hill Avenue Station.\n",
        "effect_name": "Delay",
        "effect": "ACCESS_ISSUE",
        "description": "If entering the station, cross Tremont Street to the Boston Common and use Park Street Elevator 978 to the Green Line westbound platform. Red Line platform access is available via the elevator beyond the fare gates. If exiting the station, please travel down the Winter Street Concourse toward Downtown Crossing Station, exit through the fare gates, and take Downtown Crossing Elevator 892 to the street level.\n",
        "created_at": "2017-08-14T14:54:01-04:00",
        "cause": "ACCIDENT",
        "banner": "All service suspended due to severe weather",
        "active_period": [
          {
            "start": "2017-08-14T14:54:01-04:00",
            "end": "2017-08-14T14:54:01-04:00"
          }
        ]
      }
    }
  ]
}
"""


def check_facets(facets: list):
    """ Examples of offending facet:
    Incorrectly ends in period
    [
      {
        '$type': 'app.bsky.richtext.facet',
        'index': {'byteStart': 149, 'byteEnd': 178},
        'features': [{'$type': 'app.bsky.richtext.facet#link', 'uri': 'https://buseta.wmata.com/#36.'}]
      }
    ]

    "Mt.Vernon" is not a valid uri but naively looks like one
    [
      {
        '$type': 'app.bsky.richtext.facet',
        'index': {'byteStart': 148, 'byteEnd': 157},
        'features': [{'$type': 'app.bsky.richtext.facet#link', 'uri': 'Mt.Vernon'}]
      }
    ]
    """
    fixed = []
    for facet in facets:
        # if url lacks http:// or https://, manually include it
        if not facet['features'][0]['uri'].startswith("http://") and not facet['features'][0]['uri'].startswith("https://"):
            print(f"Fixing facet for uri: {facet['features'][0]['uri']}")
            facet['features'][0]['uri'] = f"https://{facet['features'][0]['uri']}"
            print(f"Fixed uri: {facet['features'][0]['uri']}")
            fixed.append(facet)
        # If url ends in a dot we accidentally matched a period
        if facet['features'][0]['uri'][-1] == '.':
            print(f"Fixing facet for uri: {facet['features'][0]['uri']}")
            # Move end byte back by one
            facet['index']['byteEnd'] -= 1
            # Take slice to skip the last character
            facet['features'][0]['uri'] = facet['features'][0]['uri'][:-1]
            print(f"Fixed uri: {facet['features'][0]['uri']}")
            fixed.append(facet)
        elif facet['features'][0]['uri'].lower() == "Mt.Vernon".lower():
            # Not an actual url so skip this one.
            pass
        # elif facet['features'][0]['uri'].lower() == "N.W.".lower():
        #     # Not an actual url so skip this one.
        #     pass
        else:
            # Nothing to fix
            fixed.append(facet)
    return fixed


def send_post(text: str):
    """Send post with the given text content
    return post_ref of generated post
    """
    print(f"Sending post with text:\n{text}")
    if not isinstance(at_client, Client):
        at_login()
        assert isinstance(at_client, Client)
        assert at_client.me is not None

    # Make links clickable via rich text facets
    # Facet model structure:
    # facets = [
    #     models.AppBskyRichtextFacet.Main(
    #         features=[models.AppBskyRichtextFacet.Link(uri=url)],
    #         # Indicate the start and end of link in text
    #         index=models.AppBskyRichtextFacet.ByteSlice(byteStart=link_start, byteEnd=link_end)
    #     )
    # ]
    facets = detectLinks(text)
    # NOTE: sometimes finds urls with bogus trailing dots (bc of data like "wmata.com.")
    print(f"Found rich text facets: {facets}")
    facets = check_facets(facets)
    print(f"Adjusted rich text facets: {facets}")

    try:
        if IS_DEPLOYED or MANUAL:
            # Only bother embedding facets if there's a url.
            if len(facets) == 0:
                at_client.send_post(text=text)
            else:
                # Manually create post record to include rich text facets
                at_client.com.atproto.repo.create_record(
                    models.ComAtprotoRepoCreateRecord.Data(
                        repo=at_client.me.did,
                        collection=models.ids.AppBskyFeedPost,
                        record=models.AppBskyFeedPost.Main(
                            createdAt=at_client.get_current_time_iso(), text=text, facets=facets
                        )
                    )
                )
        else:
            print("Skipping sending post...")
    except Exception as ex:
        print("Failed to send post. Got error: ", str(ex))
        return False
    return True


def at_login():
    """Login with the atproto client
    """
    global at_client
    at_client = Client()
    profile = at_client.login(BOT_HANDLE, BOT_APP_PASSWORD)
    print("Logged in as: ", profile.display_name)


def is_newer(update_time: Union[str, datetime], last_posted: Optional[Union[str, datetime]]) -> bool:
    """Determine if update_time is more recent than the retrieved"""
    if last_posted is None or last_posted == "":
        return True  # TODO: is this a safe default or do we risk spamming?
    if not isinstance(update_time, datetime):
        update_time = datetime.fromisoformat(update_time)
        # Remove timezone as we know it will be given in the same time zone as was posted.
        update_time = update_time.replace(tzinfo=None)
    if not isinstance(last_posted, datetime):
        last_posted = datetime.fromisoformat(last_posted)
    return update_time > last_posted


def get_alerts():
    """Query MBTA for alerts
    """
    pass


def get_latest_post_time():
    """ Time corresponds to alert update time, not post time.
    Example reponse:
    Response(
        feed=[
            FeedViewPost(
                post=PostView(author=ProfileViewBasic(did='did:plc:4fzw4vfbpsdy77d6jvtmpxgk', handle='wmata-incidents.bsky.social', avatar='https://cdn.bsky.social/imgproxy/hteEyCauUcf07g7DRZ1TVjd6NjiDIpp68dEqlML7nD4/rs:fill:1000:1000:1:0/plain/bafkreicptnkurw36wwvqe5nqqd5ebwo7uq5yynwt4v4x72icn4v4irxqdq@jpeg', displayName='WMATA Incidents', labels=[], viewer=ViewerState(blockedBy=False, blocking=None, followedBy=None, following=None, muted=False, mutedByList=None, _type='app.bsky.actor.defs#viewerState'), _type='app.bsky.actor.defs#profileViewBasic'), cid='bafyreiezwte44vksso53ltnl5f7tkrlpnxeiqo3tukkjmmjlzeixth66xe', indexedAt='2023-07-26T02:04:52.699Z', record=Main(createdAt='2023-07-26T02:04:52.640687', text='Bus incident reported affecting the following routes: 36.\n\n    Alert: Route 36 westbound on detour at Naylor Rd & Suitland Pkwy, resuming regular route at Naylor Rd & 30th St.\n\n    Last updated: 2023-07-25 21:35:06 (Eastern Time).', embed=None, entities=None, facets=None, langs=['en'], reply=None, _type='app.bsky.feed.post'), uri='at://did:plc:4fzw4vfbpsdy77d6jvtmpxgk/app.bsky.feed.post/3k3fd4zfdza2d', embed=None, labels=[], likeCount=0, replyCount=0, repostCount=0, viewer=ViewerState(like=None, repost=None, _type='app.bsky.feed.defs#viewerState'), _type='app.bsky.feed.defs#postView'), reason=None, reply=None, _type='app.bsky.feed.defs#feedViewPost'
            )
        ],
        cursor='1690337092640::bafyreiezwte44vksso53ltnl5f7tkrlpnxeiqo3tukkjmmjlzeixth66xe'
    )
    """
    try:
        if not isinstance(at_client, Client):
            at_login()
            assert isinstance(at_client, Client)

        # Fetch feed of latest posts from this bot
        feed_resp = at_client.get_author_feed(actor=BOT_HANDLE, limit=1)
        print(f"Got feed response:\n{feed_resp}")
        # Get post itself
        latest_post = feed_resp.feed[0].post
        # Get text from the post
        post_text: str = latest_post.record.text
        print(f"Got latest post with text:\n{post_text}")
        # Get post by lines
        post_lines = post_text.splitlines()
        # Get update line: "Updated: 2023-07-25 20:10:19 (Eastern Time)."
        update_line = post_lines[-1]
        print(f"Post update line reads: {update_line}")
        # Get timestamp from within this line: "2023-07-25 20:10:19"
        time_string = update_line[update_line.find(": ")+len(": "): update_line.find("(")-len("(")]
        # Convert to datetime object for comparisons
        timestamp = datetime.fromisoformat(time_string)
    except Exception as ex:
        print("Failed to login to collect latest posting time!")
        # Default to most recent 24 hours
        timestamp = datetime.now() - timedelta(hours=24)

    return timestamp


def find_new_alerts(alert_list, latest_post: datetime):
    """Collect new / updated alerts based on latest post records
    """
    new_alerts = []

    # Active alerts are listed in reverse chronological order, reverse for posting.
    alert_list.reverse()
    for alert in alert_list:
        if is_newer(alert['attributes']["updated_at"], latest_post):
            print("Found new alert for processing...")
            new_alerts.append(alert)
        elif not IS_DEPLOYED and not MANUAL:
            print("Appending old alert due to development config...")
            new_alerts.append(alert)

    return new_alerts


def make_alert_text(alert_dict: dict):
    """Generate formatted post body for train alerts
    Example data under .data.attributes

    "attributes": {
        "url": "http://www.mbta.com/uploadedfiles/Documents/Schedules_and_Maps/Commuter_Rail/fairmount.pdf?led=6/3/2017%201:22:09%20AM",
        "updated_at": "2017-08-14T14:54:01-04:00",
        "timeframe": "Ongoing",
        "short_header": "All weekend Fairmount Line trains will be bused between Morton St. & Readville due to construction of Blue Hill Ave Station.\n",
        "severity": 10,
        "service_effect": "Minor Route 216 delay",
        "lifecycle": "Ongoing",
        "informed_entity": [
          {
            "trip": "CR-Weekday-Spring-17-517",
            "stop": "Auburndale",
            "route_type": 2,
            "route": "CR-Worcester",
            "facility": "405",
            "direction_id": 0,
            "activities": [
              "BOARD",
              "EXIT"
            ]
          }
        ],
        "header": "Starting 6/3, all weekend Fairmount Line trains will be bused between Morton St. and Readville in both directions due to construction of the new Blue Hill Avenue Station.\n",
        "effect_name": "Delay",
        "effect": "ACCESS_ISSUE",
        "description": "If entering the station, cross Tremont Street to the Boston Common and use Park Street Elevator 978 to the Green Line westbound platform. Red Line platform access is available via the elevator beyond the fare gates. If exiting the station, please travel down the Winter Street Concourse toward Downtown Crossing Station, exit through the fare gates, and take Downtown Crossing Elevator 892 to the street level.\n",
        "created_at": "2017-08-14T14:54:01-04:00",
        "cause": "ACCIDENT",
        "banner": "All service suspended due to severe weather",
        "active_period": [
          {
            "start": "2017-08-14T14:54:01-04:00",
            "end": "2017-08-14T14:54:01-04:00"
          }
        ]
      }

    """
    # TODO: try to include link as "More" hyper link? Or as a link on the heading?
    # TODO: clearer presentation of data? less redudancy?
    # TODO: have a more generic way of trimming to length
    text = dedent(f"""
{alert_dict['attributes']['service_effect']}:
{alert_dict['attributes']['header']}
Updated: {datetime.fromisoformat(alert_dict['attributes']['updated_at']).replace(tzinfo=None)} (Eastern).
""").strip()
    if len(text) > 300:
        # Cut from end of header to get back down to length. Do -1 extra for '…' grapheme.
        text = dedent(f"""
{alert_dict['attributes']['service_effect']}:
{alert_dict['attributes']['header'][:300-len(text)-1]}…
Updated: {datetime.fromisoformat(alert_dict['attributes']['updated_at']).replace(tzinfo=None)} (Eastern).
""").strip()
    return text


def main():
    print(f"Cron has been invoked at {datetime.now()}")
    # Note: Assumes the invarient "latest post has the latest WMATA update time"
    latest_update = get_latest_post_time()
    print(f"Latest post was an update from {latest_update}")

    # Step 0: generate auth header
    auth_header = {"api_key": API_KEY}

    # Step 1: Check alerts
    alert_resp = requests.get(url="https://api-v3.mbta.com/alerts", headers=auth_header)

    # print("Got alert response: ", alert_resp.json())

    # Step 2: Collect relevant alerts (check latest_update for recency)
    new_alerts = find_new_alerts(alert_resp.json()['data'], latest_update)

    # TODO: handle delay alerts more cleanly to post less
    print(f"Got {len(new_alerts)} new alerts")

    # Step 3: Generate posts to send (post_text, date_updated)
    to_send: list[tuple[str, str]] = []
    to_send.extend([(make_alert_text(alert), alert['attributes']['updated_at']) for alert in new_alerts])

    # Step 4: Send posts and note latest post update time.
    posts = 0
    latest_post = None
    # Sort posts overall by the datetime of their update (newest last)
    to_send.sort(key=lambda a: a[1])
    for post_tuple in to_send:
        if posts >= MAX_POSTS_PER_RUN and (IS_DEPLOYED or MANUAL):
            print(f"Sent {MAX_POSTS_PER_RUN} posts, stopping to avoid spamming. {len(to_send)-MAX_POSTS_PER_RUN} to go next time.")
            break
        if not IS_DEPLOYED or MANUAL:
            # Pause before posting during development
            breakpoint()
        if send_post(post_tuple[0]):
            posts += 1
            latest_post = post_tuple[1]
        else:
            print("Post failed! Moving on...")

    # Will look this time up via atproto on next run.
    # Note: we post the most recent update last to uphold invarient.
    print(f"Lastest post was from timestamp: {latest_post}.")
    print(f"Sent {posts} alert posts. Exiting...")


if __name__ == "__main__":
    main()
