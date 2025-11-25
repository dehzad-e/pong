# =================================================================================================
# Contributing Authors:	    Ehsanullah Dehzad, Fatima Fayazi, David Salas
# Email Addresses:          ede274@uky.edu, ffa241@uky.edu, davidsalas@uky.edu
# Date:                     Nov 25, 2025
# Purpose:                  This server manages the game state for a multiplayer Pong game.
#                           It handles connections from two clients, synchronizes paddle positions,
#                           ball coordinates, and scores, and relays this information between players.
# Misc:                     Uses TCP sockets for reliable communication. The left client is the
#                           authoritative physics engine. Threading allows simultaneous client handling.
#                           Communication protocol: CSV format for game state (6 fields).
# =================================================================================================

import socket
import threading

# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games

# Global game state dictionary to store the current status of the game elements
# This acts as the "source of truth" for the server
gameState = {
    "leftPaddleY": 215,  # Center (480/2 - 50/2)
    "rightPaddleY": 215,
    "ballX": 320,        # Center (640/2)
    "ballY": 240,        # Center (480/2)
    "lScore": 0,
    "rScore": 0,
    "sync": 0
}

# Lock to ensure thread-safe access to the global gameState
# This prevents race conditions when multiple client threads try to read/write state simultaneously
gameLock = threading.Lock()

# Track connected clients to handle disconnections and reconnections
connected_clients = {"left": None, "right": None}

def reset_game_state():
    """Resets the game state to initial values."""
    gameState["leftPaddleY"] = 215
    gameState["rightPaddleY"] = 215
    gameState["ballX"] = 320
    gameState["ballY"] = 240
    gameState["lScore"] = 0
    gameState["rScore"] = 0
    gameState["sync"] = 0
    print("Game state reset.")

def client_handler(client_socket, player_side):
    """
    Handles communication with a single connected client.
    
    Args:
        client_socket (socket): The socket object for the connected client.
        player_side (str): The side assigned to this client ("left" or "right").
    """
    global gameState, connected_clients
    
    try:
        while True:
            # Receive data from client
            # Expected Format: paddleY,ballX,ballY,lScore,rScore,sync
            data = client_socket.recv(1024).decode()
            if not data:
                break
            
            parts = data.split(',')
            if len(parts) != 6:
                continue
                
            # Parse the received data
            paddleY = float(parts[0])
            ballX = float(parts[1])
            ballY = float(parts[2])
            lScore = int(parts[3])
            rScore = int(parts[4])
            sync = int(parts[5])
            
            # Acquire lock to safely update the shared game state
            with gameLock:
                # Update server state based on who sent it
                # We only trust the client to update their OWN paddle position
                if player_side == "left":
                    gameState["leftPaddleY"] = paddleY
                else:
                    gameState["rightPaddleY"] = paddleY
                
                # Update shared state (ball, score, sync)
                # Logic: If the client's sync count is higher, it means they have newer game data.
                # This is a simple way to keep states roughly in sync, though a more robust
                # authoritative server model would calculate physics here instead of trusting clients.
                if sync > gameState["sync"]:
                    gameState["ballX"] = ballX
                    gameState["ballY"] = ballY
                    gameState["lScore"] = lScore
                    gameState["rScore"] = rScore
                    gameState["sync"] = sync
                
                # Prepare response to send back to the client
                # We send the OPPONENT'S paddle position so this client can render it.
                # We also send back the authoritative (or latest) ball and score data.
                # Format: oppPaddleY,ballX,ballY,lScore,rScore,sync
                if player_side == "left":
                    oppPaddleY = gameState["rightPaddleY"]
                else:
                    oppPaddleY = gameState["leftPaddleY"]
                
                response = f"{oppPaddleY},{gameState['ballX']},{gameState['ballY']},{gameState['lScore']},{gameState['rScore']},{gameState['sync']}"
            
            # Send the constructed response string back to the client
            client_socket.send(response.encode())
            
    except Exception as e:
        print(f"Error with {player_side} client: {e}")
    finally:
        # Clean up the connection when the loop ends or an error occurs
        print(f"Client {player_side} disconnected")
        with gameLock:
            connected_clients[player_side] = None
            if connected_clients["left"] is None and connected_clients["right"] is None:
                reset_game_state()
        client_socket.close()

def main():
    """
    Main server function to set up the socket and accept client connections.
    """
    # Server configuration
    server_ip = "127.0.0.1" # Localhost
    server_port = 5555      # Port to listen on
    
    # Create a TCP/IP socket
    # AF_INET = IPv4, SOCK_STREAM = TCP
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Bind the socket to the address and port
    server.bind((server_ip, server_port))
    
    # Listen for incoming connections (queue up to 2 requests)
    server.listen(2)
    
    print(f"Server listening on {server_ip}:{server_port}")
    
    # Wait for clients to connect
    while True:
        client_sock, addr = server.accept()
        print(f"Accepted connection from {addr}")
        
        # Determine side assignment based on available slots
        side = None
        with gameLock:
            if connected_clients["left"] is None:
                side = "left"
            elif connected_clients["right"] is None:
                side = "right"
        
        if side:
            with gameLock:
                connected_clients[side] = client_sock
            
            # Send initial configuration to the client
            # Format: screenWidth,screenHeight,playerSide
            # Screen size is hardcoded to 640x480 to match the client's default
            config = f"640,480,{side}"
            client_sock.send(config.encode())
            
            # Start a new thread to handle this client's communication
            # This allows the server to handle multiple clients simultaneously
            thread = threading.Thread(target=client_handler, args=(client_sock, side))
            thread.start()
        else:
            print("Server full. Rejecting connection.")
            client_sock.close()

if __name__ == "__main__":
    main()