# =================================================================================================
# Contributing Authors:	    Student Implementation
# Email Addresses:          student@uky.edu
# Date:                     November 2025
# Purpose:                  Server for multiplayer Pong game - handles two clients and manages game state
# Misc:                     Server is authoritative for ball physics and scoring
# =================================================================================================

import socket
import threading
import json
import sys
import time

# =================================================================================================
# GLOBAL GAME STATE
# Server is now AUTHORITATIVE for all ball physics and scoring
# =================================================================================================
game_state = {
    "left_paddle_y": 215,      
    "right_paddle_y": 215,     
    "ball_x": 320.0,           
    "ball_y": 240.0,           
    "ball_xvel": -5.0,         
    "ball_yvel": 0.0,          
    "left_score": 0,           
    "right_score": 0,          
    "sync": 0                  
}

game_lock = threading.Lock()

# Store connected clients
clients = {}  # Changed to dict: {"left": socket, "right": socket}
clients_lock = threading.Lock()

# Screen dimensions
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480

# Paddle dimensions (must match client)
PADDLE_HEIGHT = 50
PADDLE_WIDTH = 10

# Game physics running flag
game_running = False


# =================================================================================================
# Author: Instructor
# Purpose: Server-side ball physics calculation (runs in separate thread)
# Pre: Two clients must be connected
# Post: Ball position updated 60 times per second
# =================================================================================================
def run_game_physics() -> None:
    """
    This runs the authoritative game physics on the server.
    Only the server calculates ball movement, collisions, and scoring.
    Clients just render what the server tells them.
    """
    global game_running
    
    print("[PHYSICS] Game physics thread started")
    
    while game_running:
        time.sleep(1/60)  # Run at 60 FPS like the client
        
        with game_lock:
            # Check if game is over (someone reached 5 points)
            if game_state["left_score"] >= 5 or game_state["right_score"] >= 5:
                # Don't update ball physics if game is over
                continue
            # Update ball position
            game_state["ball_x"] += game_state["ball_xvel"]
            game_state["ball_y"] += game_state["ball_yvel"]
            
            # Check for scoring (ball goes off left or right edge)
            if game_state["ball_x"] > SCREEN_WIDTH:
                game_state["left_score"] += 1
                print(f"[SCORE] Left player scores! {game_state['left_score']}-{game_state['right_score']}")
                # Reset ball to center, going left
                game_state["ball_x"] = SCREEN_WIDTH / 2
                game_state["ball_y"] = SCREEN_HEIGHT / 2
                game_state["ball_xvel"] = -5.0
                game_state["ball_yvel"] = 0.0
                
            elif game_state["ball_x"] < 0:
                game_state["right_score"] += 1
                print(f"[SCORE] Right player scores! {game_state['left_score']}-{game_state['right_score']}")
                # Reset ball to center, going right
                game_state["ball_x"] = SCREEN_WIDTH / 2
                game_state["ball_y"] = SCREEN_HEIGHT / 2
                game_state["ball_xvel"] = 5.0
                game_state["ball_yvel"] = 0.0
            
            # Check for wall collisions (top and bottom)
            if game_state["ball_y"] <= 10 or game_state["ball_y"] >= SCREEN_HEIGHT - 10:
                game_state["ball_yvel"] *= -1
            
            # Check for paddle collisions
            ball_rect = {
                "left": game_state["ball_x"],
                "right": game_state["ball_x"] + 5,
                "top": game_state["ball_y"],
                "bottom": game_state["ball_y"] + 5
            }
            
            # Left paddle collision
            left_paddle = {
                "left": 10,
                "right": 10 + PADDLE_WIDTH,
                "top": game_state["left_paddle_y"],
                "bottom": game_state["left_paddle_y"] + PADDLE_HEIGHT
            }
            
            if (ball_rect["left"] <= left_paddle["right"] and 
                ball_rect["right"] >= left_paddle["left"] and
                ball_rect["bottom"] >= left_paddle["top"] and
                ball_rect["top"] <= left_paddle["bottom"] and
                game_state["ball_xvel"] < 0):  # Only if moving left
                
                game_state["ball_xvel"] *= -1
                # Add paddle influence on Y velocity
                paddle_center = left_paddle["top"] + PADDLE_HEIGHT / 2
                ball_center = game_state["ball_y"] + 2.5
                game_state["ball_yvel"] = (ball_center - paddle_center) / 2
            
            # Right paddle collision
            right_paddle = {
                "left": SCREEN_WIDTH - 20,
                "right": SCREEN_WIDTH - 20 + PADDLE_WIDTH,
                "top": game_state["right_paddle_y"],
                "bottom": game_state["right_paddle_y"] + PADDLE_HEIGHT
            }
            
            if (ball_rect["right"] >= right_paddle["left"] and 
                ball_rect["left"] <= right_paddle["right"] and
                ball_rect["bottom"] >= right_paddle["top"] and
                ball_rect["top"] <= right_paddle["bottom"] and
                game_state["ball_xvel"] > 0):  # Only if moving right
                
                game_state["ball_xvel"] *= -1
                # Add paddle influence on Y velocity
                paddle_center = right_paddle["top"] + PADDLE_HEIGHT / 2
                ball_center = game_state["ball_y"] + 2.5
                game_state["ball_yvel"] = (ball_center - paddle_center) / 2
            
            game_state["sync"] += 1


# =================================================================================================
# Author: Instructor
# Purpose: Handle communication with a single client
# Pre: client_socket is a connected socket, player_side is "left" or "right"
# Post: Client is removed from clients dict when disconnected
# =================================================================================================
def handle_client(client_socket: socket.socket, player_side: str, address: tuple) -> None:
    """
    This function runs in a separate thread for each client.
    It continuously:
    1. Receives paddle position updates from the client
    2. Sends the authoritative game state back to the client
    """
    print(f"[NEW CONNECTION] {address} connected as {player_side} paddle")
    
    buffer = ""  # Buffer to accumulate partial messages
    
    try:
        # Send initial game info to client
        initial_data = {
            "screen_width": SCREEN_WIDTH,
            "screen_height": SCREEN_HEIGHT,
            "player_paddle": player_side
        }
        message = json.dumps(initial_data) + "\n"
        client_socket.send(message.encode())
        print(f"[SENT] Initial data to {player_side}: {initial_data}")
        
        # Main communication loop
        while True:
            # Receive data from client
            data = client_socket.recv(1024).decode()
            
            if not data:
                print(f"[DISCONNECTED] {address} ({player_side} paddle)")
                break
            
            # Add received data to buffer
            buffer += data
            
            # Process all complete messages in buffer (messages end with \n)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                
                # Parse the JSON message from client
                try:
                    client_data = json.loads(line.strip())
                except json.JSONDecodeError:
                    print(f"[ERROR] Invalid JSON from {address}: {line}")
                    continue
                
                # Update only the paddle position from this client
                with game_lock:
                    if player_side == "left":
                        game_state["left_paddle_y"] = client_data.get("paddle_y", game_state["left_paddle_y"])
                    else:
                        game_state["right_paddle_y"] = client_data.get("paddle_y", game_state["right_paddle_y"])
                    
                    # Prepare full game state to send back
                    # Send BOTH paddle positions so client knows both
                    response_data = {
                        "left_paddle_y": game_state["left_paddle_y"],
                        "right_paddle_y": game_state["right_paddle_y"],
                        "ball_x": game_state["ball_x"],
                        "ball_y": game_state["ball_y"],
                        "ball_xvel": game_state["ball_xvel"],
                        "ball_yvel": game_state["ball_yvel"],
                        "left_score": game_state["left_score"],
                        "right_score": game_state["right_score"],
                        "sync": game_state["sync"],
                        "player_side": player_side  # Tell client which paddle is theirs
                    }
                
                # Send updated game state back to client
                response_message = json.dumps(response_data) + "\n"
                client_socket.send(response_message.encode())
            
    except Exception as e:
        print(f"[ERROR] Exception with {address}: {e}")
    
    finally:
        client_socket.close()
        with clients_lock:
            if player_side in clients:
                del clients[player_side]
        print(f"[CLOSED] Connection with {address} closed")


# =================================================================================================
# Author: Instructor
# Purpose: Start the server and accept client connections
# Pre: None
# Post: Server is running and handling up to 2 clients
# =================================================================================================
def start_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    """
    Main server function that accepts connections and starts game physics
    """
    global game_running
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(2)
    
    print(f"[STARTING] Server starting on {host}:{port}")
    print(f"[LISTENING] Waiting for 2 players to connect...")
    
    # Accept first client (left paddle)
    client_socket, address = server_socket.accept()
    with clients_lock:
        clients["left"] = client_socket
    
    thread = threading.Thread(target=handle_client, args=(client_socket, "left", address))
    thread.daemon = True
    thread.start()
    
    print(f"[CONNECTED] 1/2 players connected (left paddle)")
    
    # Accept second client (right paddle)
    client_socket, address = server_socket.accept()
    with clients_lock:
        clients["right"] = client_socket
    
    thread = threading.Thread(target=handle_client, args=(client_socket, "right", address))
    thread.daemon = True
    thread.start()
    
    print(f"[CONNECTED] 2/2 players connected (right paddle)")
    print(f"[GAME STARTED] Both players connected! Starting game physics...")
    
    # Start the game physics thread
    game_running = True
    physics_thread = threading.Thread(target=run_game_physics)
    physics_thread.daemon = True
    physics_thread.start()
    
    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server shutting down...")
        game_running = False
        server_socket.close()
        sys.exit(0)


if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 5000
    
    start_server(HOST, PORT)