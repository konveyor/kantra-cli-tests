import os
import subprocess
import pytest

from utils import constants
from utils.command import build_analysis_command
from utils.common import run_containerless_parametrize
from utils.manage_maven_credentials import manage_credentials_in_maven_xml
from utils.report import assert_insights_from_report_file, get_json_from_report_output_js_file

# Polarion TC 598
@run_containerless_parametrize
def test_insights_binary_app(analysis_data, additional_args):
    application_data = analysis_data['jee_example_app']

    command = build_analysis_command(
        application_data['file_name'],
        application_data['sources'],
        application_data['targets'],
        **additional_args
    )

    output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE,
        encoding='utf-8').stdout

    assert 'generating static report' in output
    assert_insights_from_report_file()

# Polarion TC 576, 577, 578, 589, 606
@run_containerless_parametrize
@pytest.mark.parametrize('analysis_mode', ["source-only", "full"])
def test_insights_custom_rules(analysis_data, analysis_mode, additional_args):
    application_data = analysis_data['tackle-testapp-project']
    custom_rule_path = os.path.join(
        os.getenv(constants.PROJECT_PATH),
        'data',
        'yaml',
        'custom_rule_insights.yaml'
    )

    custom_maven_settings = os.path.join(
        os.getenv(constants.PROJECT_PATH),
        'data',
        'xml',
        'tackle-testapp-public-settings.xml'
    )

    manage_credentials_in_maven_xml(custom_maven_settings)

    if analysis_mode == 'source-only':
        command = build_analysis_command(
            application_data['file_name'],
            application_data['sources'],
            application_data['targets'],
            **{'rules': custom_rule_path},
            **{'mode': 'source-only'},
            **{'maven-settings': custom_maven_settings},
            **additional_args
        )
    else:
        command = build_analysis_command(
            application_data['file_name'],
            application_data['sources'],
            application_data['targets'],
            **{'rules': custom_rule_path},
            **{'maven-settings': custom_maven_settings},
            **additional_args
        )
    output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE,
        encoding='utf-8').stdout
    assert 'generating static report' in output

    report_data = get_json_from_report_output_js_file()
    for rule in report_data['rulesets']:
        insights = rule.get('insights', {})

        for insight in insights.values():
            if rule['name'] == 'custom-ruleset':
                if insight['description'] in ('Properties file (Insights TC0)',
                    'Properties file (Insights TC1)', 'Properties file (Insights TC2)'):
                    # Assert insight occurrence is > 0 for each insight
                    assert len(insight['incidents']) > 0, "No insights were generated"
                else:
                    assert 'Properties file (Insights TC3)' in insight['description'], \
                        "Insight incorrectly generated"

    manage_credentials_in_maven_xml(custom_maven_settings, True)
