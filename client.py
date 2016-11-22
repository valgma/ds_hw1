#! /usr/bin/env python
import Tkinter as tk

from socket import socket, AF_INET, SOCK_STREAM, SHUT_WR, SHUT_RD
from socket import error as soc_error
from threading import Thread

from utils import make_logger
from protocol import IND_SIZE, INS_CHAR, BLOCK_LINE, UNBLOCK_LINE, GET_LINE, INIT_TXT, get_filename, NO_FILE, RSP_OK
import protocol
from sys import argv

LOG = make_logger()

class Application(tk.Frame):
    sock = None
    text = None

    def __init__(self,server,master=None):
        tk.Frame.__init__(self,master)
        self.grid()
        self.createWidgets()
        self.connect(server)
        self.bindKeys()
        self.req_file(argv[1])
        self.retrieve_initial_text()

        self.resp_handler = ClientRespHandler(self.text, self.sock)
        self.resp_handler.setDaemon(True) # kill it when app closed
        self.resp_handler.start()

    def bindKeys(self):
        self.text.bind("<Key>",self.key_press)
        self.text.bind("<Return>", self.enter_press)
        self.text.bind("<BackSpace>", self.bs_press)
        self.text.bind("<Delete>", self.del_press)
        self.pack()

    def createWidgets(self):
        self.quitButton = tk.Button(self, text="Quit", command=self.quit)
        self.quitButton.grid()

        self.text = tk.Text(self)
        self.text.tag_config("blocked", foreground="#ff0000", background="#000000")
        self.text.insert("0.0","Retrieving content from server..")

        self.text.config(bg="#d6d8d8",state=tk.DISABLED)

        self.text.grid()

    def key_press(self,event):
        row, col =  self.text.index(tk.INSERT).split(".")
        try:
            protocol.send_char(self.sock, row, col, event.char[0])
        except:
            return

    def enter_press(self,event):
        row, col =  self.text.index(tk.INSERT).split(".")
        print "ENTER at %s.%s" % (row, col)
        try:
            protocol.send_char(self.sock,row,col,'enter')
        except:
            return

    def bs_press(self,event):
        row, col =  self.text.index(tk.INSERT).split(".")
        print "BACKSPACE at %s.%s" % (row, col)
        try:
            if row != '1' or col != '0':
                protocol.send_char(self.sock,row,col,'backspace')
        except:
            return

    def del_press(self,event):
        row, col =  self.text.index(tk.INSERT+'+1c').split(".")
        print "DEL at %s.%s" % (row, col)
        try:
            if (row+'.'+col) != self.text.index(tk.END):
                protocol.send_char(self.sock,row,col,'backspace')
        except:
            return

    def retrieve_initial_text(self):
        protocol.ask_initial_text(self.sock)
        message = protocol.retr_msg(self.sock)
        identifier, row, col, txt = protocol.parse_msg(message)
        self.text.config(state=tk.NORMAL, bg="white")
        self.text.delete(1.0, tk.END)
        self.text.insert(0.0, txt)
        return

    def connect(self, server):
        LOG.info("Connecting to %s." % str(server))
        try:
            self.sock = socket(AF_INET,SOCK_STREAM)
            self.sock.connect(server)
        except:
            LOG.error("No connection could be made to %s." % str(server))
            return

    def disconnect(self):
        try:
            self.sock.fileno()
        except:
            return
        LOG.info("Disconnected from server.")
        self.sock.close()

    def req_file(self,filename):
        protocol.get_filename(self.sock,filename)
        rsp = protocol.retr_msg(self.sock)
        if rsp.startswith(RSP_OK):
            LOG.info("Server found the file!")
        elif rsp.startswith(NO_FILE):
            LOG.info("Server has no such file: %s" % filename)
        else:
            LOG.ERROR("Server responded weird to the filename request: %s" % rsp)


class ClientRespHandler(Thread):
    text = None
    socket = None

    def __init__(self, text, socket):
        super(ClientRespHandler, self).__init__()
        self.text = text
        self.socket = socket
        print "Started new listener"

    def run(self):
        while True:
            msg = protocol.retr_msg(self.socket)
            self.parse_and_handle_message(msg)

    def parse_and_handle_message(self, message):
        identifier, row, col, txt = protocol.parse_msg(message)

        if identifier == INS_CHAR:
            if txt.startswith('backspace'):
                if col > 0:
                    self.text.delete('%d.%d' % (row, col-1))
                elif row > 1:
                    self.text.delete('%d.%s' % (row-1, tk.END))
                return
            if txt.startswith('enter'):
                char = '\n'
            else:
                char = txt[0]
            print "received char %s in %s:%s" % (char,str(row),str(col))
            self.text.insert(str(row)+'.'+str(col), char)
        elif identifier == BLOCK_LINE or identifier == UNBLOCK_LINE:
            blocking = identifier == BLOCK_LINE
            self.toggle_block(row, blocking)
            # ask from server new line
            if not blocking:
                protocol.ask_line(self.socket, row)
        elif identifier == GET_LINE:
            self.text.delete('%d.0' % row, '%d.end' % row)
            self.text.insert('%d.0' % row, txt)
        else:
            print "unexpected!"
            print "msg: " + message

    def toggle_block(self,lineno,blocking):
        line_begin = "%d.0" %lineno
        line_end = "%d.0" % (lineno+1)
        if blocking:
            self.text.tag_add("blocked",line_begin,line_end)
        else:
            self.text.tag_remove("blocked",line_begin, line_end)



server = ("127.0.0.1", 7777)
app = Application(server)
app.master.title("Collaborative text editor")
app.mainloop()
app.disconnect()
