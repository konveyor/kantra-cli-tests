#!/bin/bash
set -e

# Configuration
HUB_URL="${HUB_BASE_URL:-localhost:8080}"
BASE_URL="http://${HUB_URL}"

echo "============================================"
echo "Creating Hub Entities"
echo "============================================"
echo "Hub URL: $BASE_URL"
echo ""

# Function to check if hub is ready
check_hub_ready() {
    echo "Checking if hub is ready..."
    local CURL_OPTS=(--fail --silent --show-error --connect-timeout 3 --max-time 15)
    for i in {1..30}; do
        if curl "${CURL_OPTS[@]}" "${BASE_URL}/applications" > /dev/null; then
            echo "✓ Hub is ready!"
            return 0
        fi
        echo "Attempt $i: Hub not ready yet, waiting..."
        sleep 2
    done
    echo "✗ Hub did not become ready in time"
    exit 1
}

# Check hub is ready
check_hub_ready

echo ""
echo "============================================"
echo "Step 1: Creating Target"
echo "============================================"

TARGET_RESPONSE=$(curl --fail --silent --show-error -X POST "${BASE_URL}/targets" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cloud-readiness",
    "description": "Cloud readiness target for containerization",
    "custom": true,
    "labels": [],
    "image": {"id": 1}
  }')

TARGET_ID=$(echo $TARGET_RESPONSE | jq -r '.id')
TARGET_NAME=$(echo $TARGET_RESPONSE | jq -r '.name')

if [ "$TARGET_ID" != "null" ] && [ "$TARGET_ID" != "" ]; then
    echo "✓ Target created successfully"
    echo "  - ID: $TARGET_ID"
    echo "  - Name: $TARGET_NAME"
else
    echo "✗ Failed to create target"
    echo "Response: $TARGET_RESPONSE"
    exit 1
fi

echo ""
echo "============================================"
echo "Step 2: Creating Analysis Profile"
echo "============================================"

PROFILE_RESPONSE=$(curl --fail --silent --show-error -X POST "${BASE_URL}/analysis/profiles" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "profile1",
    "description": "Analysis profile for cloud readiness assessment",
    "mode": {
      "withDeps": false
    },
    "scope": {
      "withKnownLibs": false,
      "packages": {
        "included": [],
        "excluded": []
      }
    },
    "rules": {
      "targets": [{"id": '"$TARGET_ID"'}],
      "labels": {
        "included": [],
        "excluded": []
      }
    }
  }')

PROFILE_ID=$(echo $PROFILE_RESPONSE | jq -r '.id')
PROFILE_NAME=$(echo $PROFILE_RESPONSE | jq -r '.name')

if [ "$PROFILE_ID" != "null" ] && [ "$PROFILE_ID" != "" ]; then
    echo "✓ Analysis Profile created successfully"
    echo "  - ID: $PROFILE_ID"
    echo "  - Name: $PROFILE_NAME"
    echo "  - Target: $TARGET_NAME (ID: $TARGET_ID)"
else
    echo "✗ Failed to create analysis profile"
    echo "Response: $PROFILE_RESPONSE"
    exit 1
fi

echo ""
echo "============================================"
echo "Step 3: Creating Application"
echo "============================================"

APP_RESPONSE=$(curl --fail --silent --show-error -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "application1",
    "description": "Test application for cloud readiness assessment",
    "comments": "Created via automated script"
  }')

APP_ID=$(echo $APP_RESPONSE | jq -r '.id')
APP_NAME=$(echo $APP_RESPONSE | jq -r '.name')

if [ "$APP_ID" != "null" ] && [ "$APP_ID" != "" ]; then
    echo "✓ Application created successfully"
    echo "  - ID: $APP_ID"
    echo "  - Name: $APP_NAME"
else
    echo "✗ Failed to create application"
    echo "Response: $APP_RESPONSE"
    exit 1
fi

echo ""
echo "============================================"
echo "Step 4: Creating Archetype with Target Profile"
echo "============================================"

ARCHETYPE_RESPONSE=$(curl --fail --silent --show-error -X POST "${BASE_URL}/archetypes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "archetype1",
    "description": "Archetype for cloud-native applications",
    "comments": "Includes cloud readiness analysis profile",
    "profiles": [
      {
        "name": "TargetProfile1",
        "analysisProfile": {"id": '"$PROFILE_ID"'}
      }
    ],
    "tags": [],
    "criteria": [],
    "stakeholders": [],
    "stakeholderGroups": []
  }')

ARCHETYPE_ID=$(echo $ARCHETYPE_RESPONSE | jq -r '.id')
ARCHETYPE_NAME=$(echo $ARCHETYPE_RESPONSE | jq -r '.name')
TARGET_PROFILE_ID=$(echo $ARCHETYPE_RESPONSE | jq -r '.profiles[0].id')
TARGET_PROFILE_NAME=$(echo $ARCHETYPE_RESPONSE | jq -r '.profiles[0].name')

if [ "$ARCHETYPE_ID" != "null" ] && [ "$ARCHETYPE_ID" != "" ]; then
    echo "✓ Archetype created successfully"
    echo "  - ID: $ARCHETYPE_ID"
    echo "  - Name: $ARCHETYPE_NAME"
    echo "  - Target Profile: $TARGET_PROFILE_NAME (ID: $TARGET_PROFILE_ID)"
    echo "  - Analysis Profile: $PROFILE_NAME (ID: $PROFILE_ID)"
else
    echo "✗ Failed to create archetype"
    echo "Response: $ARCHETYPE_RESPONSE"
    exit 1
fi

echo ""
echo "============================================"
echo "Summary of Created Entities"
echo "============================================"
echo "1. Target:"
echo "   - Name: $TARGET_NAME"
echo "   - ID: $TARGET_ID"
echo ""
echo "2. Analysis Profile:"
echo "   - Name: $PROFILE_NAME"
echo "   - ID: $PROFILE_ID"
echo "   - Target: $TARGET_NAME"
echo ""
echo "3. Application:"
echo "   - Name: $APP_NAME"
echo "   - ID: $APP_ID"
echo ""
echo "4. Archetype:"
echo "   - Name: $ARCHETYPE_NAME"
echo "   - ID: $ARCHETYPE_ID"
echo "   - Target Profile: $TARGET_PROFILE_NAME (ID: $TARGET_PROFILE_ID)"
echo "   - Analysis Profile: $PROFILE_NAME"
echo ""
echo "============================================"
echo "Verification"
echo "============================================"

# Curl options for safe verification requests
CURL_VERIFY_OPTS=(--fail --silent --show-error --connect-timeout 5 --max-time 10)

echo ""
echo "Applications:"
curl "${CURL_VERIFY_OPTS[@]}" "${BASE_URL}/applications" | jq '.[] | {id, name, description}'

echo ""
echo "Analysis Profiles:"
curl "${CURL_VERIFY_OPTS[@]}" "${BASE_URL}/analysis/profiles" | jq '.[] | {id, name, description, targets: .rules.targets}'

echo ""
echo "Archetypes:"
curl "${CURL_VERIFY_OPTS[@]}" "${BASE_URL}/archetypes" | jq '.[] | {id, name, description, profiles: .profiles | map({id, name, analysisProfile})}'

echo ""
echo "============================================"
echo "✓ All entities created successfully!"
echo "============================================"
