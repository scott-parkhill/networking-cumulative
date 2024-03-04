#!/usr/bin/env python3

## Scott Parkhill
## 251125463
## CS 3357 Assignment 2
## Dr. Katchabaw

import argparse
import os
import re
import selectors
import signal
import socket
import sys

# Import status codes and buffer information.
from status_codes import *
import client_gui
import client_shared

## TODO Find a way to guard against sending files when an empty term list is given.
## Allowing quoting of files to allow for spaces in the filenames is messing things up.

## TODO make the if args.terminal PRINT if args.terminal repeated code block a macro or something.

# Setup argparse.
# Tabbing is weird in the help description because of the raw formatting.
# This tabbing aligns the connect help message with default help messages (i.e. from -h).
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,description="""\
    ====================================================
    || The client program for CS 3357's Assignment 2 ||
    ====================================================

    Run the program by typing: `python3 client.py --connect chat://USERNAME@localhost:PORT`,
    where USERNAME is your choice of username and PORT is the port number provided
    to you from the server program. In order to have a username with spaces in it, be
    sure to put quotes around the entire URI. Usernames may not contain symbols.
    """)
parser.add_argument("-c", "--connect", metavar="URI", nargs=1, required=True, dest="address", type=str,\
    help="""\
The URI to the server in the form of: chat://USERNAME@HOSTNAME:PORT.
For example, chat://Batman@localhost:55555. HOSTNAME may only be 'localhost'
or the numeric address of the server, such as 127.0.0.1. In order to have a
username with spaces in it, be sure to put quotes around the entire URI.
Usernames may not contain symbols.
        """)
parser.add_argument("-t", "--terminal", dest="terminal", action="store_true", help="""\
Indicate whether you want to launch this app in the terminal only without the GUI.
""")
args = parser.parse_args()

# Setup selector.
selector = selectors.DefaultSelector()

# Setup regex.
response_code = re.compile('^(?P<code>\d+).*$')
chat_address = re.compile('^chat://(?P<username>.+)@(?P<hostname>localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(?P<port>\d*)$')
disconnect = re.compile("^DISCONNECT CHAT/1.0$")

# See comment for file signature in server.py.
file_signature = re.compile('^FILE (?P<filename>["\'].+["\']|\S+) (?P<file_size>\d*) (?P<term_list>.+)$')

# Signal handler to exit on SIGINT.
def signal_handler(signum, frame):

    if args.terminal: REMOVE_CURRENT_LINE()
    print("\nClosing connection with server...")

    disconnect_sent = False

    while not disconnect_sent:
        for key, mask in selector.select(timeout=0):
            # Select the client-server connection.
            if key.data["username"] == client_shared.username:
                # Send disconnect request to the server.
                if mask & selectors.EVENT_WRITE and disconnect_sent is False:
                    key.fileobj.sendall(FILL_BUFFER(f"DISCONNECT {client_shared.username} CHAT/1.0".encode()))
                    disconnect_sent = True

    selector.close()

    print("Connection successfully closed.")
    sys.exit(0)

# Defines custom print behaviour to determine if CLI or GUI.
# Printc for "print custom".
def printc(text, func):
    if args.terminal:
        func()
    else:
        client_gui.app.insert_text(text)

# Parses for codes sent by the server.
def code_check(message):
    response = response_code.match(message)
    if response is None:
        return SUCCESS_200
    else:
        code = response.group('code')
        response = response.group()

        if code == str(SUCCESS_200):
            return SUCCESS_200
        elif int(code) in ERROR_CODES:
            printc(response, lambda: print(response))
            return int(code)
        else:
            text = f"{UNKNOWN_RESPONSE_CODE_501} Unknown response code: {response}" 
            printc(text, lambda: print(text))
            return int(code)

# Socket Operations.
def sockops(key, mask):
    sock = key.fileobj

    # Read event.
    if mask & selectors.EVENT_READ:

        # If the key is stdin then read the input from stdin into the message global variable.
        if key.data["username"] == "stdin":
            print(f"@{client_shared.username}: ", end="", flush=True)
            client_shared.msg = FILL_BUFFER((f"@{client_shared.username}: " + sock.readline()).encode())

        # Otherwise the key is our connection with the server, so read from the socket and print to console.
        else:
            data = b""
            while True:
                # Read from the socket.
                data += sock.recv(BUF_SIZE)

                # If there is no data then break.
                if not data: break

                # Check if a file send request is being made, and handle it.
                if data[:4].decode() == "SEND":
                    # TODO Compile this regex at the top of the file.
                    send_request = re.match('^SEND (?P<filename>["\'].+["\']|\S+) (?P<term_list>.+)$', data.decode().strip())
                    if send_request is not None:
                        filename = send_request.group("filename")
                        
                        # Check that the provided filename exists.
                        if not os.path.exists(filename.strip('"\'')):
                            # TODO macro this
                            if args.terminal:
                                REMOVE_CURRENT_LINE()
                            msg = "No file by that name exists\n"
                            printc(msg, lambda: print(msg, end=""))
                            if args.terminal:
                                print(f"@{client_shared.username}: ", end="", flush=True)
                            return

                        # Get the basename of the file, size of the file, list of terms to send to, and construct the header.
                        filename_trimmed = '"' + os.path.basename(filename.strip('"\'')) + '"'
                        file_size = os.path.getsize(filename.strip('"\''))
                        term_list = send_request.group("term_list")
                        file_header = f'FILE {filename_trimmed} {file_size} {term_list}\n'.encode()

                        # Create the file record as a dictionary.
                        new_file_to_send = {"filename":filename, "file_header":file_header, "header_size":len(file_header),\
                                            "file_remaining":file_size, "file_pointer":open(filename.strip('"\''), 'rb')}

                        # Add the record to the storage list.
                        client_shared.sending_file.append(new_file_to_send)

                        # TODO macro this
                        if args.terminal:
                            REMOVE_CURRENT_LINE()
                        sending_msg = f"Sending file {filename}\n"
                        printc(sending_msg, lambda: print(sending_msg, end=""))
                        if args.terminal:
                            print(f"@{client_shared.username}: ", end="", flush=True)
                    
                    return


                # Check if a file is being received, and handle it.
                if data[:4].decode() == "FILE":
                    count = 0
                    while data[count] != ord('\n'):
                        count += 1
                    
                    # Strip off the file header.
                    file_header = data[:count]
                    count += 1

                    # Decode the header and save the information held within.
                    file_header_decoded = file_signature.match(file_header.decode())
                    filename = file_header_decoded.group("filename")
                    file_size = int(file_header_decoded.group("file_size"))
                    file_found = False

                    # Loop over the list of files being received and find this particular file.
                    for file in client_shared.recv_file:
                        if file["filename"] == filename:
                            file_found = True
                            # Read the rest of the entire message or, if it'll go past the size of the file, read up to the length of the file.
                            # File is buffered with '\0's, so this chops off all the '\0's if not doing a full read.
                            read_max = count + file["file_size"] - len(file["file"])
                            file["file"] += data[count:read_max]
                            
                            # If file has been completely read, write it.
                            if len(file["file"]) == file["file_size"]:
                                with open(file["filename"].strip('"\''), 'wb') as new_file:
                                    new_file.write(file["file"])

                                # TODO macro this
                                if args.terminal:
                                    REMOVE_CURRENT_LINE()
                                download_msg = f"File {file['filename']} successfully downloaded\n"
                                printc(download_msg, lambda: print(download_msg, end=""))
                                if args.terminal:
                                    print(f"@{client_shared.username}: ", end="", flush=True)

                                # Removes the file from the list of files being received.
                                client_shared.recv_file.remove(file)
                            
                            break

                    # If no record exists of the filename in the list, then process the header.
                    if file_found is False:

                        # TODO macro this
                        if args.terminal:
                            REMOVE_CURRENT_LINE()
                        recv_msg = f"Receiving file {filename}\n"
                        printc(recv_msg, lambda: print(recv_msg, end=""))
                        if args.terminal:
                            print(f"@{client_shared.username}: ", end="", flush=True)

                        # Compute the amount of the file to read, and construct the file record.
                        read_max = count + file_size
                        file = {"filename":filename, "file_size":file_size, "file":data[count:read_max]}
                        
                        # If the entire file has been sent in this single message, then write the file.
                        if len(file["file"]) == file_size:
                            with open(file["filename"].strip('"\''), 'wb') as new_file:
                                new_file.write(file["file"])

                            if args.terminal:
                                REMOVE_CURRENT_LINE()
                            download_msg = f"File {filename} successfully downloaded\n"
                            printc(download_msg, lambda: print(download_msg, end=""))
                            if args.terminal:
                                print(f"@{client_shared.username}: ", end="", flush=True)
                        
                        # Otherwise, add the file to the list of files being received.
                        else:
                            client_shared.recv_file.append(file)

                    return


                # Check for any error messages coming from the server.
                if code_check(data.decode().strip()) != SUCCESS_200:
                    os.kill(0, signal.SIGINT)

                # Check for disconnect signal from the server.
                if disconnect.match(data.decode().strip()) is not None:
                    if args.terminal:
                        selector.unregister(sys.stdin)
                        REMOVE_CURRENT_LINE()
                    print("Server has shutdown. Goodbye.")
                    sock.close()
                    selector.close()
                    sys.exit(0)

                # Once the newline character is found, break. Otherwise, message
                # is greater than BUF_SIZE, so loop and read more until '\n'.
                if data.find(b"\n") != -1:
                    break

            # Print the complete message.
            if args.terminal:
                REMOVE_CURRENT_LINE()
                print(data.decode().strip())
                print(f"@{client_shared.username}: ", end="", flush=True)
            else:
                printc(data.decode().strip() + '\n', None)

    # Write event.
    if mask & selectors.EVENT_WRITE:

        # Sending a message.
        if client_shared.msg:
            # Disconnect if the user types in !quit.
            exit_request = re.match(f'^@{key.data["username"]}: !(quit|exit)$', client_shared.msg.decode().strip())
            if exit_request is not None:
                os.kill(0, signal.SIGINT)
            sock.sendall(client_shared.msg)
            client_shared.msg = b""

        # Sending a file.
        if client_shared.sending_file != []:
            
            # Loop over the list of files being sent.
            for file in client_shared.sending_file:

                # Initialize the message with the header for the file.
                msg = file["file_header"]

                # Calculate the read amount so that each block sent is of size BUF_SIZE.
                read_amount = file["file_remaining"] if BUF_SIZE-file["header_size"] > file["file_remaining"] else BUF_SIZE-file["header_size"]

                # Read that amount from the file, and add it to the message.
                msg += file["file_pointer"].read(read_amount)

                # Decrement the amount of file left to read by that amount.
                file["file_remaining"] -= read_amount

                # If the file has finished sending, close the read and remove the file from the list of files to send.
                if file["file_remaining"] == 0:
                    file["file_pointer"].close()
                    client_shared.sending_file.remove(file)

                # Buffer the file to length BUF_SIZE with 0x00s.
                msg = FILL_BUFFER_FILE(msg)

                # Send the file part.
                sock.sendall(msg)



# Function to handle the logic for registering the client with the server and handling errors therein.
def register_with_server():

    registration_sent = False

    while True:
        for key, mask in selector.select(timeout=0):
            # Obtain the key that contains the client's connection with the server.
            if key.data["username"] == client_shared.username:
                sock = key.fileobj

                # Send register request to the server.
                if mask & selectors.EVENT_WRITE and registration_sent is False:
                    sock.sendall(FILL_BUFFER(f"REGISTER {client_shared.username} CHAT/1.0".encode()))
                    registration_sent = True

                # Wait for server response to registration request.
                if mask & selectors.EVENT_READ and registration_sent is True:
                    response = sock.recv(BUF_SIZE)
                    response = response_code.match(response.decode().strip())
    
                    # If there is no match to a valid response signature then exit.
                    if response is None:
                        print(f"{INVALID_RESPONSE_500} Invalid response received from server")
                        selector.close()
                        sock.close()
                        sys.exit(1)
                    
                    # Response matches response signature.
                    else:
                        code = response.group('code')
                        code = int(code)
                        response = response.group()

                        # Server acknowledged request.
                        if code == ACCEPTING_CONNECTION_100:
                            print("Connecting to server...\n")
                        # Connection established correctly.
                        elif code == SUCCESS_200:
                            return
                        # Error code received.
                        elif code in ERROR_CODES:
                            print(response)
                            selector.close()
                            sock.close()
                            sys.exit(1)
                        # Unknown code received.
                        else:
                            print(f"{UNKNOWN_RESPONSE_CODE_501} Unknown response code: {response}")
                            selector.close()
                            sock.close()
                            sys.exit(1)


def main():

    # Setup signal handler to exit on SIGINT.
    signal.signal(signal.SIGINT, signal_handler)

    # Parse CLI arguments:
    uri = chat_address.match(args.address[0])
    if uri is None:
        print("Improper construction of URI. Please see program help for info.")
        sys.exit(1)

    hostname = uri.group('hostname')
    port = int(uri.group('port'))
    client_shared.username = uri.group('username')

    # Setup TCP socket.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

        # Connect to the server.
        sock.connect((hostname, port))
        sock.setblocking(False)
        selector.register(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data={"username":client_shared.username})

        if args.terminal:
            selector.register(sys.stdin, selectors.EVENT_READ, data={"username":"stdin"})

        register_with_server()

        if args.terminal:
            print("Type '!commands' for a list of server commands.\n")
            print(f"@{client_shared.username}: ", end="", flush=True)
        else:
            client_gui.main()

        # Let the selector work its magic until SIGINT received.
        while True:
            if not args.terminal:
                client_gui.update_gui()

            try:
                for key, mask in selector.select(timeout=None):
                    sockops(key, mask)
            # This catches some weird behaviour that occurs when disconnecting the GUI.
            except ValueError:
                if client_shared.disconnecting:
                    break
                else:
                    print("Fatal selector IO error. Program crashed.")
                    sys.exit(1)


if __name__ == "__main__":
    main()