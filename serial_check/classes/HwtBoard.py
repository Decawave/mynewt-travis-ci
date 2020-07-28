#!/usr/bin/env python3
import sys, argparse, tty, termios
from queue import Queue
from threading import Thread
import re
import time
import json
import serial
import serial.threaded
import subprocess
import threading
from serial.tools.list_ports import comports
import subprocess
from socket import *

class HwtSerial(serial.threaded.LineReader):
    """Represents the serial connection to a board used in the test"""
    def __init__(self):
        super(HwtSerial, self).__init__()
        self.rx_cb = None
        self.rx_raw_cb = None
        self.connected = False

    def connection_made(self, transport):
        super(HwtSerial, self).connection_made(transport)
        self.connected = True

    def handle_line(self, line):
        d = None
        try:
            trimline = re.sub("^[0-9]+ ", "", line.strip());
            trimline = re.sub("compat> ", "", trimline);
            trimline.replace('\x00',''); # Remove any null bytes
            d = json.loads(trimline);

        except json.decoder.JSONDecodeError:
            pass

        if d != None:
            if self.rx_cb != None:
                self.rx_cb(d)
        elif self.rx_raw_cb != None:
            self.rx_raw_cb(line)

class HwtBoard:
    """Represents a board used in the test"""
    def __init__(self, cfg=None, verbose=None, time_cb=time.time()):
        self.running = False
        self.init_complete = False
        self.cfg = cfg
        self.time_cb = time_cb
        self.board_id = {}
        self.verbose = verbose or 0
        self.image_version = None
        self.comm_ser = None
        self.proto = None
        self.linereader = None
        self.recv_objs = []
        self.recv_lines = []
        self.error_lines = []
        self.event_cbs = []
        self.stat = {}
        self.last_cmd = 0
        #
        self.dev_stat_names = []
        self.dev_stat = []
        self.stat_buf = {}
        self.stat_buf_name = None
        self.stat_buf_time = 0
        self.stat_buf_ticks = -1
        self.stat_dump_reason = None
        #
        self.stats_timer_interval = 10;
        if "stats_timer_interval" in self.cfg:
            self.stats_timer_interval = self.cfg["stats_timer_interval"];
        self.stats_timer = threading.Timer(self.stats_timer_interval, self.stats_timer_expiry)
        self.start_timer = threading.Timer(0.1, self.start_timer_expiry)
        self.end_timer = threading.Timer(0.1, self.end_timer_expiry)

    def json_serialise(self):
        s = "{"
        s+= "\"cfg\": {}\n".format(json.dumps(self.cfg))
        s+= ",\"id\": {}\n".format(json.dumps(self.board_id))
        s+= ",\"image_version\": {}\n".format(json.dumps(self.image_version))
        s+= ",\"stat\": [{}]\n".format(json.dumps(self.stat))
        s+= ",\"dev_stat\": [{}]\n".format(json.dumps(self.dev_stat))
        s+= ",\"recv_objs\": [{}]\n".format(json.dumps(self.recv_objs))
        s+= ",\"recv_lines\": [{}]\n".format(json.dumps(self.recv_lines))
        s+= ",\"error_lines\": [{}]\n".format(json.dumps(self.error_lines))
        s+= "}\n"
        return s

    def init_serial(self):
        # Find this serial
        if (self.verbose>0): print("# {}: Looking for serial port with serial: {}".format(self.cfg['name'], self.cfg['com_serial']))
        for p in sorted(comports()):
            if self.cfg['com_serial'] == p.serial_number:
                try:
                    print("#   Opening {}".format(p.device))
                    self.comm_ser = serial.Serial(p.device, baudrate=self.cfg['baudrate'], timeout=1)
                except serial.serialutil.SerialException:
                    print('# Could not open ' + p.device)
                break
        if self.comm_ser != None:
            self.proto = serial.threaded.ReaderThread(self.comm_ser, HwtSerial)
        else:
            print('# {}: Could not find port with serial {}'.format(self.cfg['name'], self.cfg['com_serial']))

    def stats_timer_restart(self):
        self.stats_timer.cancel()
        self.stats_timer = threading.Timer(self.stats_timer_interval, self.stats_timer_expiry)
        self.stats_timer.start()

    def stats_timer_expiry(self):
        if not self.running: return
        self.stat_dump("timer")
        self.stats_timer = threading.Timer(self.stats_timer_interval, self.stats_timer_expiry)
        self.stats_timer.start()

    def trigger_event(self, event_type, reason=None):
        for cb in self.event_cbs:
            if cb["type"] == event_type:
                cb["func"](reason)

    def add_event_cb(self, event_type, cb):
        self.event_cbs += [{"type": event_type, "func": cb}]

    def received_object(self, obj):
        if not self.init_complete or not self.running: return
        self.recv_objs.append({"t": self.time_cb(), "o": obj})

    def save_dev_stat(self, r):
        if self.stat_buf_name != None:
            new_stat = {"t": self.stat_buf_time, "name": self.stat_buf_name, "ticks": self.stat_buf_ticks, "stat": self.stat_buf}
            self.dev_stat.append(new_stat)
            if (self.verbose > 2):
                sys.stdout.write('{}: save_reason:"{}" {}\n'.format(self.cfg['name'], r, new_stat))
        self.stat_buf = {'reason': self.stat_dump_reason}
        self.stat_buf_name = None

    def received_line(self, line):
        if not self.running: return
        trimline = line.strip()
        ticks = -1
        try:
            if (trimline[0].isdigit()):
                ticks = trimline.split()[0]
        except IndexError:
            pass

        if (self.verbose > 5): sys.stdout.write('{}: 0"{}"\n'.format(self.cfg['name'], trimline))
        self.recv_lines.append({"t": self.time_cb(), "line": trimline})

        # Remove any leading timestamp from the stat value
        trimline = re.sub("^[0-9]+ ", "", trimline);
        trimline = re.sub("compat> ", "", trimline);

        if "stat " in trimline:
            self.save_dev_stat("new stat")
            try:
                self.stat_buf_time = self.time_cb()
                self.stat_buf_ticks = ticks
                self.stat_buf_name = trimline.split()[1]
            except IndexError:
                self.stat_buf_name = "unknown"
        elif " abc " in line:
            # Image version and hash
            self.image_version = ' '.join(trimline.split()[1:5])
        elif "level=3" in line:
            # An error logged from something
            self.error_lines.append({"t": self.time_cb(), "line": trimline})
        elif len(trimline) < 1:
            # An empty line could be the end of a stat log
            if (len(self.stat_buf) > 2):
                self.save_dev_stat("len: {:d}".format(len(trimline)))
        elif self.stat_buf_name != None:
            try:
                s = {trimline.split()[0].rstrip(':'): int(trimline.split()[1])}
                self.stat_buf.update(s)
            except:
                pass
            if self.stat_buf_ticks == -1:
                self.stat_buf_ticks = ticks
        elif (len(trimline) > 1 and self.verbose > 2):
            sys.stdout.write('{}: "{}"\n'.format(self.cfg['name'], trimline))


    def stat_dump(self, reason):
        print("No stat_dump implemented");

    def run_checks(self):
        return (1, "No run_checks implemented");

    def start_end_stat_dump(self, reason):
        self.stat_dump(reason)

        if not "start_end_stats" in self.cfg: return
        cmds = [""]
        for n in self.cfg["start_end_stats"]:
            cmds += ["stat {}".format(n)]
        cmds += ["stat stat"]  # Force saving of the normal stats

        self.stat_dump_reason = reason
        for c in cmds:
            self.linereader.write_line(c)
            time.sleep(0.05);

    def end_timer_expiry(self):
        print("{}: end timer".format(self.cfg['name']))
        self.start_end_stat_dump("Shutdown")
        time.sleep(1.0);
        self.running = False
        self.stats_timer.cancel()
        self.proto.close()
        print("{}: end timer done".format(self.cfg['name']))

    def start_timer_expiry(self):
        print("{}: start timer".format(self.cfg['name']))
        while not self.running:
            time.sleep(0.05);
        while not self.linereader.connected:
            time.sleep(0.05);
        try:
            if (self.cfg['initial_reset']):
                sys.stdout.write('{}: Issuing reset\n'.format(self.cfg['name']))
                self.linereader.write_line("")
                time.sleep(0.01);
                self.linereader.write_line("reset")
                time.sleep(2);
        except:
            pass
        self.linereader.write_line("")
        time.sleep(0.05);
        self.linereader.write_line("\nimgr list")
        time.sleep(0.05);
        self.linereader.write_line("\nconfig dump")
        time.sleep(0.05);
        self.start_end_stat_dump("Startup")
        self.init_complete = True

    def start(self):
        self.running = True
        if self.proto == None: return;

        # Start thread and get HwtSerial class
        self.linereader = self.proto.__enter__()
        #print(repr(self.linereader.__dict__))
        self.linereader.rx_cb = self.received_object
        self.linereader.rx_raw_cb = self.received_line
        self.start_timer.start()


    def stop(self):
        self.end_timer.start()

    def prepare(self, path):
        if not "debugger_serial" in self.cfg: return
        if not "target" in self.cfg: return
        if not "bl_target" in self.cfg: return
        print(self.cfg)
        cmd = ['nrfjprog','-f', 'NRF52', '-e', '-s', '{}'.format(self.cfg["debugger_serial"])]
        print(" ".join(cmd))
        erase_ret = subprocess.call(cmd, cwd=path)
        bl_load_ret = subprocess.call(["newt", "load", "{}".format(self.cfg["bl_target"]), '--extrajtagcmd', "-select usb={}".format(self.cfg["debugger_serial"])], cwd=path)
        load_ret = subprocess.call(["newt", "load", "{}".format(self.cfg["target"]), "--extrajtagcmd", "-select usb={}".format(self.cfg["debugger_serial"])], cwd=path)
        return (erase_ret and bl_load_ret and load_ret)

