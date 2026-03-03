import json
import os
import pathlib
import shutil
import subprocess

import pytest

from utils import constants
from utils.command import build_analysis_command
from utils.common import run_containerless_parametrize, verify_triggered_rules, extract_zip_to_temp_dir
from utils.manage_maven_credentials import manage_credentials_in_maven_xml
from utils.report import assert_story_points_from_report_file, get_json_from_report_output_js_file

@run_containerless_parametrize
@pytest.mark.parametrize('app_name', json.load(open("data/analysis.json")))
def test_standard_analysis(app_name, analysis_data, additional_args):
    application_data = analysis_data[app_name]

    command = build_analysis_command(
        application_data['file_name'],
        application_data['sources'],
        application_data['targets'],
        **additional_args
    )

    output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, encoding='utf-8').stdout

    assert 'generating static report' in output

    assert_story_points_from_report_file()

# Polarion TC 588
def test_java_analysis_without_pom(analysis_data):
    application_data = analysis_data['tackle-testapp-public']
    app_path = os.path.join(os.getenv(constants.PROJECT_PATH), 'data/applications', application_data['file_name'])
    app_no_pom_path = f"{app_path}-no-pom"
    shutil.rmtree(app_no_pom_path, ignore_errors=True)
    shutil.copytree(app_path, app_no_pom_path)
    pathlib.Path.unlink(pathlib.Path(os.path.join(app_no_pom_path, "pom.xml")))

    command = build_analysis_command(
        app_no_pom_path,
        application_data['sources'],
        "",
    )

    output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, encoding='utf-8').stdout

    assert 'generating static report' in output

    assert_story_points_from_report_file()
    shutil.rmtree(app_no_pom_path)

# Automates Bug 6211
def test_gradle_analysis_custom_rule():

    application_path = os.path.join(
        os.getenv(constants.PROJECT_PATH),
        'data/applications',
        'jmh-gradle-example.zip'
    )
    custom_rules_path = os.path.join(os.getenv(constants.PROJECT_PATH), 'data/yaml/serializable-gradle-rule.yaml')

    with extract_zip_to_temp_dir(application_path) as tempdir:
        command = build_analysis_command(
            tempdir,
            "",
            "",
            **{
                'rules': custom_rules_path,
                'enable-default-rulesets': 'false',
                'analyze-known-libraries': None,
                'run-local': 'false'
            },
        )

        output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, encoding='utf-8').stdout

        assert 'Static report created' in output
        assert_story_points_from_report_file()
        report_data = get_json_from_report_output_js_file()
        verify_triggered_rules(report_data, ['serializable-test-rule-jmh-gradle'])

def test_dependency_rule_analysis(analysis_data):
    application_data = analysis_data['tackle-testapp-project']
    custom_maven_settings = os.path.join(
        os.getenv(constants.PROJECT_PATH),
        'data/xml',
        'tackle-testapp-public-settings.xml'
    )
    custom_rule_path = os.path.join(
        os.getenv(constants.PROJECT_PATH),
        'data/yaml',
        'tackle-dependency-custom-rule.yaml'
    )
    manage_credentials_in_maven_xml(custom_maven_settings)

    command = build_analysis_command(
        application_data['file_name'],
        application_data['sources'],
        "",
        **{
            'maven-settings': custom_maven_settings,
            'rules': custom_rule_path,
        }
    )

    output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, encoding='utf-8').stdout

    manage_credentials_in_maven_xml(custom_maven_settings, True)

    assert 'generating static report' in output

    report_data = get_json_from_report_output_js_file()

    verify_triggered_rules(report_data, ['tackle-dependency-test-rule'])
