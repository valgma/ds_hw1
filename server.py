#! /usr/bin/env python
from socket import socket, AF_INET, SOCK_STREAM
from socket import error as soc_error
from time import sleep
from utils import make_logger,  pad_left, pad_right
from protocol import *
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
    fm = None
    stopFlag = None
    authors = {}

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
                c = ClientHandler(client_socket,source,self.fm)
                c.setDaemon(True)
                c.start()
                #self.process_client(client_socket,source)
        except KeyboardInterrupt:
            LOG.info("Received CTRL-C, shutting down..")
            self.disconnect()
        finally:
            LOG.debug("Kicking everyone out.")
            map(lambda x: x.kick_client_out, self.fm.get_all_clients())
            self.stopFlag.set()
            self.fm.store_ownership_dict()
            self.disconnect()
            LOG.debug("Trying to join threads.")
            #map(lambda x: x.join(), self.handlers)




    def disconnect(self):
        self.sock.close()








serv = Server(("127.0.0.1",7777))
