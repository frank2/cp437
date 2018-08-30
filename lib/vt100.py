#!usr/bin/env python

import sys

import png

import cp437
from cp437 import ansi

class VT100Palette(object):
    PALETTE = None

    def __init__(self, palette=None, nfo=False):
        self.palette = palette or self.PALETTE
        self.nfo = nfo

        if self.palette is None:
            self.palette = dict()

        if not isinstance(self.palette, dict):
            raise ValueError('palette must be a dictionary object')

        self.depth = 2 if self.nfo else 16

        if self.depth == 2:
            self.palette[0] = palette.get(0, ansi.colors[0])
            self.palette[1] = palette.get(1, ansi.colors[7])
        else:
            for i in xrange(self.depth):
                self.palette[i] = palette.get(i, ansi.colors[i])

    def has(self, index):
        return index in self.palette

    def get(self, index): 
        if index > 1 and self.nfo:
            index = 1

        if not 0 <= index < self.depth:
            raise ValueError('color index out of range')

        return self.palette[index]

    def find(self, r, g=None, b=None):
        if isinstance(r, list) or isinstance(r, tuple):
            r, g, b = r

        t = (r,g,b)
        reverse_dict = dict(map(lambda x: x[::-1], self.palette.items()))

        if not t in reverse_dict:
            raise ValueError('color triad {} not found'.format(t))

        return reverse_dict[t]

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

    def __str__(self):
        return chr(self.c)

    def __repr__(self):
        return '<VT100Block: character:{}/background:{}/foreground:{}>'.format(self.c, self.bg, self.fg)

class VT100Screen(object):
    SPACING_9PX = True
    SPACING_8PX = False
    WIDTH = 80
    HEIGHT = 24
    LINEBUFFER = 4096
    SPACING = True
    NFO = False
    PALETTE = None

    def __init__(self, *args, **kwargs):
        self.width = kwargs.setdefault('width', self.WIDTH)
        self.height = kwargs.setdefault('height', self.HEIGHT)
        self.linebuffer = kwargs.setdefault('linebuffer', self.LINEBUFFER)
        self.spacing = 9 if kwargs.setdefault('spacing', self.SPACING) else 8
        self.palette = kwargs.setdefault('palette', self.PALETTE)

        if self.palette is None:
            self.palette = VT100Palette(dict(map(lambda x: tuple(x[:]), ansi.colors.items()[:])))

        if self.palette.nfo:
            indecies = range(2)
        else:
            indecies = range(16)

        for k in indecies:
            if not self.palette.has(k):
                raise ValueError('index must include all values 0-15 inclusive (0 or 1 in NFO mode)')

            if not len(self.palette.get(k)) == 3:
                raise ValueError('palette entry must be a triplet of values')

            for c in self.palette.get(k):
                if not 0 <= c < 256:
                    raise ValueError('RGB value must be a number between 0-255 inclusive')

        self.drawbuffer = dict()
        self.scroll = 0
        self.vX = 0 # viewing window
        self.vY = 0
        self.dX = 0 # drawing position
        self.dY = 0

        self.reset_attributes()

    def check_eol(self):
        if self.dX < self.width:
            return

        self.dX = 0
        self.dY += 1

        self.check_linebuffer()

    def check_linebuffer(self):
        if self.dY < self.linebuffer:
            return

        scroll = self.dY - self.linebuffer
        self.delete_rows(self.scroll,scroll+1)
        self.scroll = scroll

    def draw(self, c):
        cp437.debug_state('drawing onto screen')

        if self.palette.nfo:
            self.bg = 0
            self.fg = 1
            self.bright = 0

        if self.bright and self.fg < 8:
            self.fg += 8

        block = VT100Block(c=c, bg=self.bg, fg=self.fg)

        cp437.debug_state('screen state> dX: {} / dY: {} / block: {}', self.dX, self.dY, repr(block))

        if c == 0xA: # newline
            self.dX = 0
            self.dY += 1
            self.check_linebuffer()
        elif c == 0xD: # carriage return
            pass
        else:
            self.check_eol()

            row = self.drawbuffer.setdefault(self.dY, dict())
            row[self.dX] = block
            self.dX += 1

            self.check_eol()

        cp437.debug_state('screen state< dX: {} / dY: {}', self.dX, self.dY)

    def delete_rows(self, d_from, d_to):
        for i in range(d_from,d_to):
            if i in self.drawbuffer:
                del self.drawbuffer[i]

    def reset_attributes(self):
        cp437.debug_state('resetting attributes')

        self.bg = 0
        self.fg = 7 if not self.palette.nfo else 1
        self.bright = False
        self.underscore = False
        self.blink = False
        self.reverse = False
        self.hidden = False

    def dump_str(self, colors=False, utf8=False):
        end = self.dY+1
        result = list()
        current_color = {'fg': 7, 'bg': 0, 'bright': False}

        for row in xrange(end):
            if not row in self.drawbuffer:
                if not row+1 == end:
                    result.append(' '*self.width)
                    result.append('\n')

                continue

            last_col = 0

            for col in xrange(self.width):
                delta = col - last_col
                last_col = col

                if not col in self.drawbuffer[row]:
                    block = VT100Block(bg=0,fg=7,c=0)
                else:
                    block = self.drawbuffer[row][col]

                codes = list()

                if colors:
                    block_color = {'fg': block.fg, 'bg': block.bg, 'bright': block.fg > 7}

                    if not block_color == current_color:
                        result.append('\x1b[')
                        reset = False

                        if not block_color['bright'] == current_color['bright']:
                            if current_color['bright'] and not block_color['bright']:
                                codes.append('0')
                                reset = True
                            elif not current_color['bright'] and block_color['bright']:
                                codes.append('1')

                        if not block_color['fg'] == current_color['fg'] or reset:
                            fg_color = block_color['fg']
                            fg_color -= block_color['bright']*8
                            codes.append('3{}'.format(fg_color))

                        if not block_color['bg'] == current_color['bg'] or reset:
                            codes.append('4{}'.format(block_color['bg']))

                        if block_color['fg'] == 7 and block_color['bg'] == 0:
                            result.append('0m')
                        else:
                            result.append('{}m'.format(';'.join(codes)))

                        current_color = block_color

                c = block.c

                if c == 0:
                    c = 32
                    
                if utf8:
                    c = unichr(ansi.utf8[c])
                else:
                    c = chr(c)

                result.append(c)

            result.append('\n')

        return ''.join(result)

    def dump_png(self, outfile):
        fp = open(outfile, 'wb')
        end = self.dY
        colors = ansi.colors.items()
        colors.sort(lambda x,y: cmp(x[0],y[0]))
        colors = map(lambda x: x[1], colors)
        output = png.Writer(width=self.width*self.spacing
                            ,height=end*16
                            ,alpha=False # TODO: custom backgrounds for presence of no characters
                            ,background=ansi.colors[0]
                            ,compression=9) # 'cause why not?
        
        # the goal here is to fill in the blanks, so this is sort of like the dump-to-string algorithm
        result = list()
        image_data = list()

        for row in xrange(end):
            if not row in self.drawbuffer:
                self.drawbuffer[row] = dict()

            row_data = [list() for x in xrange(16)]

            for col in xrange(self.width):
                if not col in self.drawbuffer[row]:
                    #cp437.debug('PNG drawing null-block at {}, {}', col, row)
                    # TODO: swap this out for magical custom background one day
                    block = VT100Block(c=0
                                       ,fg=7
                                       ,bg=0)
                else:
                    block = self.drawbuffer[row][col]
                    #cp437.debug('PNG drawing {} at {}, {}', repr(block), col, row)
                    
                current_color = {'fg': block.fg, 'bg': block.bg}
                pixel_map = ansi.charset[block.c]

                #cp437.debug('PNG converting {} into pixels', repr(block))

                for y in xrange(16):
                    for x in xrange(self.spacing):
                        pix = pixel_map[y][x]
                        color = ('bg', 'fg')[pix]
                        pixel = self.palette.get(current_color[color])
                      
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
        cp437.debug_event('cursor shift event: {} by {}'.format({'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}[direction]
                                                          ,shift))

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

        self.screen.check_eol()

        cp437.debug_state('screen state is now: dX: {} / dY: {}', self.screen.dX, self.screen.dY)

class VT100Parser(object):
    EVENT_TABLE = None

    def __init__(self, *args, **kwargs):
        self.stream = None

        if not 'file' in kwargs and not 'filename' in kwargs and not 'stream' in kwargs:
            raise ValueError('no file, filename or stream present')

        if 'filename' in kwargs:
            self.filename = kwargs['filename']
            kwargs['file'] = open(self.filename, 'rb')
        else:
            self.filename = None
            
        if 'file' in kwargs:
            self.stream = kwargs['file'].read()

        if 'stream' in kwargs and not self.stream:
            self.stream = kwargs['stream']

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
            cp437.debug_event('found Pablo sauce')
            self.stream = self.stream[:-129]

        sauce = self.stream[-132:]

        if sauce[:9] == '\x1a\x00\x00\x00SAUCE':
            cp437.debug_event('found Pablo sauce (variant)')
            self.stream = self.stream[:-132]

        # no idea what this is but okay
        comnt = self.stream[-201:]

        if comnt[:9] == '\x1a\x00\x00\x00COMNT':
            cp437.debug_event('found COMNT block')
            self.stream = self.stream[:-201]

        states = ['print', 'esc', 'bracket', 'paren', 'pound', 'numeric', 'alpha', 'alnum']

        while tape_index < len(self.stream):
            c = self.stream[tape_index]

            cp437.debug_state('tape index: {} / state: {} / byte: {}'.format(tape_index
                                                                       ,states[state]
                                                                       ,ord(c)))

            if state == print_state:
                tape_index += 1

                if c == '\x1B':
                    cp437.debug_state('found vt100 escape')
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
                    '[7h': UnknownEvent,
                    '[20h': UnknownEvent,
                    '[?1h': UnknownEvent,
                    '[?3h': UnknownEvent,
                    '[?33h': UnknownEvent,
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
                        cp437.debug_state('found sequence: {}'.format(sliced))

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

                cp437.debug_state('control codes: {} / command: {}', numerics, c)

                if c == 'm':
                    # do the things
                    # TODO: convert these into events
                    for n in numerics:
                        if n >= 90 and n <= 97 or n >= 100 and n <= 107:
                            cp437.debug_event('screen brightness triggered (high value)')
                            screen.bright = True
                            n -= 60

                        if n == 0:
                            cp437.debug_event('screen attributes reset')
                            screen.reset_attributes()
                        elif n == 1:
                            cp437.debug_event('screen brightness triggered')
                            screen.bright = True
                        elif n == 2:
                            cp437.debug_event('screen brightness removed')
                            screen.bright = False
                        elif n == 4:
                            cp437.debug_event('underscore triggered')
                            screen.underscore = True
                        elif n == 5:
                            cp437.debug_event('blink triggered')
                            screen.blink = False
                        elif n == 7:
                            cp437.debug_event('screen reversal triggered')
                            screen.reverse = True
                        elif n == 8:
                            cp437.debug_event('hidden blocks triggered')
                            screen.hidden = True
                        elif n >= 30 and n <= 37:
                            cp437.debug_event('foreground: {}',n-30)
                            screen.fg = ansi.vga[n]
                        elif n >= 40 and n <= 47:
                            cp437.debug_event('background: {}',n-40)
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
                    cp437.debug_state('found terminator: {} (numerics: {})\n', c, numerics)
                    event = self.get_event(UnknownEvent, screen)
                    event()
            else:
                event = self.get_event(UnknownEvent, screen)
                event()
                state = print_state
