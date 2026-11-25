import json
import os
import pathlib
import shutil
import subprocess

import pytest

import utils.common
from utils import constants
from utils.command import build_analysis_command, run_command_stream_output
from utils.common import get_project_path, run_containerless_parametrize, verify_triggered_rules
from utils.manage_maven_credentials import get_default_token
from utils.report import assert_story_points_from_report_file, get_dict_from_output_yaml_file

@run_containerless_parametrize
@pytest.mark.parametrize('app_name', json.load(open("data/analysis.json")))
def test_standard_analysis(app_name, analysis_data, additional_args):
    application_data = analysis_data[app_name]

    extra_kwargs = dict(additional_args)
    # Add settings.xml with credentials needed e.g. by tackle-testapp-public
    if application_data.get('maven_settings'):
        with open(application_data['maven_settings'], 'r') as f:
            raw_settings = f.read()
        maven_token = os.getenv(constants.GIT_PASSWORD, '')
        if maven_token == '':
            maven_token = get_default_token()
        raw_settings = raw_settings.replace('GITHUB_USER', os.getenv(constants.GIT_USERNAME, 'konveyor-read-only-bot'))
        raw_settings = raw_settings.replace('GITHUB_TOKEN', maven_token)
        input_path = os.path.join(utils.common.get_project_path(), 'data', 'applications', application_data['file_name'])
        settings_path = input_path + "_settings.xml"  
        with open(settings_path, 'w') as f:
            f.write(raw_settings)
        extra_kwargs['maven-settings'] = settings_path

    command = build_analysis_command(
        application_data['file_name'],
        application_data['sources'],
        application_data['targets'],
        **extra_kwargs
    )

    output = run_command_stream_output(command)

    assert 'analysis complete' in output.lower(), "Expected 'Analysis complete!' in Kantra output"

    assert_story_points_from_report_file()

# Polarion TC 588
def test_java_analysis_without_pom(analysis_data):
    application_data = analysis_data['tackle-testapp-public']
    app_path = os.path.join(get_project_path(), 'data', 'applications', application_data['file_name'])
    app_no_pom_path = f"{app_path}-no-pom"
    shutil.rmtree(app_no_pom_path, ignore_errors=True)
    shutil.copytree(app_path, app_no_pom_path)
    pathlib.Path.unlink(pathlib.Path(os.path.join(app_no_pom_path, "pom.xml")))

    command = build_analysis_command(
        app_no_pom_path,
        application_data['sources'],
        "",
    )
    try:
        run_command_stream_output(command)
        shutil.rmtree(app_no_pom_path)
        pytest.fail("Expected analysis to fail with 'unable to get build tool' when pom.xml is missing")
    except subprocess.CalledProcessError as e:
        output = (e.args[2] if len(e.args) > 2 else "") or getattr(e, "output", "") or str(e)
        assert "failed to start providers" in output and "unable to get build tool" in output, (
            f"Expected 'failed to start providers' and 'unable to get build tool' in output, got: {output[-2000:]!r}"
        )
    finally:
        shutil.rmtree(app_no_pom_path, ignore_errors=True)

# Automates Bug 6211
def test_gradle_analysis_custom_rule():
    if os.getenv('RUN_LOCAL_MODE') == 'true':
        pytest.skip("skip when running containerless")

    custom_rules_path = os.path.join(
        get_project_path(), 
        'data', 
        'yaml',
        'serializable-gradle-rule.yaml'
        )

    # Use app name like other analysis tests: resolves to data/applications/gradle8-example-main
    command = build_analysis_command(
        'gradle8-example-main',
        "",
        "",
        **{
            'rules': custom_rules_path,
            'enable-default-rulesets': 'false',
            'analyze-known-libraries': None,
            'run-local': 'true'
        },
    )

    output = run_command_stream_output(command)

    assert 'analysis complete' in output.lower(), "Expected 'Analysis complete!' in Kantra output"
    assert_story_points_from_report_file()
    report_data = get_dict_from_output_yaml_file()
    verify_triggered_rules(report_data, ['serializable-test-rule-jmh-gradle'])


def test_dependency_rule_analysis(analysis_data):
    application_data = analysis_data['tackle-testapp-project']
    settings_template = os.path.join(get_project_path(), 'data', 'xml', 'tackle-testapp-public-settings.xml')
    custom_rule_path = os.path.join(get_project_path(), 'data', 'yaml', 'tackle-dependency-custom-rule.yaml')

    with open(settings_template, 'r') as f:
        raw_settings = f.read()
    maven_token = os.getenv(constants.GIT_PASSWORD, '')
    if maven_token == '':
        maven_token = get_default_token()
    raw_settings = raw_settings.replace('GITHUB_USER', os.getenv(constants.GIT_USERNAME, 'konveyor-read-only-bot'))
    raw_settings = raw_settings.replace('GITHUB_TOKEN', maven_token)
    tmp_dir = os.path.join(get_project_path(), 'data', 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    settings_path = os.path.join(tmp_dir, 'tackle-testapp-project_dependency_rule_settings.xml')
    with open(settings_path, 'w') as f:
        f.write(raw_settings)

    command = build_analysis_command(
        application_data['file_name'],
        application_data['sources'],
        "",
        **{
            'maven-settings': settings_path,
            'rules': custom_rule_path,
        }
    )

    output = run_command_stream_output(command)

    assert 'analysis complete' in output.lower(), "Expected 'Analysis complete!' in Kantra output"

    report_data = get_dict_from_output_yaml_file()
    verify_triggered_rules(report_data, ['tackle-dependency-test-rule'])
