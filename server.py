#! /usr/bin/env python
from socket import socket, AF_INET, SOCK_STREAM
from socket import error as soc_error
from time import sleep
from common import make_logger, MESSAGE_SIZE, INS_CHAR, IND_SIZE, pad_left, pad_right, BLOCK_LINE, UNBLOCK_LINE
from threading import Thread, Event, Lock
import select
import os
LOG = make_logger()

class Server:
    sock = socket(AF_INET,SOCK_STREAM)
    ws = None
    handlers = []
    fm = None
    stopFlag = None

    def __init__(self,server):
        self.ws = Wordsmith()
        self.ws.start()
        self.stopFlag = Event()
        self.fm = FileManager(self.stopFlag)
        self.fm.addSmith(self.ws)
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
                c = ClientHandler(client_socket,source,self.ws)
                self.handlers.append(c)
                c.handle()
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
            self.ws.stop()
            self.ws.join()

    def disconnect(self):
        self.sock.close()

class FileManager(Thread):
    smiths = []
    #http://stackoverflow.com/questions/12435211/python-threading-timer-repeat-function-every-n-seconds#12435256
    def __init__(self,event):
        Thread.__init__(self)
        self.stopped = event

    def run(self):
        while not self.stopped.wait(10):
            for smith in self.smiths:
                pth = os.path.join("text",smith.filename)
                f = open(pth,"w")
                f.write(smith.content())
                f.close()

    def addSmith(self,ws):
        self.smiths.append(ws)

class TimedLock(Thread):
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
                LOG.debug("Line lock released on %d." % self.lineno)
                msg = self.wordsmith.create_block_msg(str(self.lineno+1),False)
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
    filename = "first.txt"
    text = [[[''],Lock(),None]]
    handlers = []

    def __init__(self):
        Thread.__init__(self)

    def in_char(self,row,col,txt,src):
        line = self.text[row][0]
        lock = self.text[row][1]
        timer = self.text[row][2]

        if txt.startswith('enter'):
            new_row_content = self.text[row][0][col:]
            if lock.acquire(False):
                self.text[row][0] = self.text[row][0][:col]

                new_lock = Lock()
                old_row_timer = TimedLock(lock,src,row,self)
                new_timer = TimedLock(new_lock,src,row + 1,self)
                self.text[row][2] = old_row_timer

                new_timer.start()
                old_row_timer.start()
                new_lock.acquire(False)

                self.text.insert(row + 1, [new_row_content,new_lock,new_timer])
                self.inc_timer_indices(row + 2)

                return True
            elif timer.author == src:
                self.text[row][0] = self.text[row][0][:col]

                timer.poke()
                new_lock = Lock()
                new_timer = TimedLock(new_lock,src,row + 1,self)
                new_timer.start()
                new_lock.acquire(False)

                self.text.insert(row + 1, [new_row_content,new_lock,new_timer])
                self.inc_timer_indices(row + 2)

                return True
        else:
            char = txt[0][0]
            (line,lock,timer) = (self.text[row][0],self.text[row][1],self.text[row][2])
            if lock.acquire(False):
                LOG.debug("Lock on line %s was open, now grabbed" % str(row+1))
                self.text[row][2] = TimedLock(lock,src,row,self)
                self.text[row][0].insert(col,char)
                self.text[row][2].start()
                return True
            elif timer.author == src:
                LOG.debug("Line %s lock owner is editing" % str(row+1))
                timer.poke()
                self.text[row][0].insert(col,char)
                return True
        return False

    def inc_timer_indices(self,n):
        for i in range(n,len(self.text)):
            timer = self.text[i][2]
            if timer:
                timer.lineno += 1



    def run(self):
        self.displayText()

    def displayText(self):
        while not self.shutdown:
            print "-----"
            print self.content()
            print "-----"
            sleep(4)

    def content(self):
        rows = map(lambda x: x[0],self.text)
        return "\n".join(map(lambda x : "".join(x),rows))

    def notify_all_clients(self, author, msg):
        for handler in self.handlers:
            if handler != author:
                handler.send_update(msg)

    def create_block_msg(self,lineno,blocking):
        m = BLOCK_LINE if blocking else UNBLOCK_LINE
        m += pad_left(lineno,MESSAGE_SIZE-1)
        return m

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
        self.send_initmsg()
        self.wordsmith.handlers.append(self)

    def send_initmsg(self):
        LOG.info("Sending client current text")
        text = self.wordsmith.content()
        length = str(len(text))
        msg = pad_left(length,MESSAGE_SIZE) + text
        try:
            read_sockets, write_sockets, error_sockets = \
                        select.select([] , [self.client_socket], [])
            for socket in write_sockets:
                socket.sendall(msg)
                LOG.info("Successfully sent client the current text.")
        except soc_error as e:
            print "woops!"

    def send_update(self, msg):
        msg = pad_left(str(len(msg)) ,MESSAGE_SIZE) + msg
        #print "sent: " + msg
        self.client_socket.sendall(msg)

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
                    msgs = []
                    msg = socket.recv(MESSAGE_SIZE)
                    if msg:
                        (row,column,txt) = self.parse_message(msg)
                        blockmsg = self.wordsmith.create_block_msg(str(row),True)
                        if self.wordsmith.in_char(row-1,column,txt,self):
                            self.wordsmith.notify_all_clients(self, msg)  # send msg to others
                            self.wordsmith.notify_all_clients(self, blockmsg)
                    else:
                        client_shutdown = True
                if self.shutdown or client_shutdown:
                    break
        finally:
            self.disconnect()

    def parse_message(self,message):
        identifier = message[0]
        if identifier == INS_CHAR:
            message = message[1:]
            row = int(message[:IND_SIZE])
            column = int(message[IND_SIZE:2*IND_SIZE])
            return (row,column,message[2*IND_SIZE:])
        else:
            print "unexpected!"

    def disconnect(self):
        self.wordsmith.handlers.remove(self)
        self.client_socket.close()
        LOG.debug("Terminating client %s:%d" % self.client_addr)

    def stop(self):
        self.shutdown = True


serv = Server(("127.0.0.1",7777))
