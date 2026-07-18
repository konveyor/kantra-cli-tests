import os
import subprocess
import sys

from utils.common import (
    get_cli_path,
    get_hub_login_url,
    get_hub_url,
    get_project_path,
    get_report_path,
    obtain_hub_token,
)

# Use PTY on Unix so the child's stdout is line-buffered and we capture the final analysis message
_USE_PTY = sys.platform != 'win32'


def _safe_stdout_write(line):
    """Write line to stdout; on Windows cp1252 replace unencodable chars to avoid UnicodeEncodeError."""
    try:
        sys.stdout.write(line)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, 'encoding', None) or 'utf-8'
        sys.stdout.buffer.write(line.encode(enc, errors='replace'))

def build_analysis_command(binary_name, sources, targets, is_bulk=False, output_path=None, settings=None, with_deps = True, **kwargs):
    """
        Builds a string for executing the "analyze" subcommand

        Args:
            binary_name (str): binary file of the application to be analyzed.
            sources (str): Array of sources of the application.
            targets (str): Array of targets for the application to migrate to.
            is_bulk (bool): Defines if '--bulk' (true) or `--overwrite`(false) run is performed
            with_deps (bool): Defines if source-only or source + dependencies analysis is performed
            settings: If defined - custom maven file will be used for analysis
            output_path: If defined - overrides default report output path
            **kwargs (str): Optional keyword arguments to be passed to Kantra as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If `binary_path` is not provided.
    """
    kantra_path = get_cli_path()

    if output_path:
        report_path = output_path
    else:
        report_path = get_report_path()

    if not binary_name:
        raise Exception('Binary path is required')

    if is_bulk:
        run_type = '--bulk'
    else:
        run_type = '--overwrite'

    if os.path.isabs(binary_name):
        binary_path = binary_name
    else:
        binary_path = os.path.join(get_project_path(), 'data', 'applications', binary_name)

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

    run_local_env = os.getenv('RUN_LOCAL_MODE')
    if run_local_env in ('true', 'false') and not any('run-local' in str(k) for k in kwargs):
        command += ' --run-local=' + run_local_env

    for key, value in kwargs.items():
        if '--' not in key:
            key = '--' + key
        command += ' ' + key

        if value:
            command += '=' + value

    print(command)
    return command


def run_command_stream_output(command, shell=True, check=True):
    """
    Stream stdout/stderr to the current process and return the combined output for assertions.
    Raises subprocess.CalledProcessError if check=True and the process exits non-zero.
    """
    if _USE_PTY:
        return _run_command_stream_output_pty(command, shell=shell, check=check)
    return _run_command_stream_output_pipe(command, shell=shell, check=check)


def _run_command_stream_output_pipe(command, shell=True, check=True):
    """Capture via pipe (used on Windows)."""
    proc = subprocess.Popen(
        command,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    lines = []
    for line in proc.stdout:
        _safe_stdout_write(line)
        sys.stdout.flush()
        lines.append(line)
    proc.wait()
    output = ''.join(lines)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, output)
    return output


def _run_command_stream_output_pty(command, shell=True, check=True):
    """Capture via PTY on Unix so child stdout is line-buffered for final output."""
    import pty
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            command,
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
        )
    except Exception:
        os.close(slave)
        os.close(master)
        raise
    os.close(slave)
    chunks = []
    try:
        while True:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            decoded = data.decode('utf-8', errors='replace')
            _safe_stdout_write(decoded)
            sys.stdout.flush()
            chunks.append(decoded)
    finally:
        os.close(master)
    proc.wait()
    output = ''.join(chunks)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, output)
    return output


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
    kantra_path = get_cli_path()

    if not binary_name:
        raise Exception('Binary path is required')


    if os.path.isabs(binary_name):
        binary_path = binary_name
    else:
        binary_path = os.path.join(get_project_path(), 'data', 'applications', binary_name)

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

def build_platform_local_discovery_command(manifest_file, output_dir=None, **kwargs):
    """
        Builds a string for executing the "discover cloud-foundry" subcommand for offline discovery

        Args:
            manifest_file (str): Path to the Cloud Foundry manifest file.
            output_dir (str, optional): Directory path for discovery output.
            **kwargs (str): Optional keyword arguments to be passed to Kantra as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If required parameters are not provided.
    """
    kantra_path = get_cli_path()

    if not manifest_file:
        raise Exception('Manifest file is required')

    if not os.path.exists(manifest_file):
        raise Exception(f"Manifest file does not exist: {manifest_file}")

    command = kantra_path + ' discover cloud-foundry --input=' + manifest_file

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


def build_central_config_login_command(hub_url, secure=False):
    """
    Builds a command for executing the "config login" subcommand.
    The CLI reads a Hub API token from stdin; use run_central_config_login().
    """
    kantra_path = get_cli_path()
    if not secure:
        print("Not secure connection")
    return [kantra_path, "config", "login", get_hub_login_url(hub_url)] + (
        ["--insecure"] if not secure else []
    )


def run_central_config_login(hub_url, username, password, secure=False):
    """Obtain a Hub token and run `kantra config login` non-interactively."""
    token = obtain_hub_token(hub_url, username, password, secure=secure)
    command = build_central_config_login_command(hub_url, secure=secure)
    print(command)
    env = os.environ.copy()
    env["HUB_TOKEN"] = token
    output = subprocess.run(
        command,
        shell=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if output.returncode != 0:
        raise RuntimeError(
            f"Login failed (exit {output.returncode}): {command}\n{output.stdout}"
        )
    return output


def build_central_config_sync_command(app_url, profile_path=None, secure=True):
    """
    Builds a string for executing the "central config sync" subcommand
    Args:
        app_url: URL of the application to be synced.
        secure: Set as false to ignore SSL certificate verification
        profile_path (str): path to profile folder, if not specified - current location is used
    Returns: Command to execute with the specified options and arguments.

    """
    kantra_path = get_cli_path()
    command = [kantra_path, 'config', 'sync', '--url', app_url]
    hub_url = get_hub_url()
    if hub_url == "http://localhost:8080/hub":
        command += ['--host', hub_url]
    if profile_path:
        command += ['--application-path=' + profile_path]
    if not secure:
        command += ['--insecure']
    print(command)
    return command


def build_analysis_command_ccm(binary_name, profile_path=None, output_path=None, **kwargs):
    """
        Builds a string for executing the "analyze" subcommand

        Args:
            binary_name (str): binary file of the application to be analyzed.
            profile_path (str): path to profile folder, if not specified - current location is used
            output_path: If defined - overrides default report output path
            **kwargs (str): Optional keyword arguments to be passed to Kantra as additional options.
                this argument takes a dict, where each key is the argument, which can be passed with or without the '--'

        Returns:
            str: The full command to execute with the specified options and arguments.

        Raises:
            Exception: If `binary_path` is not provided.
    """
    kantra_path = get_cli_path()

    if output_path:
        report_path = output_path
    else:
        report_path = get_report_path()

    if not binary_name:
        raise Exception('Binary path is required')

    run_type = '--overwrite'

    if os.path.isabs(binary_name):
        binary_path = binary_name
    else:
        binary_path = os.path.join(get_project_path(), 'data', 'applications', binary_name)

    if not os.path.exists(binary_path):
        raise Exception("Input application `%s` does not exist" % binary_path)

    command = kantra_path + ' analyze ' + run_type + ' --log-level=500 --input ' + binary_path + ' --output ' + report_path

    if profile_path:
        command += f' --profile-dir {profile_path} '

    for key, value in kwargs.items():
        if '--' not in key:
            key = '--' + key
        command += ' ' + key

        if value:
            command += '=' + value

    print(command)
    return command
