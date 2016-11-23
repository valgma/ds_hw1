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

        self.listbox = tk.Listbox(top)
        for item in flist:
            self.listbox.insert(tk.END, item)

        self.filelabel = tk.Entry(top)
        self.filelabel.insert(0,"Insert new file name")

        self.newfile = tk.BooleanVar()
        self.c = tk.Checkbutton(top, text="New file", variable=self.newfile)

        b = tk.Button(top,text="Submit", command=self.submit)
        map(lambda x:x.pack(padx=5),[self.namelabel, self.passwordlabel, self.listbox, self.filelabel, self.c, b])

    def submit(self):
        if self.listbox.curselection() or self.newfile.get():
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
        self.pack()
        self.createWidgets()
        try:
            self.connect(server)
            self.bindKeys()
            self.filename = ""
            self.username = ""
            self.password = ""
            self.permissions = FILE_NOAUTH
            flist = self.recv_file_list()
            r = InitialDialog(self,flist)
            self.wait_window(r.top)
            self.send_identity(self.filename,self.username,self.password)
            self.init_board()
            self.target_editor = ""
            self.target_editor_password = ""
            self.target_remove = False

            if self.permissions != FILE_NOAUTH:
                self.file_label.config(text=self.filename)
                self.resp_handler = ClientRespHandler(self.text, self.sock, self)
                self.resp_handler.setDaemon(True) # kill it when app closed
                self.resp_handler.start()
        except soc_error:
            self.disconnect()
            exit(1)

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
        self.quitButton.pack(anchor=tk.N)

        self.file_label = tk.Label(self, text='')
        self.file_label.pack(anchor=tk.NW)

        # scrollbar
        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text = tk.Text(self, yscrollcommand=scrollbar.set)
        self.text.tag_config("blocked", background="thistle")
        self.text.insert("0.0","Retrieving content from server..")

        self.text.config(bg="#d6d8d8",state=tk.DISABLED)

        self.text.pack()
        scrollbar.config(command=self.text.yview)


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

    def init_board(self):
        print self.permissions
        if self.permissions == FILE_NOAUTH:
            no_auth_txt = "Authentication for file %s failed." % self.filename
            self.text.config(state=tk.NORMAL, bg="white")
            self.text.delete(1.0, tk.END)
            self.text.insert(0.0, no_auth_txt)
            self.text.config(bg="#d6d8d8",state=tk.DISABLED)
        else:
            protocol.ask_initial_text(self.sock)
            message = protocol.retr_msg(self.sock)
            identifier, row, col, txt = protocol.parse_msg(message)
            self.text.config(state=tk.NORMAL, bg="white")
            self.text.delete(1.0, tk.END)
            self.text.insert(0.0, txt)

        if self.permissions == FILE_OWNER:
            self.create_author_buttons()

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

    def send_identity(self,filename,username,password):
        protocol.send_user_info(self.sock,filename,username,password)
        rsp = protocol.retr_msg(self.sock)
        if rsp.startswith(FILE_OWNER):
            self.permissions = rsp[0]
            LOG.debug("Owner access granted on %s." % filename)
        elif rsp.startswith(FILE_EDITOR):
            self.permissions = rsp[0]
            LOG.debug("Editor access granted on %s." % filename)
        elif rsp.startswith(FILE_NOAUTH):
            self.permissions = rsp[0] #Don't want to do this outside of the if's in case it's garbage
            #I do a compare later if it's FILE_NOAUTH or not, so garbage would break that.
            LOG.debug("No access to file %s." % filename)
        else:
            LOG.error("Server responded weird to the client info transmission: %s" % rsp)

    def create_author_buttons(self):
        self.adjust_editors_button = tk.Button(self, text="Add/Remove Editor", command=self.adjust_editors)
        self.adjust_editors_button.pack()

    def adjust_editors(self):
        a = EditorDialog(self)
        self.wait_window(a.top)
        if self.target_remove:
            protocol.send_msg(self.sock,REM_USER,0,0,self.target_editor)
        else:
            protocol.send_msg(self.sock,ADD_USER_NAME,0,0,self.target_editor)
            protocol.send_msg(self.sock,ADD_USER_PW,0,0,self.target_editor_password)

class EditorDialog:
    def __init__(self,parent):
        self.parent = parent
        top = self.top = tk.Toplevel(parent)

        self.removeChoice = tk.BooleanVar()
        self.removeChoice.set(False)

        self.namelabel = tk.Entry(top)
        self.namelabel.insert(0,"Insert your username")

        self.passwordlabel = tk.Entry(top)
        self.passwordlabel.insert(0,"Insert editor password")

        b = tk.Button(top,text="Submit", command=self.submit)
        self.add = tk.Radiobutton(top, text="Add Editor", variable=self.removeChoice, value=False)
        self.remove = tk.Radiobutton(top, text="Remove Editor", variable=self.removeChoice, value=True)

        map(lambda x:x.pack(padx=5),[self.namelabel, self.passwordlabel, self.add, self.remove, b])

    def submit(self):
        self.parent.target_remove = self.removeChoice.get()
        self.parent.target_editor = self.namelabel.get()
        self.parent.target_editor_password = self.passwordlabel.get()
        self.top.destroy()

class ClientRespHandler(Thread):
    text = None
    socket = None
    application = None

    def __init__(self, text, socket, application):
        super(ClientRespHandler, self).__init__()
        self.text = text
        self.socket = socket
        self.application = application
        print "Started new listener"

    def run(self):
        try:
            while True:
                msg = protocol.retr_msg(self.socket)
                if msg:
                    self.parse_and_handle_message(msg)
                else:
                    self.shut_down()
                    break
        except soc_error:
            return

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
        elif identifier == TERM_CONNECTION:
            LOG.debug('Got message to terminate connection')
            self.text.insert(tk.END, '\n\nKICKED FROM SERVER')
            self.text.config(state='disabled')
            self.application.disconnect()
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

    def shut_down(self):
        self.application.disconnect()
        self.text.insert(tk.END, '\n\nSERVER SHUT DOWN')
        self.text.config(state='disabled')



server = ("127.0.0.1", 7777)
app = Application(server)
app.master.title("Collaborative text editor")
app.mainloop()
app.disconnect()
