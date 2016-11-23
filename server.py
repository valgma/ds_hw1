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
    handlers = []
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
                self.process_client(client_socket,source)
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
        user_info = []
        fields = [("filename",USER_FILENAME),("username",USER_NAME),("password",USER_PW)]
        for description,tag in fields:
            msg = retr_msg(socket)
            if msg.startswith(tag):
                field_val = msg[1 + 2*IND_SIZE :]
                LOG.debug("Retrieved value %s for field %s" % (field_val, description))
                user_info.append(field_val)
            else:
                LOG.error("Expected to get a %s request, instead got: %s",(description,fname_msg))
                return (None,None,None)
        return tuple(user_info)

    def disconnect(self):
        self.sock.close()

    def send_filelist(self,client):
        avail_files = self.fm.get_all_titles()
        protocol.send_msg(client,FILE_LIST,0,0,len(avail_files))
        for f in avail_files:
            protocol.send_msg(client,FILE_ENTRY,0,0,f)

    def process_client(self,client,source):
        self.send_filelist(client)
        fname,user_name,password = self.ask_filename(client)
        ws = None
        if fname and user_name and password:
            ws,permission = self.fm.load_wordsmith(fname,user_name,password)
        protocol.send_permissionbit(client,permission)
        if ws:
            c = ClientHandler(client,source,ws)
            self.handlers.append(c)
            c.handle()
        else:
            client.close()







serv = Server(("127.0.0.1",7777))
