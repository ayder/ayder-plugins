"""Pure host classifier for the console-capture default (spec §5, D25).

No driver and no network: a pure function of the requested URL. Loopback
destinations (localhost, *.localhost, 127.0.0.0/8, ::1) capture by default;
everything else, about:blank included, does not. Imported at module level by
its users (D22); zendriver is not needed here.
"""
import ipaddress
from urllib.parse import urlsplit


def default_capture_for(url):
    """Return True when the URL's host is loopback (capture on by default)."""
    host = urlsplit(url).hostname  # lower-cased; IPv6 brackets removed
    if not host:
        return False
    if host.endswith("."):  # a single trailing DNS root dot changes nothing
        host = host[:-1]
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # Not a valid dotted-quad/IPv6 literal (e.g. a numeric host like
        # 2130706433): the classifier does not resolve names or guess Chrome's
        # numeric-IP coercion. Conservative off.
        return False
    # is_loopback covers 127.0.0.0/8, ::1 and IPv4-mapped loopback
    # (::ffff:127.0.0.1) on the Pythons in use.
    return bool(addr.is_loopback)
