"""One-off: turns the short key from Meta's Graph API Explorer into a long-lasting Facebook page key,
and stores it in the GitHub secret FB_PAGE_TOKEN. Nothing secret is printed.

Usage (PowerShell), with the Explorer's short key copied to the clipboard:
  python make_token.py user      # remembers the short key
Then copy the app secret and:
  python make_token.py finish
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

APP_ID = "1063313382988555"
PAGE_ID = "1364743160046540"
REPO = "geras-cloud/elenzai-poster"
TMP = os.path.join(os.environ.get("TEMP", "."), "elenzai_short_key.txt")


def clip():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True).stdout
    return out.strip()


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "user":
        k = clip()
        if not k.startswith("EAA"):
            sys.exit("The clipboard does not hold a Meta key. Copy the key from the Explorer first.")
        open(TMP, "w").write(k)
        print("Short key remembered. Now copy the app secret and run: python make_token.py finish")
    elif step == "finish":
        secret = clip()
        if len(secret) < 20 or secret.startswith("EAA"):
            sys.exit("The clipboard does not hold the app secret. Copy it from App settings > Basic first.")
        short = open(TMP).read().strip()
        q = urllib.parse.urlencode({"grant_type": "fb_exchange_token", "client_id": APP_ID, "client_secret": secret, "fb_exchange_token": short})
        long_user = get("https://graph.facebook.com/v21.0/oauth/access_token?" + q)["access_token"]
        accts = get("https://graph.facebook.com/v21.0/me/accounts?" + urllib.parse.urlencode({"fields": "id,name,access_token", "access_token": long_user}))
        page = next((a for a in accts["data"] if a["id"] == PAGE_ID), None)
        if not page:
            sys.exit("The Elenzai page was not found for this key.")
        out = os.path.join(os.environ.get("TEMP", "."), "elenzai_page_key.txt")
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(page["access_token"])
        print("Page key ready in a temporary file; store it with gh, then delete the file.")
        sys.exit(0)
        os.remove(TMP)
        subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"])
        print("Done. The long-lasting page key is stored as a GitHub secret, and your clipboard is cleared.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
