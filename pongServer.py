# =================================================================================================
# Contributing Authors:	    <Anyone who touched the code>
# Email Addresses:          <Your uky.edu email addresses>
# Date:                     <The date the file was last edited>
# Purpose:                  <How this file contributes to the project>
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
#import threading

# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games


HOST = "0.0.0.0"   # Listen on all available network interfaces
PORT = 65432       # You can change this, but remember to match it on the client

def main():
    # Create a TCP socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)  # For now, only accept 1 client
    print(f"Server listening on {HOST}:{PORT} ...")

    # Wait for a client to connect
    conn, addr = server.accept()
    print(f"Client connected from {addr}")

    # Send a simple welcome message to the client
    welcome_msg = "WELCOME_TO_PONG"
    conn.sendall(welcome_msg.encode())

    # Optionally, receive a message from the client
    try:
        data = conn.recv(1024)
        if data:
            print("Client says:", data.decode(errors="ignore"))
    except:
        pass

    # Close the connection (for now)
    conn.close()
    server.close()
    print("Server shut down.")

if __name__ == "__main__":
    main()
