import logging
def make_logger():
    FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.DEBUG,format=FORMAT)
    LOG = logging.getLogger()
    return LOG

def pad_left(ind, size):
    ind = str(ind)
    return (size - len(ind))*"0" + ind

def pad_right(msg, size):
    msg = str(msg)
    return msg + (size - len(msg))*"0"

