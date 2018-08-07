#!/usr/bin/env python

import cp437
from cp437 import vt100

if __name__ == '__main__':
    parser = vt100.VT100Parser(filename='/mnt/c/Users/teal/Documents/Art/ANSI/adnu.ans')
    screen = vt100.VT100Screen(80, 24, 4096)
    parser.parse(screen)
    screen.dump_png('test.png')
