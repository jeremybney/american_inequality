"""Cross-post the calendar to other platforms (X now; Bluesky and Threads next).

Usage:
  python social.py --verify x         # check the X keys and upload a chart; publishes nothing
  python social.py --test-post x      # publish ONE test post with a chart (only when asked)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TEST_CHART = ROOT / "charts" / "2026-11-30" / "real_wages_1973.png"


def verify_x():
    from aiq_notes import xpost
    me = xpost.whoami()
    print(f"OK: keys work for @{me['username']} ({me['name']}, id {me['id']})")
    mid = xpost.upload_image(str(TEST_CHART), alt="Line chart of real hourly wages for rank-and-file workers since 1964.")
    print(f"OK: chart upload works (media id {mid}). Nothing was posted.")


def test_post_x():
    from aiq_notes import xpost
    res = xpost.post("Testing a new charts feed. This post will be deleted shortly.", str(TEST_CHART),
                     alt="Line chart of real hourly wages for rank-and-file workers since 1964.")
    print("posted:", res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", choices=["x"])
    ap.add_argument("--test-post", choices=["x"])
    a = ap.parse_args()
    try:
        if a.verify == "x":
            verify_x()
        elif a.test_post == "x":
            test_post_x()
        else:
            ap.print_help()
    except Exception as e:  # print a readable error for the Actions log
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
