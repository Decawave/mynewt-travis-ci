#!/usr/bin/env python3
import sys, argparse, tty, termios
from queue import Queue
from threading import Thread
import re
import time
import datetime
import json
import serial
import serial.threaded
from serial.tools.list_ports import comports
import subprocess
from socket import *

from classes.HwtBoard import HwtBoard
from classes.NtwrBoard import NtwrBoard
from classes.Sniffer import Sniffer

start_t = 0;

def program_time():
    return round(time.time() - start_t, 4);

parser = argparse.ArgumentParser()
parser.add_argument('config', metavar='config', default=None, nargs='?')
parser.add_argument('-v', dest='verbose', action="count", default=0, help='increase verbosity')
parser.add_argument('-d', dest='duration', action="store", type=int, default=60, help='Duration to log')
parser.add_argument('-s', dest='save_results', action="store", type=str, default="", help='Save results')

args = parser.parse_args()

if args.config == None:
    print("Config needed")
    sys.exit(1)

config=None
with open(args.config) as config_file:
    config = json.load(config_file)

if config == None:
    print("Not a valid config file")
    sys.exit(1)

# Instantiate board classes
boards = []
threads = []
for boardcfg in config['boards']:
    if boardcfg["board_class"] == "NtwrBoard":
        b = NtwrBoard(boardcfg, verbose = args.verbose, time_cb=program_time)
    else: continue
    b.init_serial()
    boards.append(b)
    if b.proto == None:
        sys.exit(1)

if "sniffers" in config:
    for sniffer in config['sniffers']:
        s = Sniffer(sniffer["address"], sniffer["port"], time_cb=program_time);
        s.start()
        threads.append(s)


# Link Event -> Callbacks
for link in config['links']:
    src = next((x for x in boards if x.cfg['name'] == link["src"]), None)
    if src == None: continue

    for dst in link["dst"]:
        d = next((x for x in boards if x.cfg['name'] == dst), None)
        if dst == None: continue
        print("{}({}) -> {}({})".format(link["src"], link["src_type"], dst, link["dst_type"]))
        src.add_event_cb(link["src_type"], d.stat_dump)


###########  Start test
sys.stderr.write("## Started at {}, {:d}s run\n".format(datetime.datetime.now(), args.duration))
start_t = time.time()
sys.stdout.flush()

for b in boards:
    b.start()

for t in threads:
    t.recording = True

########### Main wait loop
try:
    while (time.time() - start_t < args.duration):
        sys.stdout.flush()
        time.sleep(0.5);
except KeyboardInterrupt:
    sys.stderr.write("\n#####################################\n")
    sys.stderr.write("# Keyboard Interrupt detected after {:.1f}s\n".format(time.time()-start_t))

print("\n#####################################")
for b in boards:
    b.save_dev_stat("shutdown")
    b.stop()

for t in threads:
    t.stop()

if args.save_results:
    sys.stderr.write("# Writing results to file\n");
    with open(args.save_results, "w") as f:
        f.write("{\"cmdline\": \"")
        f.write(' '.join(sys.argv))
        f.write("\",\n")
        f.write("\"boards\": [\n")
        is_first = True
        for b in boards:
            if not is_first:
                f.write(",\n")
            f.write(b.json_serialise())
            is_first = False
        f.write("],\n")
        f.write("\"threads\": [\n")
        is_first = True
        for t in threads:
            if not is_first:
                f.write(",\n")
            f.write(t.json_serialise())
            is_first = False
        f.write("]}\n")
        f.close()

time.sleep(1);
print("\n#####################################")

########### Output results
for b in boards:
    print("{} {} ({}):".format(b.cfg['name'], b.board_id, b.image_version))
    print("  {}".format(b.stat))
    print("  Num err lines: {:d}".format(len(b.error_lines)))
    if (args.verbose<1): continue
    print("############################")

    for s in b.error_lines:
        print("  EE: {}".format(s))
    print("# Stats")
    for name in b.dev_stat_names:
        for s in b.dev_stat:
            if s['name'] == name:
                print("  {}".format(s))
    if "start_end_stats" in b.cfg:
        for name in b.cfg["start_end_stats"]:
            for s in b.dev_stat:
                if s['name'] == name:
                    print("  {}".format(s))
    print("############################\n")

exit(0)
