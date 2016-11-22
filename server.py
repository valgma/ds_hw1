#! /usr/bin/env python
from socket import socket, AF_INET, SOCK_STREAM
from socket import error as soc_error
from time import sleep
from utils import make_logger,  pad_left, pad_right
from protocol import INS_CHAR, IND_SIZE, BLOCK_LINE, UNBLOCK_LINE, GET_LINE, INIT_TXT, GET_FILE, retr_msg, NO_FILE, RSP_OK, send_rspcode
import protocol
from threading import Thread, Event, Lock
import select
import os
LOG = make_logger()

TEXT_FOLDER = 'text'
class Server:
    sock = socket(AF_INET,SOCK_STREAM)
    wordsmiths = {}
    handlers = []
    fm = None
    stopFlag = None

    def __init__(self,server):
        self.stopFlag = Event()
        self.fm = FileManager(self.stopFlag)
        self.fm.start()
        try:
            LOG.info("Trying to initialize server socet.")
            self.sock.bind(server)
            self.sock.listen(10)
            LOG.info("Initialized server socket.")
        except:
            LOG.error("Error initializing server socket.")
        self.listen()


    def listen(self):
        try:
            while 1:
                LOG.info("Waiting for clients.")
                client_socket,source = self.sock.accept()
                LOG.debug("New client connected from %s:%d" % source)
                fname = self.ask_filename(client_socket)
                ws = None
                if fname:
                    ws = self.load_wordsmith(fname)
                if ws:
                    send_rspcode(client_socket,RSP_OK)
                    c = ClientHandler(client_socket,source,ws)
                    self.handlers.append(c)
                    c.handle()
                else:
                    send_rspcode(client_socket,NO_FILE)
                    client_socket.close()
                sleep(1)

        except KeyboardInterrupt:
            LOG.info("Received CTRL-C, shutting down..")
            self.disconnect()
        finally:
            self.stopFlag.set()
            self.disconnect()
            LOG.debug("Telling the threads to kill themselves.")
            map(lambda x: x.stop(), self.handlers)
            LOG.debug("Trying to join threads.")
            map(lambda x: x.join(), self.handlers)

    def ask_filename(self,socket):
        fname = retr_msg(socket)
        if fname.startswith(GET_FILE):
            return fname[1:]
        else:
            LOG.error("Expected to get a filename request, instead got: %s",fname)
            return None

    def disconnect(self):
        self.sock.close()

    def load_wordsmith(self,fname):
        if fname in self.wordsmiths.keys():
            return self.wordsmiths[fname]
        try:
            pth = os.path.join(TEXT_FOLDER,fname)
            f = open(pth,'r')
            content = f.read()
            f.close()
            ws = Wordsmith(fname)
            self.fm.addSmith(ws)
            ws.set_content(content)
            #ws.start() #TODO: we only use this for debugging..
            self.wordsmiths[fname] = ws
            return ws
        except IOError:
            return None


class FileManager(Thread):
    smiths = []
    #http://stackoverflow.com/questions/12435211/python-threading-timer-repeat-function-every-n-seconds#12435256
    def __init__(self,event):
        Thread.__init__(self)
        self.stopped = event

    def run(self):
        while not self.stopped.wait(60):
            for smith in self.smiths:
                pth = os.path.join(TEXT_FOLDER,smith.filename)
                f = open(pth,"w")
                f.write(smith.content())
                f.close()

    def addSmith(self,ws):
        self.smiths.append(ws)

class LineLockHolder(Thread):
    def __init__(self,lock,auth,nr,ws):
        Thread.__init__(self)
        self.stopped = Event()
        self.linelock = lock
        self.author = auth
        self.lineno = nr
        self.wordsmith = ws

    def run(self):
        while 1:
            sleep(4)
            if not self.stopped.is_set():
                LOG.debug("Line lock released on %d." % (self.lineno + 1))
                # msg = self.wordsmith.create_block_msg(str(self.lineno+1),False)
                msg = protocol.assemble_msg(UNBLOCK_LINE, self.lineno + 1, 0, 0)
                self.wordsmith.notify_all_clients(self.author,msg)
                self.linelock.release()
                break
            else:
                self.stopped.clear()

    def poke(self):
        self.stopped.set()


class Stoppable(Thread):
    shutdown = False
    def stop(self):
        self.shutdown = True

class Wordsmith(Stoppable):
    def __init__(self,name):
        Thread.__init__(self)
        self.filename = name
        self.subscribers = []
        self.text = [[[''],Lock(),None]]


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
                self.text[row][0] = self.text[row][0][:col]

                new_lock = Lock()
                old_row_timer = LineLockHolder(lock, src, row, self)
                new_timer = LineLockHolder(new_lock, src, row + 1, self)
                self.text[row][2] = old_row_timer

                new_timer.start()
                old_row_timer.start()
                new_lock.acquire(False)

                self.text.insert(row + 1, [new_row_content,new_lock,new_timer])
                self.inc_timer_indices(row + 2)

                return [enter_msg, blockmsg1, blockmsg2]
            elif timer.author == src:
                self.text[row][0] = self.text[row][0][:col]

                timer.poke()
                new_lock = Lock()
                new_timer = LineLockHolder(new_lock, src, row + 1, self)
                new_timer.start()
                new_lock.acquire(False)

                self.text.insert(row + 1, [new_row_content,new_lock,new_timer])
                self.inc_timer_indices(row + 2)

                return [enter_msg, blockmsg1, blockmsg2]

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
                        self.text.pop(row)
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        self.text[row - 1][2] = LineLockHolder(lock, src, row - 1, self)
                        self.text[row - 1][2].start()
                    elif prev_timer.author == src:
                        LOG.debug("Line %s lock owner is editing" % str(row))
                        self.text.pop(row)
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        prev_timer.poke()
                    else:
                        # should send notice to author that it couldn't do it
                        # basically author needs to insert enter
                        msg_newline = protocol.assemble_msg(INS_CHAR, row, len(prev_line), 'enter')
                        src.send_update(msg_newline)
                        # also send others notice that its locked
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
                        self.text.pop(row)
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        self.text[row - 1][2] = LineLockHolder(lock, src, row - 1, self)
                        self.text[row - 1][2].start()
                    elif prev_timer.author == src:
                        LOG.debug("Line %s lock owner is editing" % str(row))
                        self.text.pop(row)
                        self.text[row - 1][0].extend(line)
                        self.dec_timer_indices(row)

                        prev_timer.poke()
                    else:
                        # should send notice to author that it couldn't do it
                        # basically author needs to insert enter
                        msg_newline = protocol.assemble_msg(INS_CHAR, row, len(prev_line), 'enter')
                        src.send_update(msg_newline)
                        # also send others notice that its locked
                        return [blockmsg]

                    # now needs to send blockmsg about previous row
                    blockmsg_prev = protocol.assemble_msg(BLOCK_LINE, row, 0, 0)
                    return [bs_msg, blockmsg_prev]
        else:
            char = txt[0]
            if lock.acquire(False):
                LOG.debug("Lock on line %s was open, now grabbed" % str(row+1))
                self.text[row][2] = LineLockHolder(lock, src, row, self)
                self.text[row][0].insert(col,char)
                self.text[row][2].start()
            elif timer.author == src:
                LOG.debug("Line %s lock owner is editing" % str(row+1))
                timer.poke()
                self.text[row][0].insert(col,char)

            char_msg = protocol.assemble_msg(INS_CHAR, row + 1, col, char)
            blockmsg = protocol.assemble_msg(BLOCK_LINE, row + 1, 0, 0)
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



    def run(self):
        self.displayText()

    def displayText(self):
        while not self.shutdown:
            print "-----"
            print self.content()
            print "//Subscribers:"
            print len(self.subscribers)
            print "-----"

            sleep(4)

    def content(self):
        rows = map(lambda x: x[0],self.text)
        return "\n".join(map(lambda x : "".join(x),rows))

    def get_line(self, lineno):
        return ''.join(self.text[lineno-1][0])

    def notify_all_clients(self, author, msg):
        for handler in self.subscribers:
            if handler != author:
                handler.send_update(msg)


class ClientHandler(Stoppable):
    shutdown = False
    client_socket = None
    client_addr = None
    wordsmith = None

    def __init__(self,cs,ca,ws):
        Thread.__init__(self)
        self.client_socket = cs
        self.client_addr = ca
        self.wordsmith = ws
        #self.send_initmsg()
        self.wordsmith.subscribers.append(self)

    def send_update(self, msg):
        protocol.forward_msg(self.client_socket, msg)

    def run(self):
        self.__handle()

    def handle(self):
        self.start()

    def __handle(self):
        client_shutdown = False
        try:
            while 1:
                read_sockets, write_sockets, error_sockets = \
                        select.select([self.client_socket] , [], [])

                #TODO: Include force closes from server side.
                for socket in read_sockets:
                    msg = protocol.retr_msg(socket)
                    if msg:
                        identifier, row, col, txt = protocol.parse_msg(msg)

                        if identifier == INS_CHAR:
                            for resp_msg in self.wordsmith.in_char(row - 1, col, txt, self):
                                self.wordsmith.notify_all_clients(self, resp_msg)  # send msg to others
                        elif identifier == GET_LINE:
                            line_content = self.wordsmith.get_line(row)
                            protocol.send_line(self.client_socket, row, line_content)
                        elif identifier == INIT_TXT:
                            text = self.wordsmith.content()
                            protocol.send_initial_text(self.client_socket, text)
                    else:
                        client_shutdown = True
                if self.shutdown or client_shutdown:
                    break
        finally:
            self.disconnect()


    def disconnect(self):
        self.wordsmith.subscribers.remove(self)
        self.client_socket.close()
        LOG.debug("Terminating client %s:%d" % self.client_addr)

    def stop(self):
        self.shutdown = True


serv = Server(("127.0.0.1",7777))
