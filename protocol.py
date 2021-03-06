from utils import pad_right, pad_left
from socket import error as soc_error

# msg format: MSG_LEN | IDENTIFIER | ROW_NR | COL_NR | CONTENT
# field leng: IND_SIZE | 1 | IND_SIZE | IND_SIZE | MSG_LEN - (2*IND_SIZE + 1)
# receive works so that first read IND_SIZE -> get rest of len from that -> read the rest

DEFAULT_SERVER = ("127.0.0.1", 7777)

# MESSAGE_SIZE = 128
IND_SIZE = 32

RSP_OK = '0'

INS_CHAR = 'I'
BLOCK_LINE = 'B'
UNBLOCK_LINE = 'U'
GET_LINE = 'G'

INIT_TXT = 'S'

FILE_LIST = 'L'
FILE_ENTRY = 'E'

TERM_CONNECTION = 'T'

FILE_OWNER = 'O'
FILE_EDITOR = 'E'
FILE_NOAUTH = 'X'

USER_FILENAME = '1'
USER_NAME = '2'
USER_PW = '3'

ADD_USER_NAME = 'A'
ADD_USER_PW = 'a'
REM_USER = 'R'

def assemble_msg(identifier, row, col, content):
    content = str(content)
    msg_len = len(identifier) + 2 * IND_SIZE + len(content)
    p_msg_len = pad_left(msg_len, IND_SIZE)
    p_row = pad_left(row, IND_SIZE)
    p_col = pad_left(col, IND_SIZE)
    msg = p_msg_len + identifier + p_row + p_col + content

    return msg

def send_msg(socket, identifier, row, col, content):
    msg = assemble_msg(identifier, row, col, content)
    socket.sendall(msg)
    #print 'sent:' + msg

def forward_msg(socket, msg):
    socket.sendall(msg)
    #print 'sent:' + msg

def retr_msg(socket):
    try:
        length = int(socket.recv(IND_SIZE))
        if length:
            m = socket.recv(length)
            return m
        else:
            return ""
    except ValueError:
        return ""
    except soc_error as e:
        raise e

def parse_msg(msg):
    #print "parsing:" + msg
    ident = msg[0]
    row = int(msg[1 : IND_SIZE + 1])
    col = int(msg[IND_SIZE + 1 : 2 * IND_SIZE + 1])
    content = msg[2 * IND_SIZE + 1 :]
    #print "parse_res:%s | %d | %d | %s" % (ident, row, col, content)
    return ident, row, col, content

def send_char(socket, row, col, char):
    send_msg(socket, INS_CHAR, row, col, char)

def ask_line(socket, row):
    send_msg(socket, GET_LINE, row, 0, 0)

def send_line(socket, row, txt):
    send_msg(socket, GET_LINE, row, 0, txt)

def ask_initial_text(socket):
    send_msg(socket, INIT_TXT, 0, 0, 0)

def send_initial_text(socket, txt):
    send_msg(socket, INIT_TXT, 0, 0, txt)

def send_block_msg(socket, row, blocking):
    identifier = BLOCK_LINE if blocking else UNBLOCK_LINE
    send_msg(socket, identifier, row, 0, 0)

def send_permissionbit(socket,bit):
    send_msg(socket, bit, 0,0,0)

def send_user_info(socket,filename,username,password):
    send_msg(socket, USER_FILENAME, 0, 0, filename)
    send_msg(socket, USER_NAME, 0, 0, username)
    send_msg(socket, USER_PW, 0, 0, password)
