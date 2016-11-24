from threading import Lock
from linelockholder import *
from utils import make_logger
import protocol
from protocol import INS_CHAR, BLOCK_LINE

LOG = make_logger()

class Wordsmith():
    def __init__(self,name,filemanager):
        self.filename = name
        self.subscribers = []
        self.text = [[[''],Lock(),None]]
        self.fm = filemanager


    def set_content(self,content):
        txt = []
        lines = content.split('\n')
        for line in lines:
            l = [[],Lock(),None]
            for char in line:
                l[0].append(char)
            txt.append(l)
        self.text = txt


    def in_char(self,row,col,txt,src):
        line = self.text[row][0]
        lock = self.text[row][1]
        timer = self.text[row][2]

        if txt.startswith('enter'):
            # needs to return enter and 2 block messages
            enter_msg = protocol.assemble_msg(INS_CHAR, row + 1, col, 'enter')
            blockmsg1 = protocol.assemble_msg(BLOCK_LINE, row + 1, 0, 0)
            blockmsg2 = protocol.assemble_msg(BLOCK_LINE, row + 2, 0, 0)

            new_row_content = self.text[row][0][col:]
            if lock.acquire(False):
                LOG.debug("Lock on line %s was open, now grabbed" % str(row+1))
                self.text[row][0] = self.text[row][0][:col]

                new_lock = Lock()
                old_row_timer = LineLockHolder(lock, src, row, self)
                new_timer = LineLockHolder(new_lock, src, row + 1, self)
                self.text[row][2] = old_row_timer

                new_timer.start()
                old_row_timer.start()
                new_lock.acquire(False)
                LOG.debug("Created new lock on line %s, now grabbed" % str(row+2))

                self.text.insert(row + 1, [new_row_content,new_lock,new_timer])
                self.inc_timer_indices(row + 2)

                return [enter_msg, blockmsg1, blockmsg2]
            elif timer.author == src:
                LOG.debug("Line %s lock owner is editing" % str(row+1))
                self.text[row][0] = self.text[row][0][:col]

                timer.poke()
                new_lock = Lock()
                new_timer = LineLockHolder(new_lock, src, row + 1, self)
                new_timer.start()
                new_lock.acquire(False)
                LOG.debug("Created new lock on line %s, now grabbed" % str(row+2))

                self.text.insert(row + 1, [new_row_content,new_lock,new_timer])
                self.inc_timer_indices(row + 2)

                return [enter_msg, blockmsg1, blockmsg2]
            else:  # have to let author know that this enter wasn't accepted
                msg_backspace = protocol.assemble_msg(INS_CHAR, row + 2, 0, 'backspace')
                src.send_update(msg_backspace)

        elif txt.startswith('backspace'):
            bs_msg = protocol.assemble_msg(INS_CHAR, row + 1, col, 'backspace')
            blockmsg = protocol.assemble_msg(BLOCK_LINE, row + 1, 0, 0)

            if lock.acquire(False):
                LOG.debug("Lock on line %s was open, now grabbed" % str(row+1))

                if col > 0:
                    line.pop(col - 1)
                    self.text[row][2] = LineLockHolder(lock, src, row, self)
                    self.text[row][2].start()

                    return [bs_msg, blockmsg]
                elif row > 0:
                    # need to check if we can modify prev line
                    prev_line, prev_lock, prev_timer = self.text[row - 1]

                    if prev_lock.acquire(False):
                        LOG.debug("Lock on line %s was open, now grabbed" % str(row))
                        del self.text[row]
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        self.text[row - 1][2] = LineLockHolder(prev_lock, src, row - 1, self)
                        self.text[row - 1][2].start()
                    elif prev_timer.author == src:
                        LOG.debug("Line %s lock owner is editing" % str(row))
                        del self.text[row]
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        prev_timer.poke()
                    else:
                        # should send notice to author that it couldn't do it
                        # basically author needs to insert enter
                        msg_newline = protocol.assemble_msg(INS_CHAR, row, len(prev_line), 'enter')
                        src.send_update(msg_newline)
                        # also send others notice that its locked
                        self.text[row][2] = LineLockHolder(lock, src, row, self)
                        self.text[row][2].start()
                        return [blockmsg]

                    # now needs to send blockmsg about previous row
                    blockmsg_prev = protocol.assemble_msg(BLOCK_LINE, row, 0, 0)
                    return [bs_msg, blockmsg_prev]
            elif timer.author == src:
                LOG.debug("Line %s lock owner is editing" % str(row+1))
                if col > 0:
                    line.pop(col - 1)
                    timer.poke()

                    return [bs_msg, blockmsg]
                elif row > 0:
                    # need to check if we can modify prev line
                    prev_line, prev_lock, prev_timer = self.text[row - 1]

                    if prev_lock.acquire(False):
                        LOG.debug("Lock on line %s was open, now grabbed" % str(row))
                        del self.text[row]
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        self.text[row - 1][2] = LineLockHolder(prev_lock, src, row - 1, self)
                        self.text[row - 1][2].start()
                    elif prev_timer.author == src:
                        LOG.debug("Line %s lock owner is editing" % str(row))
                        del self.text[row]
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        prev_timer.poke()
                    else:
                        # should send notice to author that it couldn't do it
                        # basically author needs to insert enter
                        msg_newline = protocol.assemble_msg(INS_CHAR, row, len(prev_line), 'enter')
                        src.send_update(msg_newline)
                        # also send others notice that its locked
                        timer.poke()
                        return [blockmsg]

                    # now needs to send blockmsg about previous row
                    blockmsg_prev = protocol.assemble_msg(BLOCK_LINE, row, 0, 0)
                    return [bs_msg, blockmsg_prev]
        else:
            char = txt[0]
            char_msg = protocol.assemble_msg(INS_CHAR, row + 1, col, char)
            blockmsg = protocol.assemble_msg(BLOCK_LINE, row + 1, 0, 0)

            if lock.acquire(False):
                LOG.debug("Lock on line %s was open, now grabbed" % str(row+1))
                self.text[row][2] = LineLockHolder(lock, src, row, self)
                self.text[row][0].insert(col,char)
                self.text[row][2].start()

                return [char_msg, blockmsg]
            elif timer.author == src:
                LOG.debug("Line %s lock owner is editing" % str(row+1))
                timer.poke()
                self.text[row][0].insert(col,char)

                return [char_msg, blockmsg]

        return []

    def inc_timer_indices(self,n):
        for i in range(n,len(self.text)):
            timer = self.text[i][2]
            if timer:
                timer.lineno += 1

    def dec_timer_indices(self, n):
        for i in range(n, len(self.text)):
            timer = self.text[i][2]
            if timer:
                timer.lineno -= 1

    def content(self):
        rows = map(lambda x: x[0],self.text)
        return "\n".join(map(lambda x : "".join(x),rows))

    def get_line(self, lineno):
        if 0 <= lineno < len(self.text):
            return ''.join(self.text[lineno][0])
        return ''

    def notify_all_clients(self, author, msg):
        for handler in self.subscribers:
            if handler != author:
                handler.send_update(msg)

    def remove_editor(self,username):
        for handler in self.subscribers[:]:
            if handler.username == username:
                #TODO: close connection
                handler.kick_client_out()
        self.fm.remove_editor(self.filename,username)

    def add_editor(self,username,password):
        self.fm.add_editor(self.filename,username,password)
