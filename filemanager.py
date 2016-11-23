import os
import json
from threading import Thread
from wordsmith import Wordsmith
from protocol import FILE_OWNER, FILE_EDITOR, FILE_NOAUTH
from utils import make_logger

LOG = make_logger()

OWNERSHIP_FILE = 'ownerships.json'
TEXT_FOLDER = 'text'

class FileManager(Thread):
    #http://stackoverflow.com/questions/12435211/python-threading-timer-repeat-function-every-n-seconds#12435256
    def __init__(self,event,foldername):
        Thread.__init__(self)
        self.ownerships = {}
        self.stopped = event
        self.folder = foldername
        self.wordsmiths = {}
        self.load_ownership_dict()


    def run(self):
        while not self.stopped.wait(60):
            for smith in self.wordsmiths.values():
                self.write_smith(smith)

    def write_smith(self,smith):
        pth = os.path.join(self.folder,smith.filename)
        with open(pth, 'w') as f:
            f.write(smith.content())


    def get_all_titles(self):
        return os.listdir(self.folder)

    def store_ownership_dict(self):
        f = open(OWNERSHIP_FILE,'w')
        f.write(json.dumps(self.ownerships,encoding="us-ascii"))
        f.close()

    def load_ownership_dict(self):
        f = open(OWNERSHIP_FILE,'r')
        self.ownerships = json.loads(f.read(),encoding="us-ascii")
        f.close()

    def load_wordsmith(self,fname,username,password):
        LOG.debug("%s with password %s requesting %s" % (username, password, fname))
        ws = None
        permission = FILE_NOAUTH
        perms = [("editors",FILE_EDITOR),("owners",FILE_OWNER)]

        if fname in self.wordsmiths.keys():
            LOG.info("Wordsmith already loaded, checking permissions")
            permission = self.check_permissions(fname,username,password)
            if permission != FILE_NOAUTH:
                ws = self.wordsmiths[fname]
        else:
            try:
                LOG.debug("Wordsmith not loaded, trying to initialize.")
                pth = os.path.join(TEXT_FOLDER,fname)
                f = open(pth,'r')
                content = f.read()
                f.close()
                wsi = Wordsmith(fname)
                wsi.set_content(content)
                self.wordsmiths[fname] = wsi
                LOG.debug("Successfully loaded, checking permissions.")
                permission = self.check_permissions(fname,username,password)
                if permission != FILE_NOAUTH:
                    ws = wsi
            except IOError:
                LOG.debug("No such file, creating wordsmith.")
                ws = Wordsmith(fname)
                self.wordsmiths[fname] = ws
                self.write_smith(ws)
                LOG.debug("Granting privileges.")
                self.ownerships[fname] = {}
                self.ownerships[fname]["owners"] = {}
                self.ownerships[fname]["owners"][username] = password
                self.ownerships[fname]["editors"] = {}
                self.ownerships[fname]["editors"][username] = password
                self.store_ownership_dict()
                permission = FILE_OWNER
        return (ws,permission)

    def check_permissions(self,fname,username,password):
        permission = FILE_NOAUTH
        perms = [("editors",FILE_EDITOR),("owners",FILE_OWNER)]
        for index,perm_bit in perms:
            try:
                if self.ownerships[fname][index][username] == password:
                    permission = perm_bit
            except KeyError:
                break
        LOG.debug("Granted permission %c" % permission)
        return permission
