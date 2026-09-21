"""Each part of Jobcu can be loaded on its own. A loop between modules may stay hidden while
they happen to be loaded in a lucky order, so each is loaded in a fresh Python here."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["jobcu.dedupe", "jobcu.jobstore", "jobcu.sources",
                                    "jobcu.travel", "jobcu.filters", "jobcu.app"])
def test_module_loads_on_its_own(module):
    result = subprocess.run([sys.executable, "-c", f"import {module}"], capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stderr
