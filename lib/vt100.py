#!usr/bin/env python

import sys

import png

import cp437
from cp437 import ansi

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

        if not 0 <= self.background < 16:
            raise ValueError('background color must be a value from 0-15')

        if not 0 <= self.foreground < 16:
            raise ValueError('background color must be a value from 0-15')

        if not 0 <= self.character < 256:
            raise ValueError('character must be a value from 0-255')

    @property
    def bg(self):
        return self.background

    @property
    def fg(self):
        return self.foreground

    @property
    def c(self):
        return self.character

    @property
    def bg_color(self):
        return ansi.colors[self.bg]

    @property
    def fg_color(self):
        return ansi.colors[self.fg]

    def __str__(self):
        return chr(self.c)

    def __repr__(self):
        return '<VT100Block: character:{}/background:{}/foreground:{}>'.format(self.c, self.bg, self.fg)

class VT100Screen(object):
    def __init__(self, width, height, linebuffer):
        self.width = width
        self.height = height
        self.linebuffer = linebuffer
        self.drawbuffer = dict()
        self.scroll = 0
        self.vX = 0 # viewing window
        self.vY = 0
        self.dX = 0 # drawing position
        self.dY = 0

        self.reset_attributes()

    def draw(self, c):
        if self.bright and self.fg < 8:
            self.fg += 8

        block = VT100Block(c=c, bg=self.bg, fg=self.fg)

        if self.dX >= self.width:
            self.dX = 0
            self.dY += 1

            if self.dY >= self.linebuffer:
                scroll = self.dY - self.linebuffer
                self.delete_rows(self.scroll,scroll+1)
                self.scroll = scroll

        if c == 0xA: # newline
            self.dY += 1
        elif c == 0xD: # carriage return
            self.dX = 0
        else:
            row = self.drawbuffer.setdefault(self.dY, dict())
            row[self.dX] = block
            self.dX += 1

    def delete_rows(self, d_from, d_to):
        for i in range(d_from,d_to):
            if i in self.drawbuffer:
                del self.drawbuffer[i]

    def reset_attributes(self):
        self.bg = 0
        self.fg = 7
        self.bright = False
        self.underscore = False
        self.blink = False
        self.reverse = False
        self.hidden = False

    def dump_str(self):
        end = self.dY + 1
        result = list()

        for row in xrange(end):
            if not row in self.drawbuffer:
                result.append('\n')
                continue

            last_col = 0

            for col in xrange(self.width):
                if not col in self.drawbuffer[row]:
                    continue

                delta = col - last_col
                last_col = col

                if delta > 1:
                    delta -= 1
                    result.append(' '*delta)

                block = self.drawbuffer[row][col]
                result.append(chr(block.c))

            if not last_col == self.width-1:
                result.append('\n')

        return ''.join(result)

    def dump_png(self, outfile):
        fp = open(outfile, 'wb')
        end = self.dY
        colors = ansi.colors.items()
        colors.sort(lambda x,y: cmp(x[0],y[0]))
        colors = map(lambda x: x[1], colors)
        output = png.Writer(width=self.width*9
                            ,height=end*16
                            ,alpha=False # TODO: custom backgrounds for presence of no characters
                            ,background=ansi.colors[0]
                            ,compression=9) # 'cause why not?
        
        # the goal here is to fill in the blanks, so this is sort of linke the dump-to-string algorithm
        result = list()
        current_color = {'fg': 7, 'bg': 0}

        image_data = list()

        for row in xrange(end):
            if not row in self.drawbuffer:
                self.drawbuffer[row] = dict()

            row_data = [list() for x in xrange(16)]

            for col in xrange(self.width):
                if not col in self.drawbuffer[row]:
                    # TODO: swap this out for magical custom background one day
                    block = VT100Block(c=0
                                       ,fg=7
                                       ,bg=0)
                else:
                    block = self.drawbuffer[row][col]
                    current_color['fg'] = block.fg
                    current_color['bg'] = block.bg

                if col >= 20 and col <= 27:
                    if row == 12:
                        print '({},{})'.format(col+1, row+1), repr(block)

                pixel_map = ansi.charset[block.c]

                for y in xrange(16):
                    for x in xrange(9):
                        pix = pixel_map[y][x]
                        color = ('bg', 'fg')[pixel_map[y][x]]
                        pixel = ansi.colors[current_color[color]]

                        for c in pixel:
                            row_data[y].append(c)

            for subrow in row_data:
                image_data.append(subrow)

        #print image_data
        output.write(fp, image_data)
        fp.close()

    def __str__(self):
        return dump_str()

    def __repr__(self):
        return '<VT100Screen: width:{}/height:{}/linebuffer:{}>'.format(self.width, self.height, self.linebuffer)

class VT100Event(object):
    def __init__(self, screen):
        self.screen = screen

    def __call__(self, *args):
        pass

class UnknownEvent(VT100Event):
    def __call__(self):
        sys.stderr.write('unknown event at ({},{})\n'.format(self.screen.dX,self.screen.dY))
        sys.stderr.flush()

class PrintEvent(VT100Event):
    def __call__(self, character):
        return self.screen.draw(character)

class NopEvent(VT100Event):
    def __call__(self):
        return

class CursorShiftEvent(VT100Event):
    UP = 'A'
    DOWN = 'B'
    RIGHT = 'C'
    LEFT = 'D'

    def __call__(self, direction, shift):
        if not direction in 'ABCD':
            raise ValueError('direction must be one of CursorShiftEvent.{UP,DOWN,RIGHT,LEFT}')

        if self.screen.bright and self.screen.fg < 8:
            self.screen.fg += 8

        if direction == 'A':
            self.screen.dY = max(0, self.screen.dY - shift)
        elif direction == 'B':
            old_dY = self.screen.dY

            self.screen.dY = self.screen.dY + shift

            for i in range(self.screen.dY - old_dY):
                for j in range(self.screen.width):
                    if not i in self.screen.drawbuffer:
                        self.screen.drawbuffer[old_dY+i] = dict()

                    self.screen.drawbuffer[old_dY+i][j] = VT100Block(c=0, fg=self.screen.fg, bg=self.screen.bg)
        elif direction == 'C':
            old_dX = self.screen.dX

            self.screen.dX = min(self.screen.width, self.screen.dX + shift)

            if not self.screen.dY in self.screen.drawbuffer:
                self.screen.drawbuffer[self.screen.dY] = dict()

            for i in range(self.screen.dX - old_dX):
                self.screen.drawbuffer[self.screen.dY][old_dX+i] = VT100Block(c=0, fg=self.screen.fg, bg=self.screen.bg)
        elif direction == 'D':
            self.screen.dX = max(0, self.screen.dX - shift)

class VT100Parser(object):
    EVENT_TABLE = None

    def __init__(self, *args, **kwargs):
        if not 'file' in kwargs and not 'filename' in kwargs and not 'stream' in kwargs:
            raise ValueError('no file, filename or stream present')

        if 'filename' in kwargs:
            self.filename = kwargs['filename']
            kwargs['file'] = open(self.filename, 'rb')
        else:
            self.filename = None
            
        if 'file' in kwargs:
            self.stream = kwargs['file'].read()

        self.event_table = kwargs.setdefault('event_table', self.EVENT_TABLE)

        if self.event_table is None:
            self.event_table = dict()

    def get_event(self, event, screen):
        if not issubclass(event, VT100Event):
            raise ValueError('event must subclass the VT100Event object')

        return self.event_table.get(event, event)(screen)
            
    def parse(self, screen):
        tape_index = 0
        peek_index = 0
        tape_eof = len(self.stream)
        print_state = 0
        esc_state = 1
        bracket_state = 2
        paren_state = 3
        pound_state = 4
        numeric_state = 5
        alpha_state = 6
        alnum_state = 7
        state = print_state
        bg = 0
        fg = 0

        # first, look for a PabloDraw SAUCE header.
        # parse it later tho lol
        sauce = self.stream[-129:]

        if sauce[:6] == '\x1aSAUCE':
            self.stream = self.stream[:-129]

        while tape_index < len(self.stream):
            c = self.stream[tape_index]

            if state == print_state:
                tape_index += 1

                if c == '\x1B':
                    state = esc_state
                    continue
                    
                print_event = self.get_event(PrintEvent, screen)
                print_event(ord(c))
            elif state == esc_state:
                peek_index = tape_index

                if c == '[': # bracket state
                    state = bracket_state
                elif c == '(' or c == ')': # paren state
                    state = paren_state
                elif c == '#': # pound state
                    state = pound_state
                elif c in '0123456789':
                    state = numeric_state
                elif c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
                    state = alpha_state
                elif c in '<=>':
                    state = alnum_state
            elif state == bracket_state: # escape sequence starts with an open bracket
                static_sequences = {
                    '[20h': UnknownEvent,
                    '[?1h': UnknownEvent,
                    '[?3h': UnknownEvent,
                    '[?4h': UnknownEvent,
                    '[?5h': UnknownEvent,
                    '[?6h': UnknownEvent,
                    '[?7h': UnknownEvent,
                    '[?8h': UnknownEvent,
                    '[?9h': UnknownEvent,
                    '[20l': UnknownEvent,
                    '[?1l': UnknownEvent,
                    '[?2l': UnknownEvent,
                    '[?3l': UnknownEvent,
                    '[?4l': UnknownEvent,
                    '[?5l': UnknownEvent,
                    '[?6l': UnknownEvent,
                    '[?7l': UnknownEvent,
                    '[?8l': UnknownEvent,
                    '[?9l': UnknownEvent,
                    '[g': UnknownEvent,
                    '[0g': UnknownEvent,
                    '[3g': UnknownEvent,
                    '[K': UnknownEvent,
                    '[0K': UnknownEvent,
                    '[1K': UnknownEvent,
                    '[2K': UnknownEvent,
                    '[J': UnknownEvent,
                    '[0J': UnknownEvent,
                    '[1J': UnknownEvent,
                    '[2J': UnknownEvent,
                    '[c': UnknownEvent,
                    '[0c': UnknownEvent,
                    '[2;1y': UnknownEvent,
                    '[2;2y': UnknownEvent,
                    '[2;9y': UnknownEvent,
                    '[2;10y': UnknownEvent,
                    '[0q': UnknownEvent,
                    '[1q': UnknownEvent,
                    '[2q': UnknownEvent,
                    '[3q': UnknownEvent,
                    '[4q': UnknownEvent}
            
                for i in xrange(6):
                    sliced = self.stream[peek_index:peek_index+1+i]

                    if sliced in static_sequences:
                        event = self.get_event(static_sequences[sliced], screen)
                        event()

                        state = print_state
                        tape_index = peek_index+1+i
                        continue

                stack = list()
                numerics = list()
                terminators = 'mrABCDHf'

                peek_index += 1

                if self.stream[peek_index:peek_index+3] == '?1;':
                    peek_index += 3

                while peek_index < tape_eof:
                    c = self.stream[peek_index]
                    peek_index += 1

                    if c in '0123456789':
                        stack.append(c)
                    elif c == ';':
                        s = ''.join(stack)
                        n = int(s)
                        stack = list()
                        numerics.append(n)
                    else:
                        break

                if not len(stack) == 0:
                    s = ''.join(stack)
                    n = int(s)
                    stack = list()
                    numerics.append(n)

                state = print_state

                if c == 'm':
                    # do the things
                    for n in numerics:
                        if n >= 90 and n <= 97 or n >= 100 and n <= 107:
                            screen.bright = True
                            n -= 60

                        if n == 0:
                            screen.reset_attributes()
                        elif n == 1:
                            screen.bright = True
                        elif n == 2:
                            print 'dim!'
                            screen.bright = False
                        elif n == 4:
                            screen.underscore = True
                        elif n == 5:
                            screen.blink = False
                        elif n == 7:
                            screen.reverse = True
                        elif n == 8:
                            screen.hidden = True
                        elif n >= 30 and n <= 37:
                            screen.fg = ansi.vga[n]
                        elif n >= 40 and n <= 47:
                            screen.bg = ansi.vga[n]

                    if len(numerics) == 0:
                        screen.reset_attributes()

                    tape_index = peek_index
                elif c in 'ABCD':
                    if len(numerics) == 0:
                        event = self.get_event(UnknownEvent, screen)
                        event()
                        continue

                    shift = numerics.pop(0)

                    if not len(numerics) == 0:
                        event = self.get_event(UnknownEvent, screen)
                        event()
                        continue

                    event = self.get_event(CursorShiftEvent, screen)
                    event(c, shift)
                    tape_index = peek_index
                else:
                    sys.stderr.write('found terminator: {} (numerics: {})\n'.format(c, numerics))
                    event = self.get_event(UnknownEvent, screen)
                    event()
            else:
                event = self.get_event(UnknownEvent, screen)
                event()
                state = print_state
