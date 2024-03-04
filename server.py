#!/usr/bin/env python3

## Scott Parkhill
## 251125463
## CS 3357 Assignment 2
## Dr. Katchabaw

import socket
import sys
import signal
import selectors
import re
import argparse

# Import status codes and buffer information.
from status_codes import *


# Setup argparse.
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,description="""\
    ===================================================
    || The server program for CS 3357's Assignment 2 ||
    ===================================================

    Run the program by typing: `python3 server.py`. It will select a port number for you automatically.
    For ease of use, however, this program also allows you to pass a port number to it that you
    would like to use. This makes testing and such much more enjoyable. This can be accessed by
    typing `python3 server.py --port PORT_NUMBER`
    """)
parser.add_argument("-p", "--port", type=int, help="Run the server on a specific port; defaults to a random port.")
args = parser.parse_args()

# Setup selector.
selector = selectors.DefaultSelector()

# Setup regex for server commands.
register = re.compile('^REGISTER (?P<registration_body>.+) CHAT/1.0$')
disconnect = re.compile('^DISCONNECT (?P<username>.+) CHAT/1.0$')
message = re.compile('^@(?P<username>.+):(?P<message>.*)$', re.DOTALL)

# There's an error with this regex that is really bugging me but I haven't been able to figure out and need to spend more time with.
# If you do not provide the term_list, and have spaces in a quoted filename, it matches at the space. For example:
# !attach "/home/parkhill/Pictures/happy bunny.jpg" has the term_list = 'bunny.jpg"'. I tried also with the filename capture group
# using [^"\']\S+, but this did not work, so I need to do more testing on this. I also can't catch when it occurs, so for now all
# that can be done is to execute the command appropriately and don't forget the term_list lol.
# Now that I write this I wonder if that didn't work because I didn't change it in both the server and client. This line should really
# be shared between the files.
# TODO Attend to the above block of text.
file_signature = re.compile('^FILE (?P<filename>["\'].+["\']|\S+) (?P<file_size>\d*) (?P<term_list>.+)$')

# Signal handler to exit on SIGINT.
def signal_handler(signum, frame):

    # Close active connections.
    REMOVE_CURRENT_LINE()
    print("\nClosing active connections...")
    while True:
        for key, mask in selector.select(timeout=0):
            if key.data is not None:
                if mask & selectors.EVENT_WRITE:
                    key.fileobj.sendall(FILL_BUFFER(b"DISCONNECT CHAT/1.0"))
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
        # If there is only the server left, break; otherwise continue.            
        if len(selector.get_map()) == 1: break

    # Close selector.
    selector.close()

    print("Successfully closed connections.")
    print("Exiting.")
    sys.exit(0)

# Function for handling the socket's read/write states and operations.
def sockops(key, mask):

    conn = key.fileobj
    global disconnect
    new_message = b""

    # Reading from socket.
    if mask & selectors.EVENT_READ:

        # Loop in case the message sent is larger than the buffer.
        while True:
            data = conn.recv(BUF_SIZE)
            if not data:
                break


            # Handle file sending.
            if data[:4] == b'FILE':

                # Find the header length.
                count = 0

                while data[count] != ord('\n'):
                    count += 1

                # Get the header.
                file_header = data[:count].decode()

                # Strip off the header from the rest, leaving the file parts.
                data = data[count+1:]

                # Match the header.
                file_header_match = file_signature.match(file_header)

                if file_header_match is None:
                    key.data["out"] += FILL_BUFFER((f'{INVALID_FILE_HEADER_406} Invalid file header\n').encode())
                    return

                # Set up for sending out to recipients.
                file_header_to_send = (file_header + '\n').encode()
                term_list = file_header_match.group("term_list")
                term_list = term_list.split()
                term_list_filtered = []

                # This goes through and deals with the cases where a user name is for example "@Bob Lazar". Then, during the split, you have
                # ['"@Bob', 'Lazar"'], and this needs to be changed to be the single ['@Bob Lazar'] for proper sending. If it's not that case,
                # then it simply adds the term in as is to the filtered list.
                index = 0
                while index < len(term_list):
                    if term_list[index][0] == '"' or term_list[index][0] == "'":
                        new_term = term_list[index][1:]
                        index += 1
                        while index < len(term_list):
                            if '"' in term_list[index] or "'" in term_list[index]:
                                new_term += ' ' + term_list[index][:-1]
                                term_list_filtered.append(new_term)
                                break
                            else:
                                new_term += ' ' + term_list[index]
                                index += 1
                    else:
                        term_list_filtered.append(term_list[index])
                    index += 1

                # It cannot be confirmed that everyone is connected to the server as they may disconnect in the midst of the file
                # being sent. Therefore, the best that can be done is if a term does not exist in the currently logged in users, to
                # then discard that term, but send the user a message warning about this. 
                for name in term_list_filtered:
                    if name[0] == '@' and name != "@all":
                        name_confirmed = False
                        for outkey, _ in selector.select(timeout=0):
                            if outkey.data["username"] == name[1:]:
                                name_confirmed = True
                        if name_confirmed == False:
                            key.data["out"] += FILL_BUFFER(f'The user {name} is not connected to the server\n'.encode())
                            term_list_filtered.remove(name)

                # Send the file to the end recipients.
                for outkey, _ in selector.select(timeout=0):
                    if outkey.data["username"] != key.data["username"]:
                        for follow_term in outkey.data["follow"]:
                            if follow_term in term_list_filtered:
                                outkey.data["out"] += FILL_BUFFER_FILE(file_header_to_send + data)
                                break

                break


            # Handle disconnect request.
            disconnect_request = disconnect.match(data.decode().strip())
            if disconnect_request is not None:
                selector.unregister(key.fileobj)
                conn.close()
                print(f"{key.data['username']} has disconnected from the server.")
                for outkey, _ in selector.select(timeout=0):
                    msg = f"{key.data['username']} has left the server\n"
                    outkey.data["out"] += FILL_BUFFER(msg.encode())
                return


            # This matches file send requests.
            server_command = re.match(f'^@{key.data["username"]}: !attach (?P<filename>["\'].+["\']|\S+) (?P<term_list>.+)', data.decode().strip())
            if server_command is not None:
                print("Attachment being sent, sending out request for file.")
                print(f"Filename: {server_command.group('filename')}\nTerm List: {server_command.group('term_list')}")
                key.data["out"] += FILL_BUFFER(f'SEND {server_command.group("filename")} {server_command.group("term_list")}\n'.encode())
                break


            # This matches simple server commands like !list.
            server_command = re.match(f'^@{key.data["username"]}: !(?P<command>\w+\W?)$', data.decode().strip())
            if server_command is not None:
                command = server_command.group("command")
                if command == "list":
                    server_list = []
                    for tmp_key, _ in selector.select(timeout=0):
                        server_list.append(tmp_key.data["username"])
                    key.data["out"] += FILL_BUFFER((str(server_list) + '\n').encode())
                elif command == "follow?":
                    follow_list = ""
                    for term in key.data["follow"]:
                        follow_list += term + ", "
                    
                    if follow_list == "":
                        key.data["out"] += FILL_BUFFER(b"You aren't following anyone or anything\n")
                    else:
                        key.data["out"] += FILL_BUFFER((follow_list[:-2] + "\n").encode())

                elif command == "commands":
                    commands = "\
!commands -- displays this help\n\
!list -- displays the list of currently active users\n\
!follow term -- follows the given term, such as 'apple'\n\
!follow @user -- follows the given user\n\
!follow? -- displays a list of those whom you are following\n\
!quit -- exit the program\n\
!exit -- exit the program\n\
!attach file_name term_list -- !attach \"/home/user/bunny hopping.jpg\" @Sarah bunny\
"

                    key.data["out"] += FILL_BUFFER(commands.encode())

                break

            # This matches complicated server commands such as !follow bob.
            server_command = re.match(f'^@{key.data["username"]}: !(?P<command>\w+) (?P<term>.+)$', data.decode().strip())
            if server_command is not None:
                command = server_command.group("command")

                # Follow a term or user.
                if command == "follow":
                    new_follow = server_command.group("term")

                    # Check if they're already following that user or term.
                    if new_follow in key.data["follow"]:
                        key.data["out"] += FILL_BUFFER(f'Already following {new_follow}\n'.encode())

                    # Request made to follow a user.
                    elif new_follow[0] == '@':

                        # Make sure that user exists.
                        for tmp_key, _ in selector.select(timeout=0):

                            # If the user exists, add to follow list.
                            if tmp_key.data["username"] == new_follow[1:]:
                                key.data["follow"].append(new_follow)
                                key.data["out"] += FILL_BUFFER(f'Now following user {new_follow}\n'.encode())
                                tmp_key.data["out"] += FILL_BUFFER(f'{key.data["username"]} is now following you\n'.encode())
                                new_follow = None
                                break

                        # If the user doesn't exist, send error message to the user.
                        if new_follow is not None and new_follow != "@all":
                            key.data["out"] += FILL_BUFFER(f'User {new_follow} is not connected to the server\n'.encode())

                    # Otherwise, they've requested to follow a term, so add it.
                    else:
                        key.data["follow"].append(new_follow)
                        key.data["out"] += FILL_BUFFER(f'Now following {new_follow}\n'.encode())

                # Unfollow a term or user.
                if command == "unfollow":
                    unfollow_term = server_command.group("term")

                    if unfollow_term in key.data["follow"]:

                        if unfollow_term == f'@{key.data["username"]}':
                            key.data["out"] += FILL_BUFFER(b"You cannot unfollow yourself\n")
                        elif unfollow_term == "@all":
                            key.data["out"] += FILL_BUFFER(b"You cannot unfollow @all\n")
                        else:
                            key.data["follow"].remove(unfollow_term)
                            key.data["out"] += FILL_BUFFER(f"You are no longer following {unfollow_term}\n".encode())

                            if (unfollow_term[0] == '@'):
                                for tmp_key, _ in selector.select(timeout=0):
                                    if tmp_key.data["username"] == unfollow_term[1:]:
                                        tmp_key.data["out"] += FILL_BUFFER(f"{key.data['username']} is no longer following you\n".encode())
                                        break

                    else:
                        key.data["out"] += FILL_BUFFER(b"You are not following that term and so it cannot be unfollowed\n")
                break


            # If the message is not a server command, then it is either a complete
            # or partial message. If it is a complete message, i.e. it contains '\n',
            # then validate the message and add it to the send queue. Otherwise, loop
            # until a '\n' is received from the socket buffer.
            new_message += data
            if new_message.find(b"\n") != -1:
                message_validation = message.match(new_message.decode().strip())

                # Successful message signature match found.
                if message_validation is not None:
                    # If the @username does not match the provided username, then there is a mismatch.
                    if message_validation.group("username") != key.data["username"]:
                        msg = f"{USERNAME_SPOOFED_403} Username spoofed"
                        key.data["out"] = FILL_BUFFER(msg.encode())
                        return

                # Otherwise, no signature match found and the message is invalid.
                else:
                    print(f"The message causing error is: {new_message}")
                    msg = f"{INVALID_MESSAGE_SIGNATURE_402} Invalid message signature"
                    key.data["out"] = FILL_BUFFER(msg.encode())
                    return
                break

        # Write the output to each key's output buffer that is not the current key.
        for outkey, _ in selector.select():
            if outkey.data["username"] != key.data["username"]:
                term_found = False
                for follow_term in outkey.data["follow"]:
                    match = re.match(f'^({follow_term}|.*\W{follow_term})\W.*', new_message.decode())
                    if match is not None:
                        term_found = True
                        break
                if term_found:
                    outkey.data["out"] += new_message
    
    # Writing to socket.
    if mask & selectors.EVENT_WRITE:
        if key.data["out"]:
                conn.sendall(key.data["out"])
                key.data["out"] = b""

# Accept a new connection from the socket when selected.
def accept(key):

    server = key.fileobj
    conn, _ = server.accept()
    conn.setblocking(False)

    tmp_name = "###NEW_CONNECTION###"
    data = {"username":tmp_name, "out":b"", "follow":["@all"]}

    selector.register(conn, selectors.EVENT_READ | selectors.EVENT_WRITE, data)

    # Flags for communication with client.
    acknowledgement_sent = False
    registration_received = False
    result_sent = False
    registration = ""

    while not result_sent:
        for newkey, mask in selector.select(timeout=None):
            if newkey.data is not None and newkey.data["username"] == tmp_name:

                conn = newkey.fileobj

                # If the connection has just been received, then send message to the client confirming
                # the server is accepting the connection.
                if not acknowledgement_sent and mask & selectors.EVENT_WRITE:
                    print("Accepting new connection...")
                    conn.sendall(FILL_BUFFER(f"{ACCEPTING_CONNECTION_100} Accepting connection".encode()))
                    acknowledgement_sent = True
                    continue
                
                # Receive the registration request from the client.
                if not registration_received and acknowledgement_sent and mask & selectors.EVENT_READ:
                    print("Registration received.")
                    # Regex to confirm match to registration specification.
                    registration = conn.recv(BUF_SIZE)
                    registration = register.match(registration.decode().strip())
                    registration_received = True
                    continue

                # Once the registration has been received, process it and send out either a confirmation
                # message to the client or the appropriate error message.
                if not result_sent and registration_received and mask & selectors.EVENT_WRITE:

                    # If there is no match, respond with an error, otherwise get the username.
                    if registration is None:
                        print(f"{INVALID_REGISTRATION_400} Invalid registration.")
                        print("Connection refused.\n")
                        conn.sendall(FILL_BUFFER(f"{INVALID_REGISTRATION_400} Invalid registration".encode()))
                        selector.unregister(conn)
                        conn.close()
                        return

                    # Check if the username is using reserved keywords, such as 'all'.
                    elif registration.group("registration_body") == "all":
                        print(f"{RESERVED_KEYWORD_405} Chosen username is a reserved keyword.")
                        print("Connection refused.\n")
                        conn.sendall(FILL_BUFFER(f"{RESERVED_KEYWORD_405} Chosen username is a reserved keyword".encode()))
                        selector.unregister(conn)
                        conn.close()
                        return

                    # Check if the username is already registered.
                    else:
                        for current_keys, _ in selector.select(timeout=0):
                            if current_keys.data["username"] == registration.group("registration_body"):
                                print(f"{ALREADY_REGISTERED_401} Client already registered.")
                                print("Connection refused.\n")
                                conn.sendall(FILL_BUFFER(f"{ALREADY_REGISTERED_401} Client already registered".encode()))
                                selector.unregister(conn)
                                conn.close()
                                return

                    # If the username is not already registered, set the username for the key
                    # and confirm registration
                    newkey.data["username"] = registration.group("registration_body")
                    newkey.data["follow"].append(f"@{newkey.data['username']}")
                    print(f"New connection established with {data['username']}.\n")
                    conn.sendall(FILL_BUFFER(f"{SUCCESS_200} Registration successful".encode()))
                    result_sent = True

    # Send out message to the rest of the connections that someone has joined the server.
    for outkey, _ in selector.select():
        msg = f"{data['username']} has joined the server\n"
        outkey.data["out"] += FILL_BUFFER(msg.encode())

def main():
    # Setup signal handler to exit on SIGINT.
    signal.signal(signal.SIGINT, signal_handler)
 
    # Setup TCP socket.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

        # Setup socket listening on an available port.
        port = args.port if args.port else 0
        server.bind(("localhost", port))
        server.listen(100)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.setblocking(False)
        sock_addr = server.getsockname()[0]
        sock_port = server.getsockname()[1]
        print(f"Server is listening at address {sock_addr} on port {sock_port}.\n")

        # Setup selector.
        selector.register(server, selectors.EVENT_READ, data=None)
        
        # Listen until interrupt.
        while True:
            for key, mask in selector.select(timeout=0):
                if key.data is None:
                    accept(key)
                else:
                    sockops(key, mask)
        
                

if __name__ == "__main__":
    main()