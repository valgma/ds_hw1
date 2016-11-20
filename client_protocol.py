from common import INS_CHAR, pad_right, IND_SIZE, pad_left, MESSAGE_SIZE, GET_LINE
from socket import error as soc_error

def send_char(socket,row,col,char):
    p_row = pad_left(row,IND_SIZE)
    p_col = pad_left(col,IND_SIZE)
    msg = INS_CHAR + p_row + p_col + char
    print "sent: " + msg
    socket.send(pad_right(msg,MESSAGE_SIZE))

def ask_line(socket, row):
    p_row = pad_left(row,IND_SIZE)
    p_col = pad_left('',IND_SIZE)
    msg = GET_LINE + p_row + p_col
    print "sent: " + msg
    socket.send(pad_right(msg, MESSAGE_SIZE))

def retr_text(socket):
    try:
        length = int(socket.recv(MESSAGE_SIZE))
        if length:
            m = socket.recv(length)
            return m
        else:
            return ""
    except (soc_error,ValueError):
        print "Error when retrieving text from server"
        raise Exception("paha paha")
