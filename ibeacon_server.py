
#!/usr/bin/env python

import subprocess
import sys
import datetime
import time
import argparse
import traceback
from firebase import firebase

LOG_FILE_NAME = 'ibeacon_server.log'
TUNE_DAWG_MAJOR_ID = 1
TUNE_DAWG_MINOR_MAP = {
    '41': 'Toby',
    '61': 'Mac'
}

firebase = firebase.FirebaseApplication('https://tunedog.firebaseio.com/', None)

class BeaconPing():
    def __init__(self, beacon_ping_string):
        parts = beacon_ping_string.split(' ')
        self.uuid = parts[0]
        self.major = parts[1]
        self.minor = parts[2]
        self.power = parts[3]

class BeaconServer():
    def __init__(self, timeToCountAbsent, command):
        self.timeToCountAbsent = timeToCountAbsent
        self.log_file = open(LOG_FILE_NAME, 'w')
        self.command = command
        self.unknown_dawgs = []
        self.dawgs_in_office = {}

    def log(self, msg):
        output = '%s - %s' % (datetime.datetime.now(), msg)
        print(output)
        self.log_file.write(output)

    def mark_dawg_in_office(self, raw_ping):
        ping = BeaconPing(raw_ping)

        # Check that we know about this dawg
        if (ping.minor in TUNE_DAWG_MINOR_MAP):
            dawg_name = TUNE_DAWG_MINOR_MAP[ping.minor]
            if (not self.dawgs_in_office.has_key(dawg_name)):
                self.update_dawg_in_office_status(dawg_name, True)
            self.dawgs_in_office[dawg_name] = int(time.time())
        else:
            if (not ping.minor in self.unknown_dawgs):
                self.unknown_dawgs.append(ping.minor)
                self.log("Unknown Dawg! ping.minor: %s" % ping.minor)

    def update_dawg_in_office_status(self, dawg_name, status):
        dawg = firebase.get("/Dogs", dawg_name)
        dawg['IsHere'] = status
        firebase.put("/Dogs", dawg_name, dawg)

    def check_for_absent_dawgs(self):
        now = int(time.time())
        for dawg_name, last_seen in self.dawgs_in_office.iteritems():
            last_seen_offset = now - last_seen
            if (last_seen_offset >= self.timeToCountAbsent):
                del self.dawgs_in_office[dawg_name]
                self.update_dawg_in_office_status(dawg_name, nil)

    def start(self):
        self.log("Starting to listen for iBeacons...")

        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        while (self.process.poll() is None):
            output = self.process.stdout.readline()
            if output:
                output = output.rstrip()

                self.log(output)
                self.mark_dawg_in_office(output)
                self.check_for_absent_dawgs()

        self.process = None
        self.exit("Subprocess done gone closed on us. That's a wrap folks!")

    def exit(self, msg):
        self.log(msg)
        if (self.process is not None):
            self.process.kill()
        sys.exit(0)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('-a',
                        dest='absentTime',
                        required=False,
                        default=3600, # One hour
                        help="How long to wait till marking a seen dawg as absent.")

    parser.add_argument('-t',
                        dest='testing',
                        required=False,
                        default=False,
                        help="Flag to determine if we should use the mock script or not.")

    args = parser.parse_args()

    if (args.testing):
        command = ['ibeacon_scan_mock.sh']
    else:
        command = ['ibeacon_scan.sh', '-b']

    beacon_server = BeaconServer(args.absentTime, command)

    try:
        beacon_server.start()
    except KeyboardInterrupt:
        beacon_server.exit("User exited the program. Shutting down...")
    except Exception as e:
        traceback.print_exception(*sys.exc_info())
        beacon_server.exit("Something failed, Shutting down...")
