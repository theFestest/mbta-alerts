gcloud functions deploy mbta-alerts \
    --runtime="python39" \
    --trigger-topic="minutes.two" \
    --source="./" \
    --entry-point="hello_pubsub" \
    --set-env-vars IS_DEPLOYED=YES \
    --service-account="654332399478-compute@developer.gserviceaccount.com"

# NOTE: Be careful not to fill in credentials in a file that will be tracked!
# See: https://cloud.google.com/sdk/gcloud/reference/functions/deploy
# Existing manually configured secrets should remain, but they can be programmatically updated.