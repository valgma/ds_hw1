from threading import Thread, Lock, Event
from utils import make_logger
from time import sleep
import protocol
from protocol import UNBLOCK_LINE
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
                # msg = self.wordsmith.create_block_msg(str(self.lineno+1),False)
                msg = protocol.assemble_msg(UNBLOCK_LINE, self.lineno + 1, 0, 0)
                self.wordsmith.notify_all_clients(self.author,msg)
                self.linelock.release()
                break
            else:
                self.stopped.clear()

    def poke(self):
        self.stopped.set()
