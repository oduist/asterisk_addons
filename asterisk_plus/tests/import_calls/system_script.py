#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests
import json
import os
from datetime import datetime
import logging

# Configure logging
LOG_FILE = "/var/log/create_call.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Base URLs
CREATE_CALL_URL = "https://xxxxxx.oduist.com/asterisk_plus/create_call"
UPLOAD_RECORDING_URL = "https://xxxxxxx.oduist.com/asterisk_plus/upload_recording"

def parse_args(args):
    """Parse key=value arguments into a dictionary."""
    d = {}
    for arg in args:
        if '=' in arg:
            key, val = arg.split('=', 1)
            d[key.strip()] = val.strip()
    return d

def send_call_metadata(variables):
    """Send call metadata to Odoo."""
    uniqueid = variables.get("UNIQUEID", "")
    callerid = variables.get("CALLERID", "")
    dnid = variables.get("DNID", "")
    starttime = variables.get("STARTTIME", "")
    answeredtime = variables.get("ANSWEREDTIME", "")

    status = "answered" if answeredtime and answeredtime != "0" else "noanswer"
    ended = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "uniqueid": uniqueid,
        "calling_number": callerid,
        "called_number": dnid,
        "status": status,
        "started": starttime if starttime else None,
        "answered": answeredtime if answeredtime and answeredtime != "0" else None,
        "ended": ended,
        "direction": "out"
    }

    headers = {"Content-Type": "application/json"}

    try:
        r = requests.post(CREATE_CALL_URL, headers=headers, data=json.dumps(payload), timeout=5)
        logging.info(f"Call metadata sent: status={r.status_code}, response={r.text}")
    except Exception as e:
        logging.error(f"Error sending call metadata: {e}")

def upload_recording(variables):
    """Upload MixMonitor recording file to Odoo."""
    uniqueid = variables.get("UNIQUEID", "")
    mix_file = variables.get("MIXMONITOR_FILENAME", "")
    if not mix_file or not os.path.exists(mix_file):
        logging.warning(f"Recording file not found: {mix_file}")
        return

    filename = os.path.basename(mix_file)
    files = {
        "uniqueid": (None, uniqueid),
        "recording_file": (filename, open(mix_file, "rb")),
        "filename": (None, filename)
    }

    try:
        r = requests.post(UPLOAD_RECORDING_URL, files=files, timeout=10)
        logging.info(f"Recording uploaded: status={r.status_code}, response={r.text}")
    except Exception as e:
        logging.error(f"Error uploading recording: {e}")
    finally:
        files["recording_file"][1].close()

def main():
    variables = parse_args(sys.argv[1:])
    logging.info(f"Script started with variables: {variables}")
    send_call_metadata(variables)
    upload_recording(variables)
    logging.info("Script finished")

if __name__ == "__main__":
    main()
