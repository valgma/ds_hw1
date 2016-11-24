import select
from socket import SHUT_RDWR
from threading import Thread

import protocol
from protocol import *
from utils import make_logger

LOG = make_logger()

class ClientHandler(Thread):
    def __init__(self,cs,ca,fm):
        Thread.__init__(self)
        self.client_socket = cs
        self.client_addr = ca
        self.fm = fm
        self.wordsmith = None
        #self.send_initmsg()
        self.permissions = FILE_NOAUTH
        self.username = ""

    def send_update(self, msg):
        protocol.forward_msg(self.client_socket, msg)

    def run(self):
        self.process_client()
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
                    msg = protocol.retr_msg(socket)
                    if msg:
                        identifier, row, col, txt = protocol.parse_msg(msg)

                        if identifier == INS_CHAR:
                            for resp_msg in self.wordsmith.in_char(row - 1, col, txt, self):
                                self.wordsmith.notify_all_clients(self, resp_msg)  # send msg to others
                        elif identifier == INIT_TXT:
                            text = self.wordsmith.content()
                            protocol.send_initial_text(self.client_socket, text)
                        elif identifier == REM_USER:
                            if self.permissions == FILE_OWNER:
                                LOG.debug("Removing editor %s from allowed list." % msg)
                                self.wordsmith.remove_editor(txt)

                        elif identifier == ADD_USER_NAME:
                            pw_msg = protocol.retr_msg(socket)
                            _, _, _, pw = protocol.parse_msg(pw_msg)
                            if self.permissions == FILE_OWNER:
                                LOG.debug("Adding editor %s with password %s to editors." % (txt,pw))
                                self.wordsmith.add_editor(txt,pw)

                    else:
                        client_shutdown = True
                if client_shutdown:
                    break
        except soc_error as e:
            LOG.debug('Lost connection with %s:%d' % self.client_addr)
        finally:
            self.disconnect()

    def disconnect(self):
        if self.wordsmith and self in self.wordsmith.subscribers:
            self.wordsmith.subscribers.remove(self)
        try:
            self.sock.fileno()
        except:
            return
        self.client_socket.close()
        LOG.debug("Terminating client %s:%d" % self.client_addr)

    def kick_client_out(self):
        LOG.debug('Kicking out client %s:%d' % self.client_addr)
        protocol.send_msg(self.client_socket, TERM_CONNECTION, 0, 0, 0)
        self.client_socket.shutdown(SHUT_RDWR)
        self.disconnect()


    def send_filelist(self):
        avail_files = self.fm.get_all_titles()
        protocol.send_msg(self.client_socket,FILE_LIST,0,0,len(avail_files))
        for f in avail_files:
            protocol.send_msg(self.client_socket,FILE_ENTRY,0,0,f)

    def process_client(self):
        self.send_filelist()
        fname,user_name,password = self.ask_filename()
        ws = None
        if fname and user_name and password:
            self.wordsmith,self.permissions = self.fm.load_wordsmith(fname,user_name,password)
        protocol.send_permissionbit(self.client_socket,self.permissions)
        if not self.wordsmith:
            self.disconnect()
            return
        self.wordsmith.subscribers.append(self)

    def ask_filename(self):
        user_info = []
        fields = [("filename",USER_FILENAME),("username",USER_NAME),("password",USER_PW)]
        for description,tag in fields:
            msg = retr_msg(self.client_socket)
            if msg.startswith(tag):
                field_val = msg[1 + 2*IND_SIZE :]
                LOG.debug("Retrieved value %s for field %s" % (field_val, description))
                user_info.append(field_val)
            else:
                LOG.error("Expected to get a %s request, instead got: %s",(description,tag))
                return (None,None,None)
        return tuple(user_info)
