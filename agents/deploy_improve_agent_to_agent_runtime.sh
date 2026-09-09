#!/bin/bash

adk deploy agent_engine \
    --project=$GOOGLE_CLOUD_PROJECT \
    --region=$GOOGLE_CLOUD_LOCATION \
    --env_file=./improve_engagement_agent/.env.deploy \
    --display_name="Improve Engagement Agent" \
    --agent_engine_id=540869011156500480 \
    ./improve_engagement_agent

# to update an existing deployment, add:
#     --agent_engine_id=YOUR_RUNTIME_DEPLOYMENT_ID \
