#! /usr/bin/env python
import Tkinter as tk

from socket import socket, AF_INET, SOCK_STREAM, SHUT_WR, SHUT_RD
from socket import error as soc_error
from threading import Thread

from utils import make_logger
from protocol import *
import protocol
from sys import argv

LOG = make_logger()
class InitialDialog:
    def __init__(self,parent,flist):
        self.parent = parent
        top = self.top = tk.Toplevel(parent)

        self.namelabel = tk.Entry(top)
        self.passwordlabel = tk.Entry(top,show="*")

        self.namelabel.insert(0,"Insert your username")
        self.passwordlabel.insert(0,"password")

        self.namelabel.pack(padx=5)
        self.passwordlabel.pack(padx=5)

        self.listbox = tk.Listbox(top)
        self.listbox.pack()
        for item in flist:
            self.listbox.insert(tk.END, item)

        self.filelabel = tk.Entry(top)
        self.filelabel.pack(padx=5)
        self.filelabel.insert(0,"Insert new file name")

        self.newfile = tk.BooleanVar()
        self.c = tk.Checkbutton(top, text="New file", variable=self.newfile)
        self.c.pack()

        b = tk.Button(top,text="Submit", command=self.submit)
        b.pack(pady=5)

    def submit(self):
        if self.newfile.get():
            self.parent.filename = self.filelabel.get()
        else:
            self.parent.filename = self.listbox.get(self.listbox.curselection()[0])
        self.parent.password = self.passwordlabel.get()
        self.parent.username = self.namelabel.get()
        self.top.destroy()

class Application(tk.Frame):
    sock = None
    text = None

    def __init__(self,server,master=None):
        tk.Frame.__init__(self,master)
        self.grid()
        self.createWidgets()
        self.connect(server)
        self.bindKeys()
        self.filename = ""
        self.username = ""
        self.password = ""
        flist = self.recv_file_list()
        r = InitialDialog(self,flist)
        self.wait_window(r.top)
        print self.filename

        self.req_file(self.filename)
        self.retrieve_initial_text()

        self.resp_handler = ClientRespHandler(self.text, self.sock)
        self.resp_handler.setDaemon(True) # kill it when app closed
        self.resp_handler.start()

    def recv_file_list(self):
        filecount_msg = protocol.retr_msg(self.sock)
        offset = 1 + 2*IND_SIZE
        files = []
        #TODO: Notify user when file list not retrieved
        if filecount_msg.startswith(FILE_LIST):
            filecount = int(filecount_msg[offset:])
            for _ in range(filecount):
                file_msg = protocol.retr_msg(self.sock)
                if file_msg.startswith(FILE_ENTRY):
                    fname = file_msg[offset:]
                    files.append(fname)
        return files

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
            LOG.error("Server responded weird to the filename request: %s" % rsp)


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
