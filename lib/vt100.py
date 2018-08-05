#!usr/bin/env python

class VT100Block(object):
    BACKGROUND = 0
    FOREGROUND = 0
    CHARACTER = 0

    def __init__(self, *args, **kwargs):
        self.background = kwargs.setdefault('background', kwargs.setdefault('bg', self.BACKGROUND))
        self.foreground = kwargs.setdefault('foreground', kwargs.setdefault('fg', self.FOREGROUND))
        self.character = kwargs.setdefault('character', kwargs.setdefault('c', self.CHARACTER))

        if not isinstance(self.background, int):
            raise ValueError('background must be an int')

        if not isinstance(self.foreground, int):
            raise ValueError('foreground must be an int')

        if not isinstance(self.character, int) and not isinstance(self.character, str):
            raise ValueError('character must be either an int or a single-character string')

class VT100Screen(object):
    def __init__(self, width, height, linebuffer):
        self.width = width
        self.height = height
        self.linebuffer = linebuffer

class VT100Event(object):
    def __init__(self, screen):
        self.screen = screen

    def __call__(self, *args):
        pass

class PrintEvent(VT100Event):
    pass

class NewLineModeEvent(VT100Event):
    pass
