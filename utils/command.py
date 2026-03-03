import os

from utils import constants

def get_cli_path():
    value = os.getenv(constants.KANTRA_CLI_PATH)
    if not value:
        raise RuntimeError("KANTRA_CLI_PATH is not set")
    return value

def build_analysis_command(binary_name, sources, targets, is_bulk=False, output_path=None, settings=None, with_deps = True, **kwargs):
    """
        Builds a string for executing the "analyze" subcommand

        Args:
            binary_name (str): binary file of the application to be analyzed.
            source (str): Source of the application.
            target (str): Target for the application to migrate to.
            is_bulk (bool): Defines if '--bulk' (true) or `--overwrite`(false) run is performed
            **kwargs (str): Optional keyword arguments to be passed to Kantra as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If `binary_path` is not provided.
    """
    kantra_path = os.getenv(constants.KANTRA_CLI_PATH)

    if output_path:
        report_path = output_path
    else:
        report_path = os.getenv(constants.REPORT_OUTPUT_PATH)

    if not binary_name:
        raise Exception('Binary path is required')

    if is_bulk:
        run_type = '--bulk'
    else:
        run_type = '--overwrite'

    if os.path.isabs(binary_name):
        binary_path = binary_name
    else:
        binary_path = os.path.join(os.getenv(constants.PROJECT_PATH), 'data', 'applications', binary_name)

    if not os.path.exists(binary_path):
        raise Exception("Input application `%s` does not exist" % binary_path)

    command = kantra_path + ' analyze ' + run_type + ' --log-level=500 --input ' + binary_path + ' --output ' + report_path

    if sources:
        for source in sources:
            command += ' --source ' + source.lower()

    if targets:
        for target in targets:
            command += ' --target ' + target.lower()

    if settings:
        command += ' --maven-settings ' + settings

    if not with_deps:
        command += ' -m source-only'

    for key, value in kwargs.items():
        if '--' not in key:
            key = '--' + key
        command += ' ' + key

        if value:
            command += '=' + value

    print(command)
    return command

def build_discovery_command(binary_name,  **kwargs):
    """
        Builds a string for executing the "--list-language" subcommand

        Args:
            binary_name (str): binary file of the application to be analyzed.
            **kwargs (str): Optional keyword arguments to be passed to Kantra as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If `binary_path` is not provided.
    """
    kantra_path = os.getenv(constants.KANTRA_CLI_PATH)

    if not binary_name:
        raise Exception('Binary path is required')


    if os.path.isabs(binary_name):
        binary_path = binary_name
    else:
        binary_path = os.path.join(os.getenv(constants.PROJECT_PATH), 'data', 'applications', binary_name)

    if not os.path.exists(binary_path):
        raise Exception("Input application `%s` does not exist" % binary_path)

    command = kantra_path + ' analyze ' + '--list-languages --input ' + binary_path

    for key, value in kwargs.items():
        if '--' not in key:
            key = '--' + key
        command += ' ' + key

        if value:
            command += '=' + value

    print(command)
    return command

def build_platform_discovery_command(organizations, config, spaces=None, app_name=None, output_dir=None, **kwargs):
    """
        Builds a string for executing the "discover cloud-foundry" subcommand

        Args:
            organizations (list): List of organizations to discover (at least 1 required).
            config (str): Directory path where the Cloud Foundry config file resides
                         (the command looks for .cf/config.json within this directory).
            spaces (list, optional): List of spaces to discover.
            app_name (str, optional): Application name to discover.
            output_dir (str, optional): Directory path for discovery output.
            **kwargs (str): Optional keyword arguments to be passed to Kantra as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If required parameters are not provided.
    """
    kantra_path = get_cli_path()
    if not organizations or len(organizations) == 0:
        raise Exception('At least one organization is required')

    if not config:
        raise Exception('Config directory path is required')

    command = kantra_path + ' discover cloud-foundry --use-live-connection'

    # Add organizations (required)
    for org in organizations:
        command += ' --orgs=' + org

    command += ' --cf-config=' + config

    # Add spaces (optional)
    if spaces:
        for space in spaces:
            command += ' --spaces=' + space

    # Add app-name (optional)
    if app_name:
        command += ' --app-name=' + app_name

    # Add output directory
    if output_dir:
        command += ' --output-dir=' + output_dir

    # Add any additional kwargs
    for key, value in kwargs.items():
        if '--' not in key:
            key = '--' + key
        command += ' ' + key

        if value:
            command += '=' + value

    print(command)
    return command

def build_asset_generation_command(input_file, chart_dir, output_dir=None, **kwargs):
    """
        Builds a string for executing the "mta-cli generate helm" subcommand

        Args:
            input_file (str): Path to the input manifest file.
            chart_dir (str): Path to the Helm chart directory.
            output_dir (str, optional): Directory path for generated assets.
            **kwargs (str): Optional keyword arguments to be passed to mta-cli as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If required parameters are not provided.
    """
    kantra_path = get_cli_path()

    if not input_file:
        raise Exception('Input file is required')

    if not os.path.exists(input_file):
        raise Exception("Input file `%s` does not exist" % input_file)

    if not chart_dir:
        raise Exception('Chart directory is required')

    if not os.path.exists(chart_dir):
        raise Exception(f"Chart directory does not exist: {chart_dir}")

    command = kantra_path + ' generate helm --input=' + input_file

    command += ' --chart-dir=' + chart_dir

    if output_dir:
        command += ' --output-dir=' + output_dir

    # Add any additional kwargs
    for key, value in kwargs.items():
        if '--' not in key:
            key = '--' + key
        command += ' ' + key

        if value:
            command += '=' + value
    print(command)
    return command
