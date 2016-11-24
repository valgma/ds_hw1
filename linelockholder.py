from threading import Thread, Event
from time import sleep

import protocol
from protocol import UNBLOCK_LINE, GET_LINE
from utils import make_logger

LOG = make_logger()

class LineLockHolder(Thread):
    def __init__(self,lock,auth,nr,ws):
        Thread.__init__(self)
        self.stopped = Event()
        self.linelock = lock
        self.author = auth
        self.lineno = nr
        self.wordsmith = ws

    def run(self):
        while 1:
            sleep(4)
            if not self.stopped.is_set():
                LOG.debug("Line lock released on %d." % (self.lineno + 1))

                # send unblock message
                msg = protocol.assemble_msg(UNBLOCK_LINE, self.lineno + 1, 0, 0)
                self.wordsmith.notify_all_clients(self.author,msg)

                # send line contect for clients to overwrite
                line_content = self.wordsmith.get_line(self.lineno)
                msg_line = protocol.assemble_msg(GET_LINE, self.lineno + 1, 0, line_content)
                self.wordsmith.notify_all_clients(self.author, msg_line)
                
                self.linelock.release()
                break
            else:
                self.stopped.clear()

    def poke(self):
        self.stopped.set()
