# =================================================================================================
# Contributing Authors:	    <Anyone who touched the code>
# Email Addresses:          <Your uky.edu email addresses>
# Date:                     <The date the file was last edited>
# Purpose:                  <How this file contributes to the project>
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
import threading

# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games

# Global game state
gameState = {
    "leftPaddleY": 215,  # Center (480/2 - 50/2)
    "rightPaddleY": 215,
    "ballX": 320,        # Center (640/2)
    "ballY": 240,        # Center (480/2)
    "lScore": 0,
    "rScore": 0,
    "sync": 0
}
gameLock = threading.Lock()

def client_handler(client_socket, player_side):
    global gameState
    
    try:
        while True:
            # Receive data from client
            # Format: paddleY,ballX,ballY,lScore,rScore,sync
            data = client_socket.recv(1024).decode()
            if not data:
                break
            
            parts = data.split(',')
            if len(parts) != 6:
                continue
                
            paddleY = float(parts[0])
            ballX = float(parts[1])
            ballY = float(parts[2])
            lScore = int(parts[3])
            rScore = int(parts[4])
            sync = int(parts[5])
            
            with gameLock:
                # Update server state based on who sent it
                if player_side == "left":
                    gameState["leftPaddleY"] = paddleY
                else:
                    gameState["rightPaddleY"] = paddleY
                
                # Update shared state if this client is "newer" or just update anyway
                # Simple approach: Always update ball/score/sync from the client
                # Ideally, we might want one authoritative client for the ball, 
                # but for simplicity, we'll accept updates.
                # To avoid jitter, maybe only update ball if sync is higher?
                if sync > gameState["sync"]:
                    gameState["ballX"] = ballX
                    gameState["ballY"] = ballY
                    gameState["lScore"] = lScore
                    gameState["rScore"] = rScore
                    gameState["sync"] = sync
                
                # Prepare response
                # Format: oppPaddleY,ballX,ballY,lScore,rScore,sync
                if player_side == "left":
                    oppPaddleY = gameState["rightPaddleY"]
                else:
                    oppPaddleY = gameState["leftPaddleY"]
                
                response = f"{oppPaddleY},{gameState['ballX']},{gameState['ballY']},{gameState['lScore']},{gameState['rScore']},{gameState['sync']}"
            
            client_socket.send(response.encode())
            
    except Exception as e:
        print(f"Error with {player_side} client: {e}")
    finally:
        client_socket.close()

def main():
    server_ip = "127.0.0.1"
    server_port = 12321
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((server_ip, server_port))
    server.listen(2)
    
    print(f"Server listening on {server_ip}:{server_port}")
    
    clients = []
    
    # Wait for 2 clients
    while len(clients) < 2:
        client_sock, addr = server.accept()
        print(f"Accepted connection from {addr}")
        clients.append(client_sock)
        
        # Determine side
        side = "left" if len(clients) == 1 else "right"
        
        # Send initial config: screenWidth,screenHeight,playerPaddle
        # Screen size hardcoded to 640x480 as per pongClient.py default
        config = f"640,480,{side}"
        client_sock.send(config.encode())
        
        # Start thread
        thread = threading.Thread(target=client_handler, args=(client_sock, side))
        thread.start()

if __name__ == "__main__":
    main()
