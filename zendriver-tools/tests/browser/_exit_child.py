"""Child for the exit test: import the plugin (registers the exit handler),
open a throwaway browser, print the record, wait for the parent's ack,
exit normally."""
import json
import sys

import browser_tools as bt
import zendriver_tools_state as state

r = bt.browser_open(url=sys.argv[1])
if not r.is_success:
    print(json.dumps({"error": str(r)}), flush=True)
    sys.exit(1)
print(json.dumps({"pid": state.handle.pid,
                  "profile": str(state.profile_dir)}), flush=True)
input()  # parent verifies the record before allowing exit
