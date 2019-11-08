#!/usr/bin/env python3
import sys, argparse
import json

def time_sort(e):
    if "t" in e:
        return e["t"]
    else:
        return 0

parser = argparse.ArgumentParser()
parser.add_argument('files', metavar='files', default=None, nargs='?')
parser.add_argument('-v', dest='verbose', action="count", default=0, help='increase verbosity')
parser.add_argument('-s', dest='start', action="store", type=float, default=0.0, help='Start point')
parser.add_argument('-e', dest='end', action="store", type=float, default=10.0, help='End point')

args = parser.parse_args()

if args.files == None:
    print("data needed")
    sys.exit(1)

lines = []
with open(args.files) as f:
    try:
        d = json.load(f);
    except:
        print("Failed to load json");
        sys.exit(1)
    for b in d["boards"]:
        for s in b['hwt']["dev_stat"][0]:
            try:
                if s["t"] < args.start: continue
                if s["t"] > args.end: continue
                bdata = {"board": b["hwt"]["cfg"]["name"]}
                bdata.update(s)
                lines.append(bdata)
            except TypeError:
                #print(s)
                pass
        for s in b['hwt']["recv_objs"][0]:
            try:
                if s["t"] < args.start: continue
                if s["t"] > args.end: continue
                bdata = {"board": b["hwt"]["cfg"]["name"]}
                bdata.update(s)
                lines.append(bdata)
            except TypeError:
                #print(s)
                pass

    for t in d["threads"]:
        for l in t["recv_objs"][0]:
            try:
                if l["t"] < args.start: continue
                if l["t"] > args.end: continue
                lines.append(l)
            except TypeError:
                #print(s)
                pass

    # Sort?!
    lines.sort(key=time_sort)
    for l in lines:
        print(l)
