import pytest

from redteam_memory.pyrit_quickstart import run_native_demo


def test_quickstart_validates_input_before_starting_pyrit():
    with pytest.raises(ValueError, match="prompt is required"):
        run_native_demo({"prompt": "", "converter": "raw"}, python_executable="missing")
    with pytest.raises(ValueError, match="converter must be raw or base64"):
        run_native_demo({"prompt": "sample", "converter": "unknown"}, python_executable="missing")
