import os
from threading import Thread

class FileManager(Thread):
    smiths = []
    #http://stackoverflow.com/questions/12435211/python-threading-timer-repeat-function-every-n-seconds#12435256
    def __init__(self,event,foldername):
        Thread.__init__(self)
        self.stopped = event
        self.folder = foldername

    def run(self):
        while not self.stopped.wait(60):
            for smith in self.smiths:
                pth = os.path.join(self.folder,smith.filename)
                f = open(pth,"w")
                f.write(smith.content())
                f.close()

    def addSmith(self,ws):
        self.smiths.append(ws)
