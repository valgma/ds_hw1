#! /usr/bin/env python
from socket import socket, AF_INET, SOCK_STREAM
from socket import error as soc_error
from time import sleep
from utils import make_logger,  pad_left, pad_right
from protocol import INS_CHAR, IND_SIZE, BLOCK_LINE, UNBLOCK_LINE, GET_LINE, INIT_TXT, GET_FILE, retr_msg, send_ok, send_nofile
import protocol
from threading import Thread, Event, Lock
import os

from filemanager import *
from clienthandler import *
from wordsmith import *

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
        self.fm = FileManager(self.stopFlag,TEXT_FOLDER)
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
                    send_ok(client_socket)
                    c = ClientHandler(client_socket,source,ws)
                    self.handlers.append(c)
                    c.handle()
                else:
                    send_nofile(client_socket)
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
            return fname[1 + 2*IND_SIZE :]
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

serv = Server(("127.0.0.1",7777))
