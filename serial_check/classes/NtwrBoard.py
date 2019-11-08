#!/usr/bin/env python3
import sys, argparse, tty, termios
from queue import Queue
from threading import Thread
import collections
import re
import time
import json
import serial
import serial.threaded
import threading
from serial.tools.list_ports import comports
import subprocess
from socket import *

from .HwtBoard import HwtBoard

class NtwrBoard(HwtBoard):
    """Represents a NTWR board used in tests"""
    def __init__(self, cfg=None, verbose=None, time_cb=None):
        super(NtwrBoard, self).__init__(cfg=cfg, verbose=verbose, time_cb=time_cb)
        self.stat.update({"num_60ms_miss": 0, "num_200ms_miss": 0, "num_500ms_miss": 0, "num_1s_miss": 0, "num_negative_dt": 0,
                  "missing_meas": 0, "single_anchor": 0, "total_tag_msgs": 0, "total_meas": 0})
        self.dev_stat_names += ["ccp", "pan", "tdma", "mac"]
        self.tag_obj_log = {}
        self.event_timer = threading.Timer(0.01, self.stat_dump_do)

    def json_serialise(self):
        s = "{\"hwt\": "
        s += super(NtwrBoard, self).json_serialise()
        s += ", \"tag_obj_log\": [{}]".format(json.dumps(self.tag_obj_log))
        s += "}\n"
        return s

    def received_line(self, line):
        super(NtwrBoard, self).received_line(line)

    def received_object(self, obj):
        try:
            test = obj.items()
        except:
            print("### Not an object\n");
            return

        if "euid" in obj:
            self.board_id.update(obj);
        elif "mid" in obj:
            # Ignore all measurements until we've been initialised
            if not self.init_complete: return
            self.stat["total_tag_msgs"] += 1
            if "id" in obj:
                tag_id = "tag_{}".format(obj["id"])

                if tag_id in self.tag_obj_log:
                    level = "WW"
                    dt = 0;
                    try:
                        dt = obj['ts'] - self.tag_obj_log[tag_id][-1]['ts']
                    except KeyError:
                        pass

                    # List of things that can go wrong
                    if dt > 1.0 :
                        self.stat["num_1s_miss"] += 1
                    elif dt > 0.5 :
                        self.stat["num_500ms_miss"] += 1
                    elif dt > 0.2 :
                        self.stat["num_200ms_miss"] += 1
                    elif dt > 0.06 :
                        self.stat["num_60ms_miss"] += 1
                    elif dt < -0.01 :
                        self.stat["num_negative_dt"] += 1

                    if dt > 0.2:
                        self.trigger_event("error_{}".format(tag_id), "{}:{} dt > 0.2 ({:.4f})".format(self.cfg['name'], tag_id, dt))
                        level = "EE"
                    if dt < -0.01:
                        self.trigger_event("error_{}".format(tag_id), "{}:{} dt < -0.01 ({:.4f})".format(self.cfg['name'], tag_id, dt))
                        level = "EE"
                    if dt > 0.06 :
                        if (self.verbose>1):
                            sys.stdout.write('[{}] {}:{} t:{:.4f} dt:{:.4f} (>0.06)\n'.format(level, self.cfg['name'], tag_id, obj['ts'], dt))
                    try:
                        if (len(obj["meas"]["a"]) == 1):
                            self.trigger_event("warning", "{}:{} single_anchor".format(self.cfg['name'], tag_id))
                            self.stat["single_anchor"] += 1
                        self.stat["total_meas"] += 1
                    except:
                        self.trigger_event("warning", "{}:{} missing_meas".format(self.cfg['name'], tag_id))
                        self.stat["missing_meas"] += 1
                else:
                    # New data for this tag
                    print("### New tag_id:{} ".format(tag_id))
                    self.tag_obj_log[tag_id] = []

                self.tag_obj_log[tag_id].append(obj)

        super(NtwrBoard, self).received_object(obj)

    def stat_dump_do(self):
        if self.linereader == None:
            print("### ERROR: {} No serial connection".format(self.cfg['name']))
            return
        t = time.time()
        dt = t - self.last_cmd
        if dt < 0.5:
            return
        self.last_cmd = t

        cmds = [""]
        for n in self.dev_stat_names:
            cmds += ["stat {}".format(n)]
        cmds += ["stat stat"]  # Force saving of the normal stats

        self.stats_timer_restart()
        for c in cmds:
            try:
                self.linereader.write_line(c)
                time.sleep(0.05);
            except:
                print("### {} Error writing cmd".format(self.cfg['name']))
        self.stats_timer_restart()

    def stat_dump(self, reason):
        print("### {}: dump_request {} ".format(self.cfg['name'], reason))
        if self.linereader == None:
            print("### ERROR: {} No serial connection".format(self.cfg['name']))
            return
        if self.event_timer.is_alive():
            print("### {}: WW already dumping".format(self.cfg['name']))
            return
        self.stat_dump_reason = reason
        self.event_timer.cancel()
        self.event_timer = threading.Timer(0.01, self.stat_dump_do)
        self.event_timer.start()
