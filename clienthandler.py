from stoppable import *
from socket import error as soc_error, SHUT_RDWR
import select
from utils import make_logger
import protocol
from protocol import INS_CHAR, GET_LINE, INIT_TXT, TERM_CONNECTION, ADD_USER_PW, ADD_USER_NAME, REM_USER, FILE_OWNER

LOG = make_logger()

class ClientHandler(Thread):
    def __init__(self,cs,ca,ws,un,perm):
        Thread.__init__(self)
        self.client_socket = cs
        self.client_addr = ca
        self.wordsmith = ws
        #self.send_initmsg()
        self.wordsmith.subscribers.append(self)
        self.permissions = perm
        self.username = un

    def send_update(self, msg):
        protocol.forward_msg(self.client_socket, msg)

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
        if self in self.wordsmith.subscribers:
            self.wordsmith.subscribers.remove(self)
        try:
            self.sock.fileno()
        except:
            return
        self.client_socket.close()
        LOG.debug("Terminating client %s:%d" % self.client_addr)

    def stop(self):
        self.shutdown = True

    def kick_client_out(self):
        LOG.debug('Kicking out client %s:%d' % self.client_addr)
        protocol.send_msg(self.client_socket, TERM_CONNECTION, 0, 0, 0)
        self.client_socket.shutdown(SHUT_RDWR)
        self.disconnect()
