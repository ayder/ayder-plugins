"""AC-C13: browser_open description carries the separate-browsers instruction
(spec §3.1, D26) — guidance only, factual, no stealth/detection claim."""
import browser_definitions as bd


def test_browser_open_description_instruction():
    defs = {td.name: td for td in bd.TOOL_DEFINITIONS}
    desc = defs["browser_open"].description.lower()
    assert "separate browsers" in desc
    assert "browser_close before switching" in desc
    assert "on automatically for local" in desc
    assert "off for remote" in desc
    assert "leave console unset for remote" in desc
    assert "fresh browser" in desc
    for bad in ("stealth", "hide automation", "avoid detection",
                "undetected", "bot detection", "evade"):
        assert bad not in desc, bad
