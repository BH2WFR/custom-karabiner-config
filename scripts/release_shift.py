import argparse
import html
import re
import subprocess
import sys
import time


def release_shift():
    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            'tell application "System Events" to key up shift',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


if __name__ == "__main__":
    release_shift()
