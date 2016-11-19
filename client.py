#! /usr/bin/env python
import Tkinter as tk

from socket import socket, AF_INET, SOCK_STREAM, SHUT_WR, SHUT_RD
from socket import error as soc_error

from common import make_logger
from client_protocol import send_char, retr_text
LOG = make_logger()

class Application(tk.Frame):
    sock = None
    def __init__(self,server,master=None):
        tk.Frame.__init__(self,master)
        self.grid()
        self.createWidgets()
        self.connect(server)
        self.bindKeys()
        self.retrieveText()

    def bindKeys(self):
        self.text.bind("<Key>",self.key_press)
        self.pack()

    def createWidgets(self):
        self.quitButton = tk.Button(self, text="Quit", command=self.quit)
        self.quitButton.grid()

        self.text = tk.Text(self)
        self.text.insert("0.0","Retrieving content from server..")

        self.text.config(bg="#d6d8d8",state=tk.DISABLED)

        self.text.grid()

    def key_press(self,event):
        ind =  self.text.index(tk.INSERT).split(".")
        row = ind[0]
        col = ind[1]
        try:
            in_char = event.char[0]
            send_char(self.sock,row,col,event.char[0])
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
            sock.fileno()
        except:
            return
        LOG.info("Disconnected from server.")
        sock.close()


server = (("82.131.111.147",7777))
app = Application(server)
app.master.title("Minu jama")
app.mainloop()
app.disconnect()
