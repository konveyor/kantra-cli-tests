import json
import os
import shutil
import subprocess
import zipfile

import pytest

from utils.common import get_project_path, get_report_path, get_cli_path


# Polarion TC 376
# TODO Kantra transform runs in a container that does "cp -r /opt/input /tmp/source-app"
# and hits "Permission denied" Remove skip when Kantra fixes
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Kantra transform container has /tmp permission denied (cp to /tmp/source-app); skip in CI until fixed",
)
@pytest.mark.parametrize('transformation_name', json.load(open("data/openrewrite_transformation.json")))
def test_transform_code_with_openrewrite(transformation_name, openrewrite_transformation_data):
    application_data = openrewrite_transformation_data[transformation_name]
    kantra_path = get_cli_path()
    extraction_path = get_report_path()

    shutil.rmtree(extraction_path)

    application_path = os.path.join(
        get_project_path(),
        'data',
        'applications',
        application_data['file_name']
        )
    extracted_app_path = os.path.join(
        get_report_path(),
        application_data['app_name']
          )

    with zipfile.ZipFile(application_path, 'r') as zip_ref:
        zip_ref.extractall(extraction_path)

    command = f"{kantra_path} openrewrite --input {extracted_app_path} --target {application_data['targets']}"
    print(command)

    output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, encoding='utf-8').stdout
    assert 'BUILD SUCCESS' in output, "Failed command is: " + command

    with open(
            os.path.join(extracted_app_path, application_data['assertion_file']), 'r'
    ) as file:
        file_data = file.read()

    assert application_data['assertion'] in file_data


