#!/usr/bin/env python3

import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import filedialog
import os
import signal
import client_shared
from status_codes import *

## TODO Add in functionality so that ctrl+a works in the input box.

class Window(tk.Frame):

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.master = master
        
        # Widget that can take the whole window.
        self.pack(fill=tk.BOTH, expand=1)
        
        # Setup menu bar.
        menu = tk.Menu(self.master)
        self.master.config(menu=menu)

        chatMenu = tk.Menu(menu, tearoff=0, font=("Helvetica",11))
        chatMenu.add_command(label="Commands", command=self.commands)
        chatMenu.add_command(label="Send file", command=self.open_files)
        chatMenu.add_command(label="Disconnect", command=self.disconnect)
        menu.add_cascade(label="Actions", menu=chatMenu)

        # Setup buttons.
        sendButton = tk.Button(self, text="Send", font=("Helvetica",11), command=self.get_input)
        sendButton.place(x=20,y=487)

        commandsButton = tk.Button(self, text="Commands", font=("Helvetica",11), command=self.commands)
        commandsButton.place(x=85,y=487)

        disconnectButton = tk.Button(self, text="Disconnect", font=("Helvetica",11), command=self.disconnect)
        disconnectButton.place(x=488,y=487)

        # Setup labels.
        chatLabel = tk.Label(self, text=f"Chatting as {client_shared.username}", font=("Helvetica",18))
        chatLabel.place(x=20, y=12)

        inputLabel = tk.Label(self, text="Input", font=("Helvetica",12))
        inputLabel.place(x=20, y=430)

        # Setup chat box text area.
        self.chatBox = ScrolledText(self, height=25, width=68,font=("Helvetica",11), wrap=tk.WORD)
        self.chatBox.place(x=20, y=43)
        self.chatBox.config(state="disabled")
        
        # Setup chat message input box.
        self.inputBox = tk.Text(self, height=1, width=70, font=("Helvetica",11), wrap=tk.WORD)
        self.inputBox.pack()
        self.inputBox.place(x=20, y=455)
        self.inputBox.focus_set()
        
        # Setup so when the user hits enter, it submits the input.
        self.inputBox.bind("<Return>", lambda _: self.get_input())

    # Reads from the input box.
    def get_input(self):
        input = self.inputBox.get("1.0", tk.END)
        input = input.strip()

        if input == "":
            return
        input += '\n'

        msg = f"@{client_shared.username}: " + input
        client_shared.msg = FILL_BUFFER(msg.encode())

        self.insert_text(msg)
        self.inputBox.delete(0.0, tk.END)

    # Adds text to the chatbox.
    def insert_text(self, text):
        # This enables editing of the text box, adds in the text, then disables editing again, and scrolls to the bottom.
        self.chatBox.config(state="normal")
        self.chatBox.insert("end", text)
        self.chatBox.config(state="disabled")
        self.chatBox.see("end")

    # Takes the chosen file and makes the template of it in the input textbox.
    def file_template(self, filename):
        self.inputBox.delete(0.0, tk.END)
        self.inputBox.insert("end", f'!attach "{filename}" ')

    # Adds disconnect logic to the GUI.
    def disconnect(self):
        client_shared.disconnecting = True
        os.kill(0, signal.SIGINT)

    # Display list of typed server commands.
    def commands(self):
        client_shared.msg = FILL_BUFFER(f"@{client_shared.username}: !commands".encode())

    # Prompts the user to choose a file to send.
    def open_files(self):
        file = filedialog.askopenfilename(title="Choose a file", filetypes=[("All files", "*.*")])
        self.file_template(file)

# Behaviour of the X at the top right.
def close_button():
    if messagebox.askyesno("Disconnect", "Would you like to disconnect from the server?"):
        app.disconnect()

# Initialize Tkinter.
root = None
app = None

# Show window.
def main():
    global root
    global app

    # Initialize GUI
    root = tk.Tk()

    # Set window width and height.
    root.geometry("600x525")

    # Set the window's title.
    root.wm_title(client_shared.username)

    # Set the behaviour when the X button at the top right corner is clicked.
    root.protocol("WM_DELETE_WINDOW", close_button)

    # Set the font for the menu bar to the below.
    root.option_add("*Font", 'Helvetica 11')

    #Set the app to be the class defined.
    app = Window(root)

    # Run the app. Normally you would use app.mainloop(), however, there's a lot of updates that have
    # to happen with new messages coming in for the client to see, so the update is done manually in
    # the main method of client.py as it loops over the selector.
    app.update()

# Called by the client.py main method.
def update_gui():
    app.update()
