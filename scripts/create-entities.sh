#!/bin/bash
set -e

# Configuration
# If you get 404 on /targets, try: HUB_BASE_URL=localhost:8080/hub
HUB_URL="${HUB_BASE_URL:-localhost:8080}"
# Ensure URL has a scheme
if [[ "$HUB_URL" != http* ]]; then
    BASE_URL="http://${HUB_URL}"
else
    BASE_URL="${HUB_URL}"
fi

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

# If root returns no data or invalid JSON, retry with /hub (same logic as dump script)
TARGETS_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/targets" 2>/dev/null || echo "[]")
TARGETS_LEN=$(echo "$TARGETS_JSON" | jq -r 'if type == "array" then length else 0 end' 2>/dev/null || echo "0")
[ -z "$TARGETS_LEN" ] || [ "$TARGETS_LEN" = "null" ] && TARGETS_LEN="0"
if [ "${TARGETS_LEN:-0}" -eq 0 ] && [[ "$BASE_URL" != */hub ]]; then
    echo "Targets empty at root, using ${BASE_URL}/hub ..."
    BASE_URL="${BASE_URL}/hub"
    TARGETS_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/targets" 2>/dev/null || echo "[]")
fi
# Ensure TARGETS_JSON is valid JSON array (curl may return HTML on 404)
TARGETS_JSON=$(echo "$TARGETS_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")

# -----------------------------------------------------------------------------
# Custom target creation (commented out): use only built-in targets in the profile.
# -----------------------------------------------------------------------------
# echo ""
# echo "============================================"
# echo "Step 1: Getting or Creating Target (cloud-readiness)"
# echo "============================================"
# TARGET_ID=$(echo "$TARGETS_JSON" | jq -r '.[] | select(.name == "cloud-readiness") | .id' 2>/dev/null | head -1)
# if [ -n "$TARGET_ID" ] && [ "$TARGET_ID" != "null" ]; then
#     echo "✓ Using existing target 'cloud-readiness' (ID: $TARGET_ID)"
# else
#     echo "Creating target 'cloud-readiness'..."
#     TARGET_RESPONSE=$(curl --silent --show-error -w "\n%{http_code}" -X POST "${BASE_URL}/targets" \
#       -H "Content-Type: application/json" \
#       -d '{"name":"cloud-readiness","description":"Cloud readiness target for containerization","custom":true,"labels":[],"image":{"id":1}}')
#     HTTP_BODY=$(echo "$TARGET_RESPONSE" | head -n -1)
#     HTTP_CODE=$(echo "$TARGET_RESPONSE" | tail -n 1)
#     if [ "$HTTP_CODE" = "404" ] && [[ "$BASE_URL" != */hub ]]; then
#         BASE_URL="${BASE_URL}/hub"
#         TARGET_RESPONSE=$(curl --silent --show-error -w "\n%{http_code}" -X POST "${BASE_URL}/targets" ...
#         ...
#     fi
#     ...
# fi

# Resolve profile target names to IDs (built-in only: Containerization, Linux)
TARGET_ID_CONTAINERIZATION=$(echo "$TARGETS_JSON" | jq -r '.[] | select(.name == "Containerization") | .id' 2>/dev/null | head -1)
TARGET_ID_LINUX=$(echo "$TARGETS_JSON" | jq -r '.[] | select(.name == "Linux") | .id' 2>/dev/null | head -1)
# Build rules.targets array; only include built-in targets that exist (no custom target)
TARGET_IDS_FOR_PROFILE="[]"
[ -n "$TARGET_ID_CONTAINERIZATION" ] && [ "$TARGET_ID_CONTAINERIZATION" != "null" ] && TARGET_IDS_FOR_PROFILE=$(echo "$TARGET_IDS_FOR_PROFILE" | jq -c --argjson id "$TARGET_ID_CONTAINERIZATION" '. + [{"id": $id}]' 2>/dev/null) || true
[ -n "$TARGET_ID_LINUX" ] && [ "$TARGET_ID_LINUX" != "null" ] && TARGET_IDS_FOR_PROFILE=$(echo "$TARGET_IDS_FOR_PROFILE" | jq -c --argjson id "$TARGET_ID_LINUX" '. + [{"id": $id}]' 2>/dev/null) || true
# Ensure we have valid JSON for profile payload
TARGET_IDS_FOR_PROFILE=$(echo "$TARGET_IDS_FOR_PROFILE" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")

echo ""
echo "============================================"
echo "Step 2: Getting or Creating Analysis Profile"
echo "============================================"

PROFILES_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/analysis/profiles" 2>/dev/null || echo "[]")
# Ensure PROFILES_JSON is valid JSON array (hub may return HTML/error or different shape when not ready)
PROFILES_JSON=$(echo "$PROFILES_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")
PROFILE_ID=$(echo "$PROFILES_JSON" | jq -r '.[] | select(.name == "profile1") | .id' 2>/dev/null | head -1)
PROFILE_NAME="profile1"

if [ -n "$PROFILE_ID" ] && [ "$PROFILE_ID" != "null" ]; then
    echo "✓ Using existing analysis profile 'profile1' (ID: $PROFILE_ID)"
else
    PROFILE_PAYLOAD=$(jq -n -c \
      --argjson targets "$TARGET_IDS_FOR_PROFILE" \
      '{
        name: "profile1",
        description: "Analysis profile for cloud readiness assessment",
        mode: { withDeps: false },
        scope: { withKnownLibs: false, packages: { included: [], excluded: [] } },
        rules: { targets: $targets, labels: { included: [], excluded: [] } }
      }')
    PROFILE_RESPONSE=$(curl --silent --show-error -w "\n%{http_code}" -X POST "${BASE_URL}/analysis/profiles" \
      -H "Content-Type: application/json" \
      -d "$PROFILE_PAYLOAD")
    HTTP_BODY=$(echo "$PROFILE_RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$PROFILE_RESPONSE" | tail -n 1)
    PROFILE_ID=$(echo "$HTTP_BODY" | jq -r 'if type == "object" and has("id") then .id else empty end' 2>/dev/null | head -1)
    if [ -z "$PROFILE_ID" ] || [ "$PROFILE_ID" = "null" ]; then
        # May already exist; try to get existing
        PROFILES_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/analysis/profiles" 2>/dev/null || echo "[]")
        PROFILES_JSON=$(echo "$PROFILES_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")
        PROFILE_ID=$(echo "$PROFILES_JSON" | jq -r '.[] | select(.name == "profile1") | .id' 2>/dev/null | head -1)
    fi
    if [ -z "$PROFILE_ID" ] || [ "$PROFILE_ID" = "null" ]; then
        echo "✗ Failed to create or find analysis profile 'profile1'"
        exit 1
    fi
    echo "✓ Created analysis profile 'profile1' (ID: $PROFILE_ID)"
fi
echo "  - Targets: Containerization, Linux"

echo ""
echo "============================================"
echo "Step 3: Getting or Creating Application"
echo "============================================"

APPS_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/applications" 2>/dev/null || echo "[]")
APPS_JSON=$(echo "$APPS_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")
APP_ID=$(echo "$APPS_JSON" | jq -r '.[] | select(.name == "application1") | .id' 2>/dev/null | head -1)
APP_NAME="application1"

if [ -n "$APP_ID" ] && [ "$APP_ID" != "null" ]; then
    echo "✓ Using existing application 'application1' (ID: $APP_ID)"
else
    # Resolve tag names to IDs (Maven, Java, Spring, Spring Boot); tags may be under .[] or .[].tags[]
    TAGS_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/tags" 2>/dev/null || echo "[]")
    tag_id() { echo "$TAGS_JSON" | jq -r --arg n "$1" '(if type == "array" then . else [] end) | (.[]? | select(.name == $n) | .id) // (.[]? | .tags[]? | select(.name == $n) | .id) // empty' 2>/dev/null | head -1; }
    TAG_IDS_APP="[]"
    for name in "Maven" "Java" "Spring" "Spring Boot"; do
        id=$(tag_id "$name")
        [ -n "$id" ] && [ "$id" != "null" ] && TAG_IDS_APP=$(echo "$TAG_IDS_APP" | jq -c --argjson id "$id" '. + [{"id": $id}]')
    done

    APP_PAYLOAD=$(jq -n -c \
      --argjson tagIds "$TAG_IDS_APP" \
      '{
        name: "application1",
        description: "Test application for cloud readiness assessment",
        comments: "Created via automated script",
        repository: { kind: "git", url: "https://github.com/ibraginsky/book-server", branch: "", tag: "", path: "" },
        tags: $tagIds
      }')
    APP_RESPONSE=$(curl --silent --show-error -w "\n%{http_code}" -X POST "${BASE_URL}/applications" \
      -H "Content-Type: application/json" \
      -d "$APP_PAYLOAD")
    HTTP_BODY=$(echo "$APP_RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$APP_RESPONSE" | tail -n 1)
    APP_ID=$(echo "$HTTP_BODY" | jq -r 'if type == "object" and has("id") then .id else empty end' 2>/dev/null | head -1)
    if [ -z "$APP_ID" ] || [ "$APP_ID" = "null" ]; then
        APPS_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/applications" 2>/dev/null || echo "[]")
        APPS_JSON=$(echo "$APPS_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")
        APP_ID=$(echo "$APPS_JSON" | jq -r '.[] | select(.name == "application1") | .id' 2>/dev/null | head -1)
    fi
    if [ -z "$APP_ID" ] || [ "$APP_ID" = "null" ]; then
        echo "✗ Failed to create or find application 'application1'"
        exit 1
    fi
    echo "✓ Created application 'application1' (ID: $APP_ID)"
fi

echo ""
echo "============================================"
echo "Step 4: Getting or Creating Archetype"
echo "============================================"

ARCHETYPES_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/archetypes" 2>/dev/null || echo "[]")
ARCHETYPES_JSON=$(echo "$ARCHETYPES_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")
ARCHETYPE_ID=$(echo "$ARCHETYPES_JSON" | jq -r '.[] | select(.name == "archetype1") | .id' 2>/dev/null | head -1)
ARCHETYPE_NAME="archetype1"

if [ -n "$ARCHETYPE_ID" ] && [ "$ARCHETYPE_ID" != "null" ]; then
    TARGET_PROFILE_ID=$(echo "$ARCHETYPES_JSON" | jq -r '.[] | select(.name == "archetype1") | .profiles[0].id' 2>/dev/null | head -1)
    TARGET_PROFILE_NAME=$(echo "$ARCHETYPES_JSON" | jq -r '.[] | select(.name == "archetype1") | .profiles[0].name' 2>/dev/null | head -1)
    echo "✓ Using existing archetype 'archetype1' (ID: $ARCHETYPE_ID)"
else
    # Archetype criteria use tag IDs (e.g. Java); tag_id may be defined in Step 3
    if ! type tag_id &>/dev/null; then
        TAGS_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/tags" 2>/dev/null || echo "[]")
        tag_id() { echo "$TAGS_JSON" | jq -r --arg n "$1" '(if type == "array" then . else [] end) | (.[]? | select(.name == $n) | .id) // (.[]? | .tags[]? | select(.name == $n) | .id) // empty' 2>/dev/null | head -1; }
    fi
    JAVA_TAG_ID=$(tag_id "Java")
    CRITERIA_JSON="[]"
    [ -n "$JAVA_TAG_ID" ] && [ "$JAVA_TAG_ID" != "null" ] && CRITERIA_JSON=$(jq -n -c --argjson id "$JAVA_TAG_ID" '[{id: $id}]')

    ARCHETYPE_PAYLOAD=$(jq -n -c \
      --argjson profileId "$PROFILE_ID" \
      --argjson criteria "$CRITERIA_JSON" \
      '{
        name: "archetype1",
        description: "Archetype for cloud-native applications",
        comments: "Includes cloud readiness analysis profile",
        profiles: [{ name: "TargetProfile1", analysisProfile: { id: $profileId } }],
        tags: [],
        criteria: $criteria,
        stakeholders: [],
        stakeholderGroups: []
      }')
    ARCHETYPE_RESPONSE=$(curl --silent --show-error -w "\n%{http_code}" -X POST "${BASE_URL}/archetypes" \
      -H "Content-Type: application/json" \
      -d "$ARCHETYPE_PAYLOAD")
    HTTP_BODY=$(echo "$ARCHETYPE_RESPONSE" | head -n -1)
    HTTP_CODE=$(echo "$ARCHETYPE_RESPONSE" | tail -n 1)
    ARCHETYPE_ID=$(echo "$HTTP_BODY" | jq -r 'if type == "object" and has("id") then .id else empty end' 2>/dev/null | head -1)
    if [ -z "$ARCHETYPE_ID" ] || [ "$ARCHETYPE_ID" = "null" ]; then
        ARCHETYPES_JSON=$(curl --silent --show-error --max-time 10 "${BASE_URL}/archetypes" 2>/dev/null || echo "[]")
        ARCHETYPES_JSON=$(echo "$ARCHETYPES_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")
        ARCHETYPE_ID=$(echo "$ARCHETYPES_JSON" | jq -r '.[] | select(.name == "archetype1") | .id' 2>/dev/null | head -1)
    fi
    if [ -z "$ARCHETYPE_ID" ] || [ "$ARCHETYPE_ID" = "null" ]; then
        echo "✗ Failed to create or find archetype 'archetype1'"
        exit 1
    fi
    TARGET_PROFILE_ID=$(echo "$HTTP_BODY" | jq -r 'if type == "object" and (.profiles | type == "array") and (.profiles[0] | type == "object") then .profiles[0].id else empty end' 2>/dev/null | head -1)
    TARGET_PROFILE_NAME=$(echo "$HTTP_BODY" | jq -r 'if type == "object" and (.profiles | type == "array") and (.profiles[0] | type == "object") then .profiles[0].name else empty end' 2>/dev/null | head -1)
    echo "✓ Created archetype 'archetype1' (ID: $ARCHETYPE_ID)"
fi
echo "  - Target Profile: ${TARGET_PROFILE_NAME:-TargetProfile1} (ID: $TARGET_PROFILE_ID)"
echo "  - Analysis Profile: $PROFILE_NAME (ID: $PROFILE_ID)"

echo ""
echo "============================================"
echo "Summary of Created Entities"
echo "============================================"
# echo "1. Target: (custom target creation disabled)"
# echo "   - Name: cloud-readiness"
# echo "   - ID: $TARGET_ID"
# echo ""
echo "1. Analysis Profile:"
echo "   - Name: $PROFILE_NAME"
echo "   - ID: $PROFILE_ID"
echo "   - Targets: Containerization, Linux"
echo ""
echo "2. Application:"
echo "   - Name: $APP_NAME"
echo "   - ID: $APP_ID"
echo ""
echo "3. Archetype:"
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
