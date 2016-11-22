from threading import Thread

class Stoppable(Thread):
    shutdown = False
    def stop(self):
        self.shutdown = True
