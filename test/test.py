#!/usr/bin/env python

import sys

import cp437
from cp437 import vt100

if __name__ == '__main__':
    parser = vt100.VT100Parser(filename='joey.ans')
    screen_9px = vt100.VT100Screen(width=80
                                   ,height=24
                                   ,linebuffer=4096
                                   ,nfo=False)
    parser.parse(screen_9px)
    parsed = screen_9px.dump_str(colors=True, utf8=True)

    if not sys.stdout.encoding:
        parsed = bytearray(parsed, 'utf8')

    print parsed
