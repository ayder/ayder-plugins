"""AC-C11: pure host classifier for the console-capture default (spec §5)."""
import pytest

from zendriver_tools_console import default_capture_for


@pytest.mark.parametrize("url", [
    "http://localhost/",
    "http://localhost:8080/x",
    "https://LOCALHOST/",
    "http://user@localhost/",
    "http://a.localhost/",
    "http://sub.a.localhost/",
    "http://127.0.0.1/",
    "http://127.1.2.3:5000/",
    "http://[::1]/",
    "http://[::1]:8080/",
    "http://localhost./",
    "http://[::ffff:127.0.0.1]/",
])
def test_local_hosts_capture_on(url):
    assert default_capture_for(url) is True


@pytest.mark.parametrize("url", [
    "http://128.0.0.1/",
    "http://localhost.example.com/",
    "http://example.com/",
    "https://www.bim.com.tr/",
    "http://0.0.0.0/",
    "about:blank",
    "http://2130706433/",
    "http://[::ffff:128.0.0.1]/",
    "http://[::2]/",
])
def test_remote_hosts_capture_off(url):
    assert default_capture_for(url) is False
