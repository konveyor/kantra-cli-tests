#!/bin/bash
# Remove all hub entities: archetypes, applications, analysis profiles.
# Targets are not deleted (built-in or custom).
#
# Usage: ./cleanup-hub-entities.sh
#        HUB_BASE_URL=localhost:8080/hub ./cleanup-hub-entities.sh
# Auth: HUB_USERNAME/HUB_PASSWORD (default admin/admin), or set HUB_TOKEN to skip login.
# TLS: set HUB_SECURE=true to verify certificates (default: insecure / -k).
set -e

HUB_URL="${HUB_BASE_URL:-localhost:8080}"
HUB_USERNAME="${HUB_USERNAME:-admin}"
HUB_PASSWORD="${HUB_PASSWORD:-admin}"
HUB_SECURE="${HUB_SECURE:-false}"

if [[ "$HUB_URL" != http* ]]; then
    BASE_URL="http://${HUB_URL}"
else
    BASE_URL="${HUB_URL}"
fi

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

hub_api_url() {
    echo "${1%/}/${2#/}"
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

resolve_hub_api_base() {
    local base="${1%/}"
    if [[ "$base" == */hub ]]; then
        echo "$base"
        return
    fi

    local candidate probe
    for candidate in "$base" "${base}/hub"; do
        probe=$(curl "${CURL_OPTS[@]}" "${candidate}/targets" 2>/dev/null || true)
        if echo "$probe" | jq -e 'type == "array"' >/dev/null 2>&1; then
            if [ "$candidate" != "$base" ]; then
                echo "Using API base ${candidate} (auto-detected)" >&2
            fi
            echo "$candidate"
            return
        fi
    done

    echo "$base"
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
echo "Cleaning up Hub Entities"
echo "============================================"
echo "Hub URL: $BASE_URL"
echo ""

HUB_TOKEN=$(obtain_hub_token)
CURL_OPTS=("${CURL_TLS_OPTS[@]}" --silent --show-error --max-time 15)
[ -n "$HUB_TOKEN" ] && CURL_OPTS+=(-H "Authorization: Bearer ${HUB_TOKEN}")
BASE_URL=$(resolve_hub_api_base "$BASE_URL")

# Discover /hub if root returns no data
fetch_json() {
    curl "${CURL_OPTS[@]}" "$1" 2>/dev/null | jq -c 'if type == "array" then . else [] end' 2>/dev/null || echo "[]"
}

# Delete in reverse dependency order: archetypes -> applications -> analysis profiles
echo "----------------------------------------"
echo "1. Deleting Archetypes"
echo "----------------------------------------"
ARCHETYPES_JSON=$(fetch_json "${BASE_URL}/archetypes")
COUNT=0
for id in $(echo "$ARCHETYPES_JSON" | jq -r '.[].id' 2>/dev/null); do
    [ -z "$id" ] || [ "$id" = "null" ] && continue
    if curl "${CURL_OPTS[@]}" -X DELETE "${BASE_URL}/archetypes/${id}" 2>/dev/null; then
        echo "  Deleted archetype ID: $id"
        COUNT=$((COUNT + 1))
    else
        echo "  Failed or already gone: archetype $id" >&2
    fi
done
echo "  Archetypes removed: $COUNT"

echo ""
echo "----------------------------------------"
echo "2. Deleting Applications"
echo "----------------------------------------"
APPS_JSON=$(fetch_json "${BASE_URL}/applications")
COUNT=0
for id in $(echo "$APPS_JSON" | jq -r '.[].id' 2>/dev/null); do
    [ -z "$id" ] || [ "$id" = "null" ] && continue
    if curl "${CURL_OPTS[@]}" -X DELETE "${BASE_URL}/applications/${id}" 2>/dev/null; then
        echo "  Deleted application ID: $id"
        COUNT=$((COUNT + 1))
    else
        echo "  Failed or already gone: application $id" >&2
    fi
done
echo "  Applications removed: $COUNT"

echo ""
echo "----------------------------------------"
echo "3. Deleting Analysis Profiles"
echo "----------------------------------------"
PROFILES_JSON=$(fetch_json "${BASE_URL}/analysis/profiles")
COUNT=0
for id in $(echo "$PROFILES_JSON" | jq -r '.[].id' 2>/dev/null); do
    [ -z "$id" ] || [ "$id" = "null" ] && continue
    if curl "${CURL_OPTS[@]}" -X DELETE "${BASE_URL}/analysis/profiles/${id}" 2>/dev/null; then
        echo "  Deleted analysis profile ID: $id"
        COUNT=$((COUNT + 1))
    else
        echo "  Failed or already gone: profile $id" >&2
    fi
done
echo "  Analysis profiles removed: $COUNT"

echo ""
echo "============================================"
echo "✓ Cleanup finished"
echo "============================================"
