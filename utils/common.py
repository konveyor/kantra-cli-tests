import base64
import json
import os
import platform
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager

import pytest
from functools import wraps

from utils import constants

@contextmanager
def extract_zip_to_temp_dir(application_path):
    """
    Creates a temporary directory and extracts a zip file to it.

    :param application_path: Path to the zip file
    :yield: path to the extracted zip file
    """

    tempdir = tempfile.TemporaryDirectory(dir=os.getenv(constants.PROJECT_PATH))

    # Adjusts the permissions to allow access to subprocesses
    os.chmod(tempdir.name, 0o777)

    with zipfile.ZipFile(application_path, 'r') as zip_ref:
        zip_ref.extractall(tempdir.name)

    yield tempdir.name

def run_containerless_parametrize(func):
    run_local_mode = os.getenv("RUN_LOCAL_MODE")
    if run_local_mode == "true":
        args_list = [{"--run-local=true": None}]
    elif run_local_mode == "false":
        args_list = [{"--run-local=false": None}] if platform.system().lower() != "windows" else []
    else:
        args_list = [{"--run-local=true": None}]  # Always include local mode
        if platform.system().lower() != "windows":
            args_list.append({"--run-local=false": None})  # Add container mode only if not Windows

    @pytest.mark.parametrize(
        "additional_args",
        args_list,
        ids=lambda args: list(args)[0]  # More readable way
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper

def _ruleset_contains_rule(ruleset, rule_id):
    """True if ruleset has violations for rule_id."""
    violations = ruleset.get('violations')
    if violations is None:
        return False
    if isinstance(violations, dict):
        return rule_id in violations
    if isinstance(violations, list):
        return any(
            v.get('ruleID') == rule_id or v.get('ruleId') == rule_id or v.get('rule') == rule_id
            for v in violations
        )
    return False


def _get_violation_by_rule_id(ruleset, rule_id):
    """Return the violation object for rule_id from a ruleset."""
    violations = ruleset.get('violations')
    if not violations:
        return None
    if isinstance(violations, dict):
        return violations.get(rule_id)
    for v in violations:
        if v.get('ruleID') == rule_id or v.get('ruleId') == rule_id or v.get('rule') == rule_id:
            return v
    return None


def _get_rulesets(report_data):
    """Return list of rulesets from report_data."""
    if isinstance(report_data, list):
        return report_data  
    return report_data.get('rulesets', [])


def verify_triggered_rules(report_data, rule_id_list, expected_unmatched_rules = False):
    """

    Args:
        report_data: Report data that includes rulesets
        rule_id_list: List of actual rule IDs we are looking for
        expected_unmatched_rules: Sometimes rulesets can include unmatched rules (on purpose) so expected_unmatched_rules was added to avoid failure

    Returns:

    """

    rulesets = _get_rulesets(report_data)
    errors = []
    for rule_id in rule_id_list:
        ruleset = next(
            (item for item in rulesets if _ruleset_contains_rule(item, rule_id)),
            None,
        )

        if ruleset is None:
            errors.append(f"Error for rule ID '{rule_id}': Ruleset property not found in output.")
            continue # Move to the next rule if the ruleset isn't found

        if len(ruleset.get('skipped', [])) != 0:
            errors.append(f"Error for rule ID '{rule_id}': Custom Rule was skipped. Skipped rules: {ruleset.get('skipped', [])}")

        if len(ruleset.get('unmatched', [])) != 0 and not expected_unmatched_rules:
            errors.append(f"Error for rule ID '{rule_id}': Custom Rule was unmatched. Unmatched rules: {ruleset.get('unmatched', [])}. Expected unmatched: {expected_unmatched_rules}")

        if not _ruleset_contains_rule(ruleset, rule_id):
            errors.append(f"Error for rule ID '{rule_id}': The test rule triggered no violations for this specific rule ID.")

    if errors:
        error_message = "The following rule validation errors occurred:\n" + "\n".join(errors)
        print(f"Failed assertions: {error_message}")
        raise AssertionError(error_message)

def extract_rules(analysis: dict) -> list[str]:
    return [issue.get("rule") for issue in analysis.get("issues", []) if issue.get("rule")]


def verify_triggered_yaml_rules(report_data, rule_id_list, expected_unmatched_rules = False):
    """

        Args:
            report_data: Report data that includes rulesets
            rule_id_list: List of actual rule IDs we are looking for
            expected_unmatched_rules: Sometimes rulesets can include unmatched rules (on purpose) so expected_unmatched_rules was added to avoid failure

        Returns:

        """

    errors = []

    for rule_id in rule_id_list:
        # Find the ruleset that contains this rule ID in its 'violations'
        ruleset = next((item for item in report_data if rule_id in item.get('violations', {})), None)

        if ruleset is None:
            errors.append(f"Error for rule ID '{rule_id}': Ruleset property not found in output.")
            continue  # Move to the next rule if the ruleset isn't found

        if len(ruleset.get('skipped', [])) != 0:
            errors.append(f"Error for rule ID '{rule_id}': Custom Rule was skipped. Skipped rules: {ruleset.get('skipped', [])}")

        if len(ruleset.get('unmatched', [])) != 0 and not expected_unmatched_rules:
            errors.append(f"Error for rule ID '{rule_id}': Custom Rule was unmatched. Unmatched rules: {ruleset.get('unmatched', [])}. Expected unmatched: {expected_unmatched_rules}")

        if 'violations' not in ruleset:
            errors.append(f"Error for rule ID '{rule_id}': Custom rules didn't trigger any violation.")
        elif rule_id not in ruleset['violations']:
            errors.append(f"Error for rule ID '{rule_id}': The test rule triggered no violations for this specific rule ID.")

    if errors:
        error_message = "The following rule validation errors occurred:\n" + "\n".join(errors)
        print(f"Failed assertions: {error_message}")
        raise AssertionError(error_message)

def extract_name_and_violations_from_dictionary(data):
    result = {}
    for item in data:
        if not item.get("violations") and not item.get("insights"):
            continue
        item.pop("unmatched", None)
        name = item.get("name")
        if name is not None:
            result[name] = item.get("violations", [])
    return result

def get_hub_url():
    value = os.getenv("HUB_URL")
    if not value:
        value = "http://localhost:8080/hub"
    return value

def get_hub_login_url(hub_url=None):
    """Return hub URL suitable for `kantra config login`."""
    url = (hub_url or get_hub_url()).rstrip("/")
    if url.endswith("/hub"):
        return url[:-4]
    return url

def _hub_auth_urls(hub_url):
    url = hub_url.rstrip("/")
    if url.endswith("/hub"):
        return [f"{url}/auth/tokens"]
    if url.startswith("https://"):
        return [f"{url}/hub/auth/tokens", f"{url}/auth/tokens"]
    return [f"{url}/auth/tokens", f"{url}/hub/auth/tokens"]

def obtain_hub_token(hub_url=None, username=None, password=None, secure=None):
    """Obtain a Hub API token using basic auth or HUB_TOKEN env var."""
    token = os.getenv("HUB_TOKEN")
    if token:
        return token

    hub_url = hub_url or get_hub_url()
    username = username if username is not None else get_hub_username()
    password = password if password is not None else get_hub_password()
    secure = get_hub_secure() if secure is None else secure

    basic = base64.b64encode(f"{username}:{password}".encode()).decode()
    context = ssl.create_default_context()
    if not secure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    last_error = None
    last_body = ""
    for auth_url in _hub_auth_urls(hub_url):
        request = urllib.request.Request(
            auth_url,
            data=b"{}",
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, context=context, timeout=15) as response:
                body = response.read().decode()
        except urllib.error.HTTPError as exc:
            last_error = exc
            last_body = exc.read().decode(errors="replace")
            continue
        except urllib.error.URLError as exc:
            last_error = exc
            continue

        try:
            parsed = json.loads(body)
            token = parsed.get("token")
            if token:
                return token
        except json.JSONDecodeError:
            pass

        for line in body.splitlines():
            if line.startswith("token:"):
                return line.split(":", 1)[1].strip()

        last_body = body

    if isinstance(last_error, urllib.error.HTTPError):
        raise RuntimeError(
            f"Failed to authenticate against Hub (HTTP {last_error.code}): {last_body}"
        ) from last_error
    if last_error is not None:
        raise RuntimeError(f"Failed to authenticate against Hub: {last_error}") from last_error
    raise RuntimeError(f"Failed to obtain hub token: {last_body}")

def get_hub_username():
    return os.getenv("HUB_USERNAME", "admin")

def get_hub_password():
    return os.getenv("HUB_PASSWORD", "admin")

def get_hub_secure():
    is_secure_raw = os.getenv("HUB_SECURE", "false")
    return str(is_secure_raw).lower() in ("true", "1", "yes")

def get_full_application_path(binary_name):
    if not binary_name:
        raise Exception("No binary name provided")
    return os.path.join(get_project_path(), 'data', 'applications', binary_name)

def get_cli_path():
    value = os.getenv(constants.KANTRA_CLI_PATH)
    if not value:
        raise RuntimeError("KANTRA_CLI_PATH is not set")
    return value

def get_project_path():
    value = os.getenv(constants.PROJECT_PATH)
    if not value:
        raise RuntimeError("PROJECT_PATH is not set")
    return value

def get_report_path():
    value = os.getenv(constants.REPORT_OUTPUT_PATH)
    if not value:
        raise RuntimeError("REPORT_OUTPUT_PATH is not set")
    return value


def clear_maven_cache():
    """
    Remove the local Maven directory (``~/.m2`` on Linux and macOS,
    ``%USERPROFILE%\\.m2`` on Windows). No-op if the directory does not exist.
    """
    m2_dir = os.path.join(os.path.expanduser("~"), ".m2")
    if os.path.isdir(m2_dir):
        shutil.rmtree(m2_dir)


def get_profile_path(config_data):
    command = [get_cli_path(),
               "config",
               "list",
               "--profile-dir",
               get_full_application_path(config_data["filename"]),
               ]
    result = run_command(command, shell=False, check=True)
    lines = result.stdout.strip().splitlines()
    return lines if lines else None

def run_command(command, shell=True, check=False):
    output = subprocess.run(command, shell=shell, check=False, # Всегда ловим сами
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    if check and output.returncode != 0:
        raise RuntimeError(f"Cmd failed: {command}\nError: {output.stderr}")
    return output