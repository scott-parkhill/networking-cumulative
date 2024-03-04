#!/usr/bin/env python3

## Scott Parkhill
## 251125463
## CS 3357 Assignment 2
## Dr. Katchabaw

# Read/write buffer stuff.
BUF_SIZE = 512
BUF_CHAR = ' '
BUF_CHAR_B = b' '
BUF_FILE_CHAR = b'\0'

# This is used because I wrote all my code using fixed reads. This worked, but I realized it opened
# myself up for some really big potential problems during file sharing, i.e. messages becoming interleaved
# with the file itself. This is therefore used to also do a fixed write based on the fixed read size.
# It's a little hacky, I know, but the alternative was re-writing basically everything from assignment 2.
FILL_BUFFER = lambda msg, bytes=True: msg + (BUF_CHAR_B if bytes else BUF_CHAR) * (BUF_SIZE - len(msg))
FILL_BUFFER_FILE = lambda msg: msg + BUF_FILE_CHAR * (BUF_SIZE - len(msg))

# Uses VT100 escape sequences so that the ^C doesn't appear on the screen.
ASCII_ESCAPE = 27
REMOVE_CURRENT_LINE = lambda: print("%c[2K\r" %ASCII_ESCAPE, end="")

# Status codes.
ACCEPTING_CONNECTION_100 = 100
SUCCESS_200 = 200
INVALID_REGISTRATION_400 = 400
ALREADY_REGISTERED_401 = 401
INVALID_MESSAGE_SIGNATURE_402 = 402
USERNAME_SPOOFED_403 = 403
RESERVED_KEYWORD_405 = 405
INVALID_FILE_HEADER_406 = 406
INVALID_RESPONSE_500 = 500
UNKNOWN_RESPONSE_CODE_501 = 501

ERROR_CODES = [INVALID_REGISTRATION_400, ALREADY_REGISTERED_401, INVALID_MESSAGE_SIGNATURE_402, USERNAME_SPOOFED_403, RESERVED_KEYWORD_405, INVALID_FILE_HEADER_406]