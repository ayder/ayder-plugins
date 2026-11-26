"""AC-W13: the launch flags open_work's config carries for the webmcp option."""
import zendriver_tools_browser as zb


def test_enable_flag_for_omitted_and_true():
    for w in (None, True):
        cfg = zb.make_open_config("/fake/chrome", "/tmp/dir", True, w)
        args = cfg()
        assert "--enable-features=WebMCP" in args
        assert not any(a.startswith("--disable-features=") and "WebMCP" in a
                       for a in args)


def test_disable_flag_false_merged_single_switch():
    cfg = zb.make_open_config("/fake/chrome", "/tmp/dir", True, False)
    args = cfg()
    assert "--enable-features=WebMCP" not in args
    dis = [a for a in args if a.startswith("--disable-features=")]
    assert len(dis) == 1
    assert "WebMCP" in dis[0]
    assert "IsolateOrigins" in dis[0] and "site-per-process" in dis[0]


def test_flags_same_for_persistent_directory():
    cfg = zb.make_open_config("/fake/chrome", "/tmp/persistent", True, True)
    assert "--enable-features=WebMCP" in cfg()
    cfgFalse = zb.make_open_config("/fake/chrome", "/tmp/persistent", True, False)
    assert any("WebMCP" in a for a in cfgFalse()
               if a.startswith("--disable-features="))
