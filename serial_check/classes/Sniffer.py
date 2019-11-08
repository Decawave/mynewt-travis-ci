#!/usr/bin/env python3
# socat TCP-LISTEN:2002 /dev/uwb_lstnr1
import sys
from threading import Thread
import time
import json
import threading
import socket
from serial.tools.list_ports import comports
import subprocess

class Sniffer(Thread):
    """A sniffer thread"""
    def __init__(self, address, port, time_cb=time.time):
        super(Sniffer, self).__init__()
        self.address = address
        self.port = port
        self.time_cb = time_cb
        self.ok_to_run = True
        self.recording = False
        self.connected = False
        self.recv_objs = []

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

    def json_serialise(self):
        s = "{\"address\": "
        s+= "\"{}\"\n".format(self.address)
        s+= ",\"num_lines\": "
        s+= "\"{}\"\n".format(len(self.recv_objs))
        s+= ",\"recv_objs\": [{}]\n".format(json.dumps(self.recv_objs))
        s+= "}\n"
        return s

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.address, self.port))
        buf = ""
        while (self.ok_to_run):
            buf += s.recv(256).decode('utf-8')
            lines = buf.split('\n')
            for line in lines:
                #print("line: {}".format(line))
                if not self.recording: continue

                try:
                    trimline = line.strip();
                    trimline.replace('\x00',''); # Remove any null bytes
                    d = json.loads(trimline);
                    self.recv_objs.append({"t": self.time_cb(), "o": d})

                except json.decoder.JSONDecodeError:
                    pass
            if buf[-1] != '\n':
                buf = lines[-1]
            else:
                buf = ""
        s.close()

    def stop(self):
        self.recording = False
        self.ok_to_run = False


if __name__ == '__main__':
    s = Sniffer("labdietpi.redcedar", 2002);
    s.start()
    s.recording = True
    time.sleep(0.1);
    s.ok_to_run = False
    time.sleep(1);
    for l in s.recv_objs:
        print(l["o"])
