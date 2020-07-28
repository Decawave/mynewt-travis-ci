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

class TwrAlohaBoard(HwtBoard):
    """Represents a TwrAloha board used in tests"""
    def __init__(self, cfg=None, verbose=None, time_cb=None):
        super(TwrAlohaBoard, self).__init__(cfg=cfg, verbose=verbose, time_cb=time_cb)
        self.stat.update({"num_80ms_miss": 0, "num_500ms_miss": 0, "total_tag_msgs": 0})
        self.dev_stat_names += ["mac"]
        self.tag_obj_log = {}
        self.event_timer = threading.Timer(0.01, self.stat_dump_do)

    def json_serialise(self):
        s = "{\"hwt\": "
        s += super(TwrAlohaBoard, self).json_serialise()
        s += ", \"tag_obj_log\": [{}]".format(json.dumps(self.tag_obj_log))
        s += "}\n"
        return s

    def received_line(self, line):
        super(TwrAlohaBoard, self).received_line(line)

    def received_object(self, obj):
        try:
            test = obj.items()
        except:
            print("### Not an object\n");
            return

        if (self.verbose>4):
            print(obj);
        if "part_id" in obj:
            self.board_id.update(obj);
        elif "uid" in obj:
            # Ignore all measurements until we've been initialised
            if not self.init_complete: return
            self.stat["total_tag_msgs"] += 1
            if "ouid" in obj:
                tag_id = "tag_{:04x}".format(int(obj["ouid"]))

                if tag_id in self.tag_obj_log:
                    level = "WW"
                    dt = 0;
                    try:
                        dt = obj['utime'] - self.tag_obj_log[tag_id][-1]['utime']
                    except KeyError:
                        pass
                    dt = dt/1000000.0

                    # List of things that can go wrong
                    if dt > 0.5 :
                        self.stat["num_500ms_miss"] += 1
                    elif dt > 0.08 :
                        self.stat["num_80ms_miss"] += 1

                    if dt > 0.5:
                        self.trigger_event("error_{}".format(tag_id), "{}:{} dt > 0.5 ({:.4f})".format(self.cfg['name'], tag_id, dt))
                        level = "EE"
                    if dt > 0.08:
                        if (self.verbose>1):
                            sys.stdout.write('[{}] {}:{} t:{:.4f} dt:{:.4f} (>0.08)\n'.format(level, self.cfg['name'], tag_id, obj['utime'], dt))

                else:
                    # New data for this tag
                    self.tag_obj_log[tag_id] = []

                self.tag_obj_log[tag_id].append(obj)

        super(TwrAlohaBoard, self).received_object(obj)

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

    def run_checks(self):
        ok = True
        ret = "All checks passed"
        tbounds = [1e6, -1e6]
        codes = {}
        for tobj in self.recv_objs:
            o = tobj['o']
            t = tobj['t']
            tbounds[0] = t if t<tbounds[0] else tbounds[0]
            tbounds[1] = t if t>tbounds[1] else tbounds[1]
            if "c" not in o: continue
            code_id = "code_{:x}".format(o["c"])
            if code_id not in codes:
                codes[code_id] = []
            codes[code_id].append(o)

        for k,c in codes.items():
            rngps = len(c)/(tbounds[1] - tbounds[0])
            if rngps < 5.0:
                ok = False
                ret = "{}: {:.2f} rng/s < 5.0".format(k, rngps)
            else:
                if (self.verbose>1):
                    print("  # {}: {:.2f} rng/s".format(k, rngps))

        if 'check_codes' in self.cfg:
            for check in self.cfg['check_codes']:
                if check["id"] not in codes:
                    ok = False
                    ret = "{}({}) missing from data".format(check["id"], check["name"])

        return (ok, ret);

    def start_timer_expiry(self):
        super(TwrAlohaBoard, self).start_timer_expiry()
        time.sleep(0.05);
        self.linereader.write_line("config uwb/frame_filter 0xf")
        time.sleep(0.05);
        self.linereader.write_line("config commit")

