from stoppable import *
from socket import error as soc_error, SHUT_RDWR
import select
from utils import make_logger
import protocol
from protocol import INS_CHAR, GET_LINE, INIT_TXT, TERM_CONNECTION

LOG = make_logger()

class ClientHandler(Stoppable):
    def __init__(self,cs,ca,ws):
        Thread.__init__(self)
        self.client_socket = cs
        self.client_addr = ca
        self.wordsmith = ws
        self.shutdown = False
        #self.send_initmsg()
        self.wordsmith.subscribers.append(self)

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
                    else:
                        client_shutdown = True
                if self.shutdown or client_shutdown:
                    break
        except soc_error as e:
            LOG.debug('Lost connection with %s:%d' % self.client_addr)
        finally:
            self.disconnect()

    def disconnect(self):
        self.wordsmith.subscribers.remove(self)
        self.client_socket.close()
        LOG.debug("Terminating client %s:%d" % self.client_addr)

    def stop(self):
        self.shutdown = True

    def kick_client_out(self):
        LOG.debug('Kicking out client %s:%d' % self.client_addr)
        protocol.send_msg(self.client_socket, TERM_CONNECTION, 0, 0, 0)
        self.client_socket.shutdown(SHUT_RDWR)
        self.disconnect()