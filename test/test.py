#!/usr/bin/env python

import cp437
from cp437 import vt100

if __name__ == '__main__':
    parser = vt100.VT100Parser(filename='/mnt/c/Users/teal/Documents/Art/ANSI/adnu.ans')
    screen_9px = vt100.VT100Screen(80, 24, 4096)
    parser.parse(screen_9px)
    screen_9px.dump_png('test-9px.png')

    screen_8px = vt100.VT100Screen(80, 24, 4096, vt100.VT100Screen.SPACING_8PX)
    parser.parse(screen_8px)
    screen_8px.dump_png('test-8px.png')
