#!/usr/bin/env python

import sys

from cp437 import ansi
from cp437 import vt100

DEBUG_NONE = 0
DEBUG_INFO = 1
DEBUG_EVENT = 2
DEBUG_STATE = 3
DEBUG = DEBUG_NONE

def debug_level(level):
    global DEBUG
    
    if not 0 < level < 4:
        raise ValueError('debug level must be cp437.DEBUG_NONE, cp437.DEBUG_INFO, cp437.DEBUG_EVENT or cp437.DEBUG_STATE')

    DEBUG = level

def debug(level, message, *args):
    global DEBUG
    
    if debug == DEBUG_NONE:
        return

    if not DEBUG >= level:
        return

    levels = {DEBUG_INFO: '\x1b[1;34mINFO\x1b[0m',
              DEBUG_EVENT: '\x1b[1;32mEVENT\x1b[0m',
              DEBUG_STATE: '\x1b[1;31mSTATE\x1b[0m'}

    sys.stderr.write('[{}] {}\n'.format(levels[level], message.format(*args)))
    sys.stderr.flush()

def debug_info(message, *args):
    return debug(DEBUG_INFO, message, *args)

def debug_event(message, *args):
    return debug(DEBUG_EVENT, message, *args)

def debug_state(message, *args):
    return debug(DEBUG_STATE, message, *args)

__all__ = ['ansi', 'vt100']
