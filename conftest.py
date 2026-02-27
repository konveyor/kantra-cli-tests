import time
import pytest
from dotenv import load_dotenv

pytest_plugins = [
    "fixtures.analysis",
    "fixtures.transformation",
]


@pytest.fixture(scope="session", autouse=True)
def load_env():
    load_dotenv()

def pytest_runtest_setup(item):
    item.start_time = time.perf_counter()

def pytest_runtest_teardown(item):
    duration = time.perf_counter() - item.start_time
    print(f"\nTest {item.name} took {duration:.4f} seconds")


def pytest_terminal_summary(terminalreporter):
    """Print a test run summary at the end of the run."""
    if not hasattr(terminalreporter, "stats") or not terminalreporter.stats:
        return
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    errors = len(terminalreporter.stats.get("error", []))
    total = passed + failed + skipped + errors
    if total == 0:
        return
    terminalreporter.write_sep("=", "Test summary")
    terminalreporter.write_line(f"  Total:   {total}")
    if passed > 0:
        terminalreporter.write_line(f"  Passed:  {passed}")
    if skipped > 0:
        terminalreporter.write_line(f"  Skipped: {skipped}")
    if failed > 0:
        terminalreporter.write_line(f"  Failed:  {failed}")
        for rep in terminalreporter.stats.get("failed", []):
            terminalreporter.write_line(f"    - {rep.nodeid}")
    terminalreporter.write_sep("=", "")