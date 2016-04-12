#!/usr/bin/env python

import subprocess
import sys
import datetime
import time
import argparse
import traceback
from firebase import firebase
import logging
import json
import urllib2

logger = logging.getLogger('iBeaconServer')
logger.setLevel(logging.INFO)

LOG_FILE_NAME = 'ibeacon_server.log'
MINOR_ID_KEY = 'MinorId'
TUNE_DAWG_MAJOR_ID = 15229

APPBOY_SEND_ENDPOINT = "https://api.appboy.com/campaigns/trigger/send"
APPBOY_APP_ID = "669b7e12-fb53-4622-a116-da620b9835e1"

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
        self.timeToCountAbsent = int(timeToCountAbsent)
        self.command = command
        self.unknown_dawgs = []
        self.dawgs_in_office = {}
        self.dawg_name_map = self.build_dawg_name_map()

    def build_dawg_name_map(self):
        result = {}
        dawgs = firebase.get("/Dogs", None)
        for name, info in dawgs.iteritems():
            if MINOR_ID_KEY in info:
                result[info[MINOR_ID_KEY]] = name
            else:
                logger.info("%s does not have a minor ID. Please fix that." % name)

        return result

    def reset_all_dawgs(self):
        names = self.dawg_name_map.values()
        for name in names:
            self.update_dawg_in_office_status(name, "nil")

    def mark_dawg_in_office(self, raw_ping):
        ping = BeaconPing(raw_ping)

        # Check that we know about this dawg
        if (ping.minor in self.dawg_name_map):
            dawg_name = self.dawg_name_map[ping.minor]
            if (not self.dawgs_in_office.has_key(dawg_name)):
                logger.info("%s is in the Office!" % dawg_name)
                self.update_dawg_in_office_status(dawg_name, True)
                self.send_notification_for_dawg_subscribers(dawg_name)
            self.dawgs_in_office[dawg_name] = int(time.time())
        else:
            if (not ping.minor in self.unknown_dawgs):
                self.unknown_dawgs.append(ping.minor)
                logger.info("Unknown Dawg! ping.minor: %s" % ping.minor)

    def get_dawg(self, dawg_name):
        return firebase.get("/Dogs", dawg_name)

    def update_dawg_in_office_status(self, dawg_name, status):
        dawg = self.get_dawg(dawg_name)
        dawg['IsHere'] = status
        firebase.put("/Dogs", dawg_name, dawg)

    def check_for_absent_dawgs(self):
        now = int(time.time())
        names = self.dawgs_in_office.keys()
        for name in names:
            last_seen = self.dawgs_in_office[name]
            last_seen_offset = now - last_seen
            if (last_seen_offset >= self.timeToCountAbsent):
                logger.info("%s hasn't been in the office in a while, marking absent." % name)
                del self.dawgs_in_office[name]
                self.update_dawg_in_office_status(name, "nil")

    def start(self):
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        while (self.process.poll() is None):
            output = self.process.stdout.readline()
            if output:
                output = output.rstrip()

                logger.debug(output)

                self.mark_dawg_in_office(output)
                self.check_for_absent_dawgs()

        self.process = None
        self.exit("Subprocess done gone closed on us. That's a wrap folks!")

    def reset_bluetooth_module(self):
        return_code = subprocess.call(["sudo hciconfig hci0 reset"], shell=True)
        logger.info("Tried to reset the bluetooth module hci0. Return code: " + str(return_code))

    def send_notification_for_dawg_subscribers(self, dawg_name):
        dawg = self.get_dawg(dawg_name)

        if not 'CampaignId' in dawg:
            logger.warn("Unable to notify %s due to unknown CampaignId." % dawg_name)
            return

        data = { "app_group_id": APPBOY_APP_ID, "campaign_id": dawg['CampaignId'] }

        req = urllib2.Request(APPBOY_SEND_ENDPOINT)
        req.add_header('Content-Type', 'application/json')

        response = urllib2.urlopen(req, json.dumps(data))

        logger.info("AppBoy Response: %s" % response.read())

    def exit(self, msg):
        logger.info(msg)
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
                        action='store_true',
                        default=False,
                        help="Flag to determine if we should use the mock script or not.")

    parser.add_argument('-v',
                        dest='verbose',
                        required=False,
                        action='store_true',
                        default=False,
                        help="Flag to determine if we should log verbosely (each ping).")

    args = parser.parse_args()

    ## Setup Logger
    ################
    if (args.verbose):
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    # create file handler which logs even debug messages
    fh = logging.FileHandler(LOG_FILE_NAME)
    fh.setLevel(logging_level)

    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging_level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.setLevel(logging_level)

    if (args.testing):
        command = ['./ibeacon_scan_mock.sh']
    else:
        command = ['./ibeacon_scan.sh -b']

    beacon_server = BeaconServer(args.absentTime, command)

    try:
        # 1. Reset the bluetooth module each time we start. This fixes issue
        # with it getting into a funky state where pings don't come across.
        # 2. Reset all the dawgs. If they're in the office we should pick them
        # immediately and set their state.
        if (not args.testing):
            beacon_server.reset_bluetooth_module()
            beacon_server.reset_all_dawgs()

        logger.info("Starting to listen for iBeacons...")
        beacon_server.start()
    except KeyboardInterrupt:
        beacon_server.exit("User exited the program. Shutting down...")
    except Exception as e:
        traceback.print_exception(*sys.exc_info())
        beacon_server.exit("Something failed, Shutting down...")
