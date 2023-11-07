
# MBTA Alerts Bot

https://bsky.app/profile/mbta-alerts.bsky.social

## References

https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python

https://vercel.com/docs/cron-jobs#cron-expressions

https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python

https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python#python-dependencies

https://cloud.google.com/scheduler/docs/creating#begin

https://www.pythonmorsels.com/dedent/

https://github.com/MarshalX/atproto/blob/main/examples/advanced_usage/send_rich_text.py

https://github.com/susumuota/nanoatp

// MBTA related

https://api-v3.mbta.com/portal

https://api-v3.mbta.com/docs/swagger/index.html#/Alert

https://www.mbta.com/developers/v3-api

https://www.mbta.com/developers

https://www.mbta.com/alerts/subway

## Demo

https://python-hello-world.vercel.app/

## Running Locally

```bash
npm i -g vercel
vercel dev
```

Your Python API is now available at `http://localhost:3000/api`.

## TODO:

- fix post time zone

- Increase frequency of checks (is 5 minutes enough? github actions doesn't keep to schedule well...)

- Enable elevator incidents

- Maybe: remove state via kv store and just check past interval (requires good scheduling to not miss any; might repeat posts sometimes)

- Maybe: keep state but only store the date of the most recent posted update. Then post everything newer than that update.

- Maybe: simply check own feed, and post anything newer than the timestamp of the last post (might miss anything between api check and post)
    - better parse the timestamp of the update out of the last post!

- Decide to keep or remove vercel compatability
    - nanoatp breaks compatability with python 3.9 on here?

- Simplify vercel layout (remove silly additions from messing with cron triggers)

- Make urls clickable via rich text (https://github.com/MarshalX/atproto/blob/main/examples/advanced_usage/send_rich_text.py)
    - use detectFacets ? https://github.com/susumuota/nanoatp
    - or just find start byte as "https://" and end byte as first whitespace after url? (might be too naive)

- Support reposting long standing incidents (such as WMATA Green line currently) once a day or so.
    - perhaps: if incident is older than 24 hours and time is within 1 interval of 8 am or 4 pm (commuting hours)?

- Let manual posts not interfere with running (tag specifically bot posts, or pull more posts if the latest doesn't contain the time)

- Trim spaces at the start/end of lines? avoid whatever caused this: https://bsky.app/profile/wmata-incidents.bsky.social/post/3k3ilx2ejfl2v
    - modify dedent to not have \n interfere with it
    - issue was: 'Description': 'Some D14 trips may be delayed due to operator availability. Check where your bus is at \nhttps://buseta.wmata.com/#D14'
    - see https://github.com/theFestest/wmata-incidents/actions/runs/5678804071/job/15389726708

- Consider replacing internal newlines in provided info to preserve formatting

- Retry posting without facets if posting with facets fails?

- Make errors / error-reporting more visible
