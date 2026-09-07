import pytest

# The app is configured for one place, and its date arithmetic — which day a
# late-evening UTC event belongs to, when the recap window opens — is asserted
# against that zone by name in several tests. Left to the environment, those
# assertions would pass locally and fail on any machine that exports a
# different TIMELESS_TZ, so the suite pins it rather than inheriting it.
SUITE_TZ = "America/Chicago"


@pytest.fixture(autouse=True)
def suite_timezone(monkeypatch):
    monkeypatch.setenv("TIMELESS_TZ", SUITE_TZ)
