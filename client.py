#! /usr/bin/env python
import Tkinter as tk

from socket import socket, AF_INET, SOCK_STREAM, SHUT_WR, SHUT_RD
from socket import error as soc_error
from threading import Thread

from common import make_logger, INS_CHAR, IND_SIZE, BLOCK_LINE, UNBLOCK_LINE, GET_LINE
from client_protocol import send_char, retr_text, ask_line
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
        self.retrieveText()

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
        print "MUU key"
        ind =  self.text.index(tk.INSERT).split(".")
        row = ind[0]
        col = ind[1]
        try:
            in_char = event.char[0]
            send_char(self.sock,row,col,event.char[0])
        except:
            return

    def enter_press(self,event):
        print "ENTERERERER"
        ind =  self.text.index(tk.INSERT).split(".")
        row = ind[0]
        col = ind[1]
        try:
            send_char(self.sock,row,col,'enter')
        except:
            return

    def bs_press(self,event):
        ind =  self.text.index(tk.INSERT).split(".")
        row = ind[0]
        col = ind[1]
        print "BACKSPACE at %s.%s" % (row, col)
        try:
            if row != '1' or col != '0':
                send_char(self.sock,row,col,'backspace')
        except:
            return

    def del_press(self,event):
        ind =  self.text.index(tk.INSERT+'+1c').split(".")
        row = ind[0]
        col = ind[1]
        print "DEL at %s.%s" % (row, col)
        try:
            if (row+'.'+col) != self.text.index(tk.END):
                send_char(self.sock,row,col,'backspace')
        except:
            return

    def retrieveText(self):
        text = retr_text(self.sock)
        self.text.config(state=tk.NORMAL,bg="white")
        self.text.delete(1.0,tk.END)
        self.text.insert(0.0,text)
        return

    def connect(self,server):
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
            msg = retr_text(self.socket)
            self.parse_message(msg)

    def parse_message(self, message):
        identifier = message[0]
        print "message:", message
        if identifier == INS_CHAR:
            message = message[1:]
            row = int(message[:IND_SIZE])
            col = int(message[IND_SIZE:2*IND_SIZE])
            txt = message[2*IND_SIZE:]
            if txt.startswith('backspace'):
                if col > 0:
                    self.text.delete('%d.%d' % (row, col-1))
                elif row > 1:
                    self.text.delete('%d.%s' % (row-1, tk.END))
                return
            if txt.startswith('enter'):
                char = '\n'
            else:
                char = txt[0][0]
            print "received char %s in %s:%s" % (char,str(row),str(col))
            self.text.insert(str(row)+'.'+str(col), char)
        elif identifier == BLOCK_LINE or identifier == UNBLOCK_LINE:
            message = message[1:]
            lineno = str(int(message))
            blocking = identifier == BLOCK_LINE
            self.toggle_block(lineno,blocking)
            # ask from server new line
            if not blocking:
                ask_line(self.socket, lineno)
        elif identifier == GET_LINE:
            message = message[1:]
            row = int(message[:IND_SIZE])
            txt = message[IND_SIZE:]
            self.text.delete('%d.0' % row, '%d.end' % row)
            self.text.insert('%d.0' % row, txt)
        else:
            print "unexpected!"
            print "msg: " + message

    def toggle_block(self,lineno,blocking):
        line_begin = lineno+".0"
        line_end = lineno+".end"
        if blocking:
            self.text.tag_add("blocked",line_begin,line_end)
        else:
            self.text.tag_remove("blocked",line_begin, line_end)



server = ("127.0.0.1", 7777)
app = Application(server)
app.master.title("Collaborative text editor")
app.mainloop()
app.disconnect()
