import tarfile as tar
import json
import datetime
import fnmatch
import os
import tkinter as tk
from tkinter import scrolledtext, messagebox

def setup():
    data = {}
    gui = {}
    data["log"] = {"events": [], "commands": []}
    data["owners"] = {}
    try:
        with open('settings.ini', 'r') as file:
            username = file.readline().strip()
            archive_path = file.readline().strip()
            log_path = file.readline().strip()
            start_path = file.readline().strip()
    except Exception:
        print('Unable to extract data from settings.ini')
        return
    root = tk.Tk()
    root.title(f"{username}@localhost Shell Emulator")
    log = {"events": [], "commands": []}
    gui["root"] = root
    try:
        with open(log_path, 'w') as logfile:
            with tar.open(archive_path, 'a') as tarfile:
                data["tarfile"] = tarfile
                data["currpath"] = "/"
                data["username"] = "root"
                with open(start_path, 'r') as startfile:
                    for line in startfile:
                        exec_command(line.strip(), data, gui)
                data["username"] = username
                text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD)
                text_area.pack(expand=True, fill='both')
                gui["text_area"] = text_area
                text_area.config(state=tk.DISABLED)
                console_print(gui, f"{data['username']}@localhost: ", False)
                entry = tk.Entry(root)
                entry.pack(fill='x')
                gui["entry"] = entry
                entry.bind('<Return>', lambda x, data=data, gui=gui: execute(x, data, gui))

                root.mainloop()

            json.dump(data["log"], logfile)
            print(data["log"])
            root.destroy()
    except FileNotFoundError:
        print('Unable to open tar, json or sh file')


def console_print(gui, text, newline=True):
    if "text_area" in gui:
        gui["text_area"].configure(state='normal')
        gui["text_area"].insert(tk.END, text+"\n" if newline else text)
        gui["text_area"].configure(state='disabled')
    
def execute(x, data, gui):
    command = gui["entry"].get()
    console_print(gui, command)
    exec_command(command, data, gui)
    gui["entry"].delete(0, tk.END)
    print('DEBUG: ', data["currpath"], data["log"])
    

def get_full_path(path, currpath):
    if path == '.':
        return currpath
    elif path == '..':
        return currpath[:currpath[:-1].rfind('/') + 1]
    elif path.startswith('/'):
        return path
    return currpath + path


def check_param(file, param, arg):
    if param == "-name":
        print("DEBUG: ", file.name[file.name.rfind('/')+1:])
        return fnmatch.fnmatch(file.name[file.name.rfind('/')+1:], arg.replace('"', ''))
    if param == "-type":
        return ((arg=="f" and file.isfile()) or
                (arg=="d" and file.isdir()) or
                (arg=="l" and file.issym()) or
                (arg=="b" and file.isblk()) or
                (arg=="c" and file.ischr()))
    if param == "-size":
        if "+" in arg:
            return file.size > int(arg)
        if "-" in arg:
            return file.size < abs(int(arg))
        return file.size == int(arg)
    raise ValueError

                
def exec_find(gui, tarfile, startpath, param=None, arg=None):
    for file in tarfile.getmembers():
        print("DEBUG", file.name, startpath, param, arg)
        if file.name.startswith(startpath[1:]):
            if param is None or check_param(file, param, arg):
                console_print(gui, '/' + file.name)

                
def exec_command(command, data, gui):
    username = data["username"]
    currpath = data["currpath"]
    if command.startswith("ls"):
        for file in data["tarfile"].getmembers():
            filename = '/' + file.name
            print('DEBUG', filename)
            if filename.startswith(currpath) and '/' not in filename[(len(currpath)):]:
                console_print(gui, filename[(len(currpath)):])
        data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"ls\" in {currpath}")
    elif command.startswith("exit"):
        gui["root"].quit()
    elif command.startswith("cd"):
        newpath = get_full_path(command[3:], currpath)
        try:
            if newpath[1:]:
                member = data["tarfile"].getmember(newpath[1:])
                if not(member.isdir()):
                    console_print(gui, f"can't cd to {command[3:]}: not a directory")
                    data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" in {currpath} but this is not a directory")
            data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" in {currpath}")
            if not newpath or newpath[-1] != '/':
                newpath += '/'
            data["currpath"] = newpath
        except KeyError:
            console_print(gui, f"can't cd to {command[3:]}: no such file or directory")
            data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" in {currpath} but no such file or directory found")
    elif command.startswith("chown"):
        params = command.split()
        if len(params) == 3:
            file = get_full_path(params[2], currpath)
            try:
                if file[1:]:
                    data["tarfile"].getmember(file[1:])
                if file not in data["owners"] or data["username"] == data["owners"][file] or data["username"] == "root":
                    data["owners"][file] = params[1]
                    data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\"")
                    print("DEBUG: ", data["owners"])
                else:
                    console_print(gui, f"{params[2]}: No permission")
                    data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" but he has no permission")
            except KeyError:
                console_print(gui, f"{params[2]}: no such file or directory")
                data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" but no such file or directory found")
        else:
            console_print(gui, "Invalid count of args")
            data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" but it cannot be processed")
    elif command.startswith("history"):
        for i, line in enumerate(data["log"]["commands"], start=1):
            console_print(gui, str(i) + " " + line)
        data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"history\"")
    elif command.startswith("find"):
        params = command.split()
        if len(params) == 4 or len(params) == 2:
            startpath = get_full_path(params[1], currpath)
            print("DEBUG", startpath)
            try:
                if startpath[1:]:
                    data["tarfile"].getmember(startpath[1:])
                if len(params) == 4:
                    exec_find(gui, data["tarfile"], startpath, params[2], params[3])
                else:
                    exec_find(gui, data["tarfile"], startpath)
            except KeyError:
                console_print(gui, f"{params[1]}: no such file or directory")
                data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\" but no such file or directory found")
            except ValueError:
                console_print(gui, f"{params[2]}: invalid parameter")
        elif len(params) == 3:
            exec_find(gui, data["tarfile"], currpath, params[1], params[2])
        elif len(params) == 1:
            exec_find(gui, data["tarfile"], currpath)
        else:
            console_print(gui, "Too many args")
        data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command}\"")
    else:
        try:
            file = get_full_path(command.split()[0], currpath)
            data["tarfile"].getmember(file[1:])
            data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} opened file {file}")
        except KeyError:
            console_print(gui, f"{command.split()[0]}: Not found")
            data["log"]["events"].append(f"[{datetime.datetime.now()}] User {username} used command \"{command.split()[0]}\" which is not found")
                
    data["log"]["commands"].append(command)
    console_print(gui, f"{data['username']}@localhost: ", False)
    
setup()


    
