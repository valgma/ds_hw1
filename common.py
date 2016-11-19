import logging
def make_logger():
    FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.DEBUG,format=FORMAT)
    LOG = logging.getLogger()
    return LOG

def pad_left(ind,size):
    return (size - len(ind))*"0" + ind

def pad_right(msg,size):
    return msg + (size - len(msg))*"0"

MESSAGE_SIZE = 128
IND_SIZE = 32

INS_CHAR = 'I'
BLOCK_LINE = 'B'
UNBLOCK_LINE = 'U'

RSP_OK = '0'
