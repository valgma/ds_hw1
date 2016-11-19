#! /usr/bin/env python
from socket import socket, AF_INET, SOCK_STREAM
from socket import error as soc_error
from time import sleep
from common import make_logger, MESSAGE_SIZE, INS_CHAR, IND_SIZE, pad_left, pad_right
from threading import Thread, Event
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

class Stoppable(Thread):
    shutdown = False
    def stop(self):
        self.shutdown = True

class Wordsmith(Stoppable):
    filename = "first.txt"
    text = [['']]
    handlers = []

    def __init__(self):
        Thread.__init__(self)

    def setChar(self,row,col,char):
        try:
            self.text[row][col] = char
        except IndexError:
            if col == len(self.text[row]):
                self.text[row].append(char)

    def in_char(self,row,col,txt):
        if txt.startswith('enter'):
            new_row = self.text[row][col-1:]
            self.text.insert(row + 1, new_row)
        else:
            char = txt[0][0]
            self.text[row].insert(col,char)

    def setEnter(self, row, col):
        new_row = self.text[row][col:]
        self.text.insert(row + 1, new_row)

    def run(self):
        self.displayText()

    def displayText(self):
        while not self.shutdown:
            print "-----"
            print self.content()
            print "-----"
            sleep(4)

    def content(self):
        return "\n".join(map(lambda x : "".join(x),self.text))

    def notify_all_clients(self, author, msg):
        for handler in self.handlers:
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
        print "sent: " + msg
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
                        self.wordsmith.in_char(row-1,column,txt)
                        self.wordsmith.notify_all_clients(self, msg)  # send msg to others
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
