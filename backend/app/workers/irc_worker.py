from jaraco.stream import buffer
from irc.client import SimpleIRCClient, ServerConnection, NickMask
import irc.client
import re
import socket
import os
import zipfile

SERVER = "irc.irchighway.net"
PORT = 6667
CHANNEL = "#ebooks"
NICK = "EbookSeeker123"
SEARCH_QUERY = "Frankenstein Mary Shelley"

class IRCXDCCClient(SimpleIRCClient):
    def __init__(self, query: str, job_id: str, save_dir: str, is_list_request: bool):
        super().__init__()
        self.reactor.add_global_handler("ctcp", self.on_ctcp)
        self.query = query
        self.job_id = job_id
        self.save_dir = save_dir
        self.saved_file: str = ''
        self.is_list_request = is_list_request
        self.search_accepted = False
        self.done = False

    def on_raw(self, connection, event):
        print(f"[RAW] {event.arguments}")

    def on_welcome(self, connection, event):
        print("[*] Connected to server.")
        connection.join(CHANNEL)

    def on_join(self, connection, event):
        if NICK in event.source:
            print(f"[*] Joined {CHANNEL}. Sending @search to channel...")
            connection.privmsg(CHANNEL, self.query)

    def on_pubmsg(self, connection, event):
        sender = NickMask(event.source).nick
        message = event.arguments[0]
        print(f"[PUBMSG] <{sender}> {message}")

        if "Your search for" in message and not self.search_accepted:
            print("[*] Search accepted, waiting for DCC SEND...")
            self.search_accepted = True

    def on_ctcp(self, connection, event):
        sender = NickMask(event.source).nick
        ctcp_type = event.arguments[0]
        content = event.arguments[1] if len(event.arguments) > 1 else ""
        print(f"[CTCP] <{sender}> {ctcp_type}: {content}")

        if ctcp_type == "DCC" and content.startswith("SEND"):
            print("[*] DCC SEND detected via CTCP.")
            self.handle_dcc_send(f"{ctcp_type} {content}")

    def on_privmsg(self, connection, event):
        sender = NickMask(event.source).nick
        message = event.arguments[0]
        print(f"[PRIVMSG] <{sender}> {message}")

        if message.startswith("\x01DCC SEND"):
            print("[*] DCC SEND detected.")
            self.handle_dcc_send(message)

    def on_dccmsg(self, connection, event):
            print("[DCCMSG] Received DCC message.")
            dcc_msg = event.arguments[0]
            self.handle_dcc_send(dcc_msg)

    def handle_dcc_send(self, dcc_msg):
        print(f"[*] DCC message: {dcc_msg}")
        # Modified regex to handle unquoted filenames
        match = re.search(r'DCC SEND "?([^"]+?)"? (\d+) (\d+) (\d+)', dcc_msg)
        if not match:
            print("[!] Failed to parse DCC SEND message.")
            return

        filename, ip_int, port, size = match.groups()
        ip = socket.inet_ntoa(int(ip_int).to_bytes(4, 'big'))
        port = int(port)
        size = int(size)

        print(f"[*] Receiving file: {filename} ({size} bytes) from {ip}:{port}")
        filepath = os.path.join(self.save_dir, self.job_id, filename)
        self.saved_file = filepath
        self.receive_file(ip, port, filepath, size)

        if self.is_list_request and filename.endswith(".zip"):
            self.extract_zip(filepath)

        self.done = True
        raise SystemExit(0)

    def receive_file(self, ip, port, filename, size):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with socket.socket() as s:
            s.connect((ip, port))
            with open(filename, "wb") as f:
                received = 0
                while received < size:
                    data = s.recv(4096)
                    if not data:
                        break
                    f.write(data)
                    received += len(data)
        print(f"[✓] Download complete: {filename}")

    def extract_zip(self, zip_path):
        os.makedirs(self.save_dir, exist_ok=True)
        self.saved_file = os.path.join(self.save_dir, self.job_id, 'list.txt')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            original_name = zf.namelist()[0]
            with zf.open(original_name) as source, \
                    open(self.saved_file, 'wb') as target:
                target.write(source.read())

    def display_search_results(self, folder):
        for file in os.listdir(folder):
            if file.endswith(".txt"):
                print("\n[Search Results]")
                with open(os.path.join(folder, file), "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.strip().startswith("!"):
                            print(line.strip())

def download_list(title: str, author: str, job_id) -> str:
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    query: str = f'@search {title} {author}'
    client = IRCXDCCClient(query, job_id, '/data/books', True)
    client.connect(SERVER, PORT, NICK)
    try:
        client.start()
        return client.saved_file
    except SystemExit:
        client.connection.disconnect()
        return client.saved_file

def download_book(query: str, job_id: str) -> str:
    irc.client.ServerConnection.buffer_class = buffer.LenientDecodingLineBuffer
    client = IRCXDCCClient(query, job_id, '/data/books', False)
    client.connect(SERVER, PORT, NICK)
    try:
        client.start()
        return client.saved_file
    except SystemExit:
        print("[*] Finished and exiting.")
        return client.saved_file