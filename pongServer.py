# =================================================================================================
# Contributing Authors:	    Student Implementation
# Email Addresses:          student@uky.edu
# Date:                     November 2025
# Purpose:                  Server for multiplayer Pong game - handles two clients and manages game state
# Misc:                     Uses threading for concurrent client handling
# =================================================================================================

import socket
import threading
import json
import sys

# =================================================================================================
# GLOBAL GAME STATE
# This dictionary holds the authoritative game state that both clients will synchronize with
# =================================================================================================
game_state = {
    "left_paddle_y": 215,      # Y position of left paddle (starts centered at 240/2 - 25)
    "right_paddle_y": 215,     # Y position of right paddle
    "ball_x": 320,             # Ball X position (center of 640)
    "ball_y": 240,             # Ball Y position (center of 480)
    "ball_xvel": -5,           # Ball X velocity
    "ball_yvel": 0,            # Ball Y velocity
    "left_score": 0,           # Left player score
    "right_score": 0,          # Right player score
    "sync": 0                  # Sync counter to help detect desynchronization
}

# Thread lock to prevent race conditions when multiple threads access game_state
game_lock = threading.Lock()

# Store connected clients (we need exactly 2)
clients = []
clients_lock = threading.Lock()

# Screen dimensions (must match client)
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480


# =================================================================================================
# Author: Instructor
# Purpose: Handle communication with a single client
# Pre: client_socket is a connected socket, player_side is "left" or "right"
# Post: Client is removed from clients list when disconnected
# =================================================================================================
def handle_client(client_socket: socket.socket, player_side: str, address: tuple) -> None:
    """
    This function runs in a separate thread for each client.
    It continuously:
    1. Receives paddle position updates from the client
    2. Updates the shared game_state
    3. Sends the full game state back to the client
    """
    print(f"[NEW CONNECTION] {address} connected as {player_side} paddle")
    
    try:
        # STEP 1: Send initial game info to client
        # Client needs to know: screen dimensions and which paddle they control
        initial_data = {
            "screen_width": SCREEN_WIDTH,
            "screen_height": SCREEN_HEIGHT,
            "player_paddle": player_side
        }
        message = json.dumps(initial_data) + "\n"  # Add newline as delimiter
        client_socket.send(message.encode())
        print(f"[SENT] Initial data to {player_side}: {initial_data}")
        
        # STEP 2: Main game loop - continuously exchange data
        while True:
            # Receive data from client
            data = client_socket.recv(1024).decode()
            
            if not data:
                # Client disconnected
                print(f"[DISCONNECTED] {address} ({player_side} paddle)")
                break
            
            # Parse the JSON message from client
            try:
                client_data = json.loads(data.strip())
            except json.JSONDecodeError:
                print(f"[ERROR] Invalid JSON from {address}: {data}")
                continue
            
            # STEP 3: Update game state with client's paddle position
            with game_lock:
                if player_side == "left":
                    game_state["left_paddle_y"] = client_data.get("paddle_y", game_state["left_paddle_y"])
                else:
                    game_state["right_paddle_y"] = client_data.get("paddle_y", game_state["right_paddle_y"])
                
                # Update scores if client sent them (client detects scoring)
                if "left_score" in client_data:
                    game_state["left_score"] = client_data["left_score"]
                if "right_score" in client_data:
                    game_state["right_score"] = client_data["right_score"]
                
                # Update ball position if client sent it (client runs physics)
                if "ball_x" in client_data:
                    game_state["ball_x"] = client_data["ball_x"]
                    game_state["ball_y"] = client_data["ball_y"]
                    game_state["ball_xvel"] = client_data["ball_xvel"]
                    game_state["ball_yvel"] = client_data["ball_yvel"]
                
                game_state["sync"] = client_data.get("sync", 0)
                
                # STEP 4: Prepare state to send back to client
                # Each client needs to know opponent's paddle position and ball state
                response_data = {
                    "opponent_paddle_y": game_state["right_paddle_y"] if player_side == "left" else game_state["left_paddle_y"],
                    "ball_x": game_state["ball_x"],
                    "ball_y": game_state["ball_y"],
                    "ball_xvel": game_state["ball_xvel"],
                    "ball_yvel": game_state["ball_yvel"],
                    "left_score": game_state["left_score"],
                    "right_score": game_state["right_score"],
                    "sync": game_state["sync"]
                }
            
            # STEP 5: Send updated game state back to client
            response_message = json.dumps(response_data) + "\n"
            client_socket.send(response_message.encode())
            
    except Exception as e:
        print(f"[ERROR] Exception with {address}: {e}")
    
    finally:
        # Clean up when client disconnects
        client_socket.close()
        with clients_lock:
            if client_socket in clients:
                clients.remove(client_socket)
        print(f"[CLOSED] Connection with {address} closed")


# =================================================================================================
# Author: Instructor
# Purpose: Start the server and accept client connections
# Pre: None
# Post: Server is running and handling up to 2 clients
# =================================================================================================
def start_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    """
    Main server function:
    1. Creates and binds a TCP socket
    2. Listens for connections
    3. Accepts exactly 2 clients (left and right paddles)
    4. Creates a thread for each client
    """
    # STEP 1: Create TCP socket
    # AF_INET = IPv4, SOCK_STREAM = TCP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Allow reusing the address (useful for quick restarts during testing)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # STEP 2: Bind to host and port
    # "0.0.0.0" means listen on all network interfaces
    server_socket.bind((host, port))
    
    # STEP 3: Start listening (backlog of 2 since we only need 2 clients)
    server_socket.listen(2)
    
    print(f"[STARTING] Server starting on {host}:{port}")
    print(f"[LISTENING] Waiting for 2 players to connect...")
    
    # STEP 4: Accept first client (left paddle)
    client_socket, address = server_socket.accept()
    with clients_lock:
        clients.append(client_socket)
    
    # Create thread for left player
    thread = threading.Thread(target=handle_client, args=(client_socket, "left", address))
    thread.daemon = True  # Thread will exit when main program exits
    thread.start()
    
    print(f"[CONNECTED] 1/2 players connected (left paddle)")
    
    # STEP 5: Accept second client (right paddle)
    client_socket, address = server_socket.accept()
    with clients_lock:
        clients.append(client_socket)
    
    # Create thread for right player
    thread = threading.Thread(target=handle_client, args=(client_socket, "right", address))
    thread.daemon = True
    thread.start()
    
    print(f"[CONNECTED] 2/2 players connected (right paddle)")
    print(f"[GAME STARTED] Both players connected! Game is live.")
    
    # Keep server running
    try:
        while True:
            # Check if both clients are still connected
            with clients_lock:
                if len(clients) < 2:
                    print("[WAITING] A player disconnected. Waiting for reconnection...")
            threading.Event().wait(1)  # Sleep for 1 second
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server shutting down...")
        server_socket.close()
        sys.exit(0)


# =================================================================================================
# Main entry point
# =================================================================================================
if __name__ == "__main__":
    # You can change host and port here
    # Use "127.0.0.1" for localhost testing or "0.0.0.0" to accept external connections
    HOST = "127.0.0.1"  # Change to "0.0.0.0" for network play
    PORT = 5000
    
    start_server(HOST, PORT)