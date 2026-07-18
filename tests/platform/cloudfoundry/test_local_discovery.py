import glob
import os
import shlex
import subprocess
import pytest
import shutil
from pathlib import Path

from utils import constants
from utils.command import build_platform_local_discovery_command, build_asset_generation_command

def test_cf_asset_generation_from_local_discovery():
    """
    Test end-to-end workflow: offline discovery of CF application and asset generation.
    1. Uses existing CF manifest file (hello-spring-cloud-manifest.yml)
    2. Generates discovery manifest from the CF manifest file
    3. Generates Helm charts from discovered manifest
    """
    project_path = os.getenv(constants.PROJECT_PATH)
    cf_files_path = os.getenv(constants.CLOUDFOUNDRY_FILES_PATH)

    if not project_path:
        raise Exception("PROJECT_PATH environment variable is not set")
    if not cf_files_path:
        raise Exception("CLOUDFOUNDRY_FILES_PATH environment variable is not set")

    # Path to the local manifest file
    manifest_file = os.path.join(os.getenv(constants.PROJECT_PATH), 'data', 'yaml', 'platform', 'cloudfoundry', 'hello-spring-cloud-manifest.yml')
    if not os.path.exists(manifest_file):
        raise Exception(f"Manifest file not found: {manifest_file}")

    helm_chart_dir = os.path.join(os.getenv(constants.PROJECT_PATH), 'helm-charts')
    discovery_output_dir = os.path.join(cf_files_path, 'offline_discovery')
    asset_dir = os.path.join(cf_files_path, 'offline_assets')

    if os.path.exists(discovery_output_dir):
        shutil.rmtree(discovery_output_dir)
    if os.path.exists(asset_dir):
        shutil.rmtree(asset_dir)

    discovery_command = build_platform_local_discovery_command(
        manifest_file=manifest_file,
        output_dir=discovery_output_dir
    )

    # Perform offline discovery of Cloud Foundry (CF) application manifest
    # Input: CF application manifest, Output: Discovery manifest
    print(f"Running offline discovery command: '{discovery_command}'")
    discovery_output = subprocess.run(
        shlex.split(discovery_command),
        check=True,
        stdout=subprocess.PIPE,
        text=True
    ).stdout
    assert 'Writing content to file' in discovery_output, "Discovery command failed"

    dir_path = Path(discovery_output_dir)
    assert dir_path.exists() and dir_path.is_dir(), f"Output directory '{dir_path}' was not created"

    yaml_files = glob.glob(f'{discovery_output_dir}/*.yaml')
    assert yaml_files, f"Discovery manifest was not generated in {discovery_output_dir}"
    print(f"Found {len(yaml_files)} discovery manifest(s)")

    # Generate assets after discovering CF application
    # Use the first generated YAML file as input
    input_manifest = yaml_files[0]
    chart_dir = os.path.join(helm_chart_dir, 'hello-spring-cloud')
    print(f"Generating assets from {input_manifest}")
    asset_command = build_asset_generation_command(
        input_file=input_manifest,
        chart_dir=chart_dir,
        output_dir=asset_dir
    )

    print(f"Running asset generation command: '{asset_command}'")
    subprocess.run(shlex.split(asset_command), check=True, stdout=subprocess.PIPE, text=True)
    asset_files = glob.glob(f'{asset_dir}/*.yaml')
    assert asset_files, f"Assets were not generated in {asset_dir}"
    print(f"Successfully generated {len(asset_files)} asset file(s)")

    if os.path.exists(discovery_output_dir):
        shutil.rmtree(discovery_output_dir)
    if os.path.exists(asset_dir):
        shutil.rmtree(asset_dir)
