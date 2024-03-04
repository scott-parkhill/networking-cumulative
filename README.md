TO USE THE GUI, PLEASE SSH WITH X11 FORWARDING
Example: ssh -X username@compute.gaul.csd.uwo.ca


General Instructions:

By typing `python3 server.py --help` or `python3 client.py --help`, help information will be displayed
there that also lists these instructions. If you have permission issues running this, please type
`chmod 700 server.py client.py status_codes.py` to give you execution permissions.

As a point of note, for connecting to the client, the Professor asked specifically
that it accept two parameters, the address with the port and the username. I accidentally
read this too late after employing a URI scheme for the command line input. See the wiki
link below for the details and the client instructions below for an example. I hope that
this is okay as it still gets the job done. I was inspired by the Professor's use of the
"chat://" notation and ran with it.

https://en.wikipedia.org/wiki/URL#Syntax



Server Instructions:

Type `python3 server.py` to run the program. It will choose a port for you at random. If you like,
however, you can specify a port with `python3 server --port PORT_NUMBER`. 

Press CTRL+C to shutdown the server.

Examples:

1) `python3 server.py`
2) `python3 server.py --port 55555`



Client Instructions:

Firstly, note down the port number that the server says it is running on. The server should be running
on localhost, but, if you like, you may also note down the numeric address of the server and use that
in lieu of localhost below.

To run the client, type in `python3 client.py --connect chat://USERNAME@localhost:PORT_NUMBER`. Remember to
put quote marks around the parameter if you would like to have a username with more than one word in it.
Usernames may not contain symbols.

This client now comes with a GUI. Please run the program with X11 forwarding. If you do not want to use
the GUI, please add the -t or --terminal flags.

Press CTRL+C to close the client.

Examples:

1) `python3 client.py --connect chat://RainbowTrout@localhost:55555`
2) `python3 client.py -c "chat://TAs Are Great!@127.0.0.1:45455"`
3) `python3 client.py -c chat://Hello@localhost:55555 --terminal`
