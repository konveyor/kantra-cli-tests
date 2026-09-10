#!/bin/bash
set -e

# Configuration
# If you get 404 on /targets, try: HUB_BASE_URL=localhost:8080/hub
# Auth: HUB_USERNAME/HUB_PASSWORD (default admin/admin), or set HUB_TOKEN to skip login.
# TLS: set HUB_SECURE=true to verify certificates (default: insecure / -k).
HUB_URL="${HUB_BASE_URL:-localhost:8080}"
HUB_USERNAME="${HUB_USERNAME:-admin}"
HUB_PASSWORD="${HUB_PASSWORD:-admin}"
HUB_SECURE="${HUB_SECURE:-false}"

# Ensure URL has a scheme
if [[ "$HUB_URL" != http* ]]; then
    BASE_URL="http://${HUB_URL}"
else
    BASE_URL="${HUB_URL}"
fi

# Generate unique suffix for entity names
RANDOM_SUFFIX="$(date +%s)"
PROFILE_NAME="profile-${RANDOM_SUFFIX}"
APP_NAME="application-${RANDOM_SUFFIX}"
ARCHETYPE_NAME="archetype-${RANDOM_SUFFIX}"
TARGET_PROFILE_NAME="TargetProfile-${RANDOM_SUFFIX}"

CURL_TLS_OPTS=()
[[ "$(echo "$HUB_SECURE" | tr '[:upper:]' '[:lower:]')" != "true" ]] && CURL_TLS_OPTS+=(-k)

hub_auth_url() {
    local base="${1%/}"
    if [[ "$base" == */hub ]]; then
        echo "${base}/auth/tokens"
    elif [[ "$base" == https://* ]]; then
        echo "${base}/hub/auth/tokens"
    else
        echo "${base}/auth/tokens"
    fi
}

hub_resource_urls() {
    local base="${1%/}" path="${2#/}"
    if [[ "$base" == */hub ]]; then
        echo "${base}/${path}"
    else
        echo "${base}/${path}"
        echo "${base}/hub/${path}"
    fi
}

hub_allows_anonymous_api() {
    local url http_code body
    for url in $(hub_resource_urls "$BASE_URL" targets); do
        body=$(curl "${CURL_TLS_OPTS[@]}" -sS --connect-timeout 3 --max-time 15 -w "\n%{http_code}" "$url" 2>/dev/null || echo -e "\n000")
        http_code=$(echo "$body" | tail -n1)
        body=$(echo "$body" | sed '$d')
        if [ "$http_code" = "200" ] && echo "$body" | jq -e 'type == "array"' >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}

obtain_hub_token() {
    if [ -n "${HUB_TOKEN:-}" ]; then
        echo "Using provided HUB_TOKEN" >&2
        echo "$HUB_TOKEN"
        return 0
    fi

    echo "Authenticating as ${HUB_USERNAME}..." >&2
    local auth_url basic_auth response token
    basic_auth=$(printf '%s:%s' "$HUB_USERNAME" "$HUB_PASSWORD" | base64 -w0 2>/dev/null \
        || printf '%s:%s' "$HUB_USERNAME" "$HUB_PASSWORD" | base64)

    for auth_url in "$(hub_auth_url "$BASE_URL")" "${BASE_URL%/}/hub/auth/tokens" "${BASE_URL%/}/auth/tokens"; do
        [ -z "$auth_url" ] && continue
        response=$(curl "${CURL_TLS_OPTS[@]}" -sS --connect-timeout 5 --max-time 15 -X POST \
            "$auth_url" \
            -H "Authorization: Basic ${basic_auth}" \
            -H "Content-Type: application/json" \
            -d '{}' || true)
        token=$(echo "$response" | jq -r '.token // empty' 2>/dev/null)
        if [ -z "$token" ]; then
            token=$(echo "$response" | awk '/^token:/{print $2}')
        fi
        if [ -n "$token" ]; then
            echo "✓ Authentication successful (${auth_url})" >&2
            echo "$token"
            return 0
        fi
    done

    if hub_allows_anonymous_api; then
        echo "Hub auth not required; proceeding without API token" >&2
        echo ""
        return 0
    fi

    echo "✗ Failed to authenticate against Hub" >&2
    echo "Last response: $response" >&2
    exit 1
}

echo "============================================"
echo "Creating Hub Entities (random names)"
echo "============================================"
echo "Hub URL: $BASE_URL"
echo "Unique suffix: ${RANDOM_SUFFIX}"
echo ""

check_hub_ready() {
    echo "Checking if hub is ready..."
    local CURL_OPTS=("${CURL_TLS_OPTS[@]}" --silent --show-error --connect-timeout 3 --max-time 15)
    for i in {1..30}; do
        local http_code
        http_code=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" "${BASE_URL}/applications" 2>/dev/null || echo "000")
        if [[ "$http_code" =~ ^(200|401|403)$ ]]; then
            echo "✓ Hub is ready!"
            return 0
        fi
        echo "Attempt $i: Hub not ready yet, waiting..."
        sleep 2
    done
    echo "✗ Hub did not become ready in time"
    exit 1
}

check_hub_ready

HUB_TOKEN=$(obtain_hub_token)
CURL_OPTS=("${CURL_TLS_OPTS[@]}" --silent --show-error --max-time 15)
[ -n "$HUB_TOKEN" ] && CURL_OPTS+=(-H "Authorization: Bearer ${HUB_TOKEN}")

TARGETS_JSON=$(curl "${CURL_OPTS[@]}" "${BASE_URL}/targets" 2>/dev/null || echo "[]")
TARGETS_LEN=$(echo "$TARGETS_JSON" | jq -r 'if type == "array" then length else 0 end' 2>/dev/null || echo "0")
[ -z "$TARGETS_LEN" ] || [ "$TARGETS_LEN" = "null" ] && TARGETS_LEN="0"
if [ "${TARGETS_LEN:-0}" -eq 0 ] && [[ "$BASE_URL" != */hub ]]; then
    echo "Targets empty at root, using ${BASE_URL}/hub ..."
    BASE_URL="${BASE_URL}/hub"
    TARGETS_JSON=$(curl "${CURL_OPTS[@]}" "${BASE_URL}/targets" 2>/dev/null || echo "[]")
fi
TARGETS_JSON=$(echo "$TARGETS_JSON" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")

# Resolve profile target names to IDs (built-in only: Containerization, Linux)
TARGET_ID_CONTAINERIZATION=$(echo "$TARGETS_JSON" | jq -r '.[] | select(.name == "Containerization") | .id' 2>/dev/null | head -1)
TARGET_ID_LINUX=$(echo "$TARGETS_JSON" | jq -r '.[] | select(.name == "Linux") | .id' 2>/dev/null | head -1)
TARGET_IDS_FOR_PROFILE="[]"
[ -n "$TARGET_ID_CONTAINERIZATION" ] && [ "$TARGET_ID_CONTAINERIZATION" != "null" ] && TARGET_IDS_FOR_PROFILE=$(echo "$TARGET_IDS_FOR_PROFILE" | jq -c --argjson id "$TARGET_ID_CONTAINERIZATION" '. + [{"id": $id}]' 2>/dev/null) || true
[ -n "$TARGET_ID_LINUX" ] && [ "$TARGET_ID_LINUX" != "null" ] && TARGET_IDS_FOR_PROFILE=$(echo "$TARGET_IDS_FOR_PROFILE" | jq -c --argjson id "$TARGET_ID_LINUX" '. + [{"id": $id}]' 2>/dev/null) || true
TARGET_IDS_FOR_PROFILE=$(echo "$TARGET_IDS_FOR_PROFILE" | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]")

echo ""
echo "============================================"
echo "Step 1: Creating Analysis Profile"
echo "============================================"

PROFILE_PAYLOAD=$(jq -n -c \
  --arg name "$PROFILE_NAME" \
  --argjson targets "$TARGET_IDS_FOR_PROFILE" \
  '{
    name: $name,
    description: "Analysis profile for cloud readiness assessment",
    mode: { withDeps: false },
    scope: { withKnownLibs: false, packages: { included: [], excluded: [] } },
    rules: { targets: $targets, labels: { included: [], excluded: [] } }
  }')
PROFILE_RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X POST "${BASE_URL}/analysis/profiles" \
  -H "Content-Type: application/json" \
  -d "$PROFILE_PAYLOAD")
HTTP_BODY=$(echo "$PROFILE_RESPONSE" | head -n -1)
PROFILE_ID=$(echo "$HTTP_BODY" | jq -r '.id')
if [ -z "$PROFILE_ID" ] || [ "$PROFILE_ID" = "null" ]; then
    echo "✗ Failed to create analysis profile '${PROFILE_NAME}'"
    echo "Response: $HTTP_BODY"
    exit 1
fi
echo "✓ Created analysis profile '${PROFILE_NAME}' (ID: $PROFILE_ID)"
echo "  - Targets: Containerization, Linux"

echo ""
echo "============================================"
echo "Step 2: Creating Application"
echo "============================================"

TAGS_JSON=$(curl "${CURL_OPTS[@]}" "${BASE_URL}/tags" 2>/dev/null || echo "[]")
tag_id() { echo "$TAGS_JSON" | jq -r --arg n "$1" '(if type == "array" then . else [] end) | (.[]? | select(.name == $n) | .id) // (.[]? | .tags[]? | select(.name == $n) | .id) // empty' 2>/dev/null | head -1; }
TAG_IDS_APP="[]"
for name in "Maven" "Java" "Spring" "Spring Boot"; do
    id=$(tag_id "$name")
    [ -n "$id" ] && [ "$id" != "null" ] && TAG_IDS_APP=$(echo "$TAG_IDS_APP" | jq -c --argjson id "$id" '. + [{"id": $id}]')
done

APP_PAYLOAD=$(jq -n -c \
  --arg name "$APP_NAME" \
  --argjson tagIds "$TAG_IDS_APP" \
  '{
    name: $name,
    description: "Test application for cloud readiness assessment",
    comments: "Created via automated script",
    repository: { kind: "git", url: "https://github.com/ibraginsky/book-server", branch: "", tag: "", path: "" },
    tags: $tagIds
  }')
APP_RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -d "$APP_PAYLOAD")
HTTP_BODY=$(echo "$APP_RESPONSE" | head -n -1)
APP_ID=$(echo "$HTTP_BODY" | jq -r '.id')
if [ -z "$APP_ID" ] || [ "$APP_ID" = "null" ]; then
    echo "✗ Failed to create application '${APP_NAME}'"
    echo "Response: $HTTP_BODY"
    exit 1
fi
echo "✓ Created application '${APP_NAME}' (ID: $APP_ID)"

echo ""
echo "============================================"
echo "Step 3: Creating Archetype"
echo "============================================"

JAVA_TAG_ID=$(tag_id "Java")
CRITERIA_JSON="[]"
[ -n "$JAVA_TAG_ID" ] && [ "$JAVA_TAG_ID" != "null" ] && CRITERIA_JSON=$(jq -n -c --argjson id "$JAVA_TAG_ID" '[{id: $id}]')

ARCHETYPE_PAYLOAD=$(jq -n -c \
  --arg name "$ARCHETYPE_NAME" \
  --arg targetProfileName "$TARGET_PROFILE_NAME" \
  --argjson profileId "$PROFILE_ID" \
  --argjson criteria "$CRITERIA_JSON" \
  '{
    name: $name,
    description: "Archetype for cloud-native applications",
    comments: "Includes cloud readiness analysis profile",
    profiles: [{ name: $targetProfileName, analysisProfile: { id: $profileId } }],
    tags: [],
    criteria: $criteria,
    stakeholders: [],
    stakeholderGroups: []
  }')
ARCHETYPE_RESPONSE=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" -X POST "${BASE_URL}/archetypes" \
  -H "Content-Type: application/json" \
  -d "$ARCHETYPE_PAYLOAD")
HTTP_BODY=$(echo "$ARCHETYPE_RESPONSE" | head -n -1)
ARCHETYPE_ID=$(echo "$HTTP_BODY" | jq -r '.id')
if [ -z "$ARCHETYPE_ID" ] || [ "$ARCHETYPE_ID" = "null" ]; then
    echo "✗ Failed to create archetype '${ARCHETYPE_NAME}'"
    echo "Response: $HTTP_BODY"
    exit 1
fi
TARGET_PROFILE_ID=$(echo "$HTTP_BODY" | jq -r '.profiles[0].id')
TARGET_PROFILE_NAME=$(echo "$HTTP_BODY" | jq -r '.profiles[0].name')
echo "✓ Created archetype '${ARCHETYPE_NAME}' (ID: $ARCHETYPE_ID)"
echo "  - Target Profile: ${TARGET_PROFILE_NAME} (ID: $TARGET_PROFILE_ID)"
echo "  - Analysis Profile: ${PROFILE_NAME} (ID: $PROFILE_ID)"

echo ""
echo "============================================"
echo "Summary of Created Entities"
echo "============================================"
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

CURL_VERIFY_OPTS=("${CURL_TLS_OPTS[@]}" --fail --silent --show-error --connect-timeout 5 --max-time 10)
[ -n "$HUB_TOKEN" ] && CURL_VERIFY_OPTS+=(-H "Authorization: Bearer ${HUB_TOKEN}")

echo ""
echo "Applications:"
curl "${CURL_VERIFY_OPTS[@]}" "${BASE_URL}/applications" | jq --arg name "$APP_NAME" '.[] | select(.name == $name) | {id, name, description}'

echo ""
echo "Analysis Profiles:"
curl "${CURL_VERIFY_OPTS[@]}" "${BASE_URL}/analysis/profiles" | jq --arg name "$PROFILE_NAME" '.[] | select(.name == $name) | {id, name, description, targets: .rules.targets}'

echo ""
echo "Archetypes:"
curl "${CURL_VERIFY_OPTS[@]}" "${BASE_URL}/archetypes" | jq --arg name "$ARCHETYPE_NAME" '.[] | select(.name == $name) | {id, name, description, profiles: .profiles | map({id, name, analysisProfile})}'

echo ""
echo "============================================"
echo "✓ All entities created successfully!"
echo "============================================"
