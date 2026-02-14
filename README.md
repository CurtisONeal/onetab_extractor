Pre-requisites & Assumptions
Snappy Requirement: On macOS, plyvel often requires snappy to be installed via Homebrew to handle compressed Chrome data.

Database Lock: As discussed, you must either close Chrome or copy the database folder to a temporary location before running this, as LevelDB only allows one process to hold a LOCK file at a time.

1. The Python Script (~/onetab_extractor.py)
Copy this code into a file named onetab_extractor.py in your home directory.
import plyvel Because we're dealing with binary LevelDB data
snappy plyvel often requires snappy
import json
import csv for the output
import os
import sys
import argparse for the flags
from datetime import datetime

You can find the OneTab files here:
~/Library/Application Support/Google/Chrome/Default/Extensions/chphlpgkkbolifaimnlloiipkdnihall

If you are looking to backup or recover your actual saved tabs, they are stored in a LevelDB database. Depending on your version of Chrome, they live in one of these two hidden folders:

Primary Location:
~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall/

Alternative Location:
~/Library/Application Support/Google/Chrome/Default/Local Storage/leveldb/

[!IMPORTANT]
OneTab data is primarily identified by the ID chphlpgkkbolifaimnlloiipkdnihall. Inside the Local Extension Settings folder, you will see .ldb and .log files; these are the actual files that contain your links.
