# =================================================================================================
# Contributing Authors:	    Student Implementation
# Email Addresses:          student@uky.edu
# Date:                     November 2025
# Purpose:                  Client for multiplayer Pong game - connects to server and plays game
# Misc:                     Integrates socket communication with Pygame rendering
# =================================================================================================

import pygame
import tkinter as tk
import sys
import socket
import json
import threading

from assets.code.helperCode import *

# Global variable to store received game state from server
received_state = {
    "opponent_paddle_y": 215,
    "ball_x": 320,
    "ball_y": 240,
    "ball_xvel": -5,
    "ball_yvel": 0,
    "left_score": 0,
    "right_score": 0,
    "sync": 0
}
state_lock = threading.Lock()


# =================================================================================================
# Author: Instructor
# Purpose: Background thread to continuously receive updates from server
# Pre: client is a connected socket
# Post: Updates received_state with data from server
# =================================================================================================
def receive_from_server(client: socket.socket) -> None:
    """
    This function runs in a background thread.
    It continuously listens for messages from the server and updates received_state.
    
    Why a separate thread? 
    - The main game loop (playGame) needs to run at 60 FPS without blocking
    - Network recv() is blocking, so we handle it in a separate thread
    """
    global received_state
    buffer = ""  # Buffer to accumulate partial messages
    
    try:
        while True:
            # Receive data from server
            data = client.recv(1024).decode()
            
            if not data:
                print("[DISCONNECTED] Lost connection to server")
                break
            
            # Add to buffer (messages are delimited by newlines)
            buffer += data
            
            # Process all complete messages in buffer
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                
                try:
                    server_data = json.loads(line)
                    
                    # Update the shared state (thread-safe)
                    with state_lock:
                        received_state["opponent_paddle_y"] = server_data.get("opponent_paddle_y", received_state["opponent_paddle_y"])
                        received_state["ball_x"] = server_data.get("ball_x", received_state["ball_x"])
                        received_state["ball_y"] = server_data.get("ball_y", received_state["ball_y"])
                        received_state["ball_xvel"] = server_data.get("ball_xvel", received_state["ball_xvel"])
                        received_state["ball_yvel"] = server_data.get("ball_yvel", received_state["ball_yvel"])
                        received_state["left_score"] = server_data.get("left_score", 0)
                        received_state["right_score"] = server_data.get("right_score", 0)
                        received_state["sync"] = server_data.get("sync", 0)
                        
                except json.JSONDecodeError:
                    print(f"[ERROR] Invalid JSON received: {line}")
                    
    except Exception as e:
        print(f"[ERROR] Receive thread error: {e}")


# =================================================================================================
# Author: Original + Instructor modifications
# Purpose: Main game loop with networking integrated
# Pre: screenWidth, screenHeight, playerPaddle ("left"/"right"), and client socket are provided
# Post: Game runs until someone wins or window is closed
# =================================================================================================
def playGame(screenWidth: int, screenHeight: int, playerPaddle: str, client: socket.socket) -> None:
    
    # Pygame inits
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.init()

    # Constants
    WHITE = (255, 255, 255)
    clock = pygame.time.Clock()
    scoreFont = pygame.font.Font("./assets/fonts/pong-score.ttf", 32)
    winFont = pygame.font.Font("./assets/fonts/visitor.ttf", 48)
    pointSound = pygame.mixer.Sound("./assets/sounds/point.wav")
    bounceSound = pygame.mixer.Sound("./assets/sounds/bounce.wav")

    # Display objects
    screen = pygame.display.set_mode((screenWidth, screenHeight))
    winMessage = pygame.Rect(0, 0, 0, 0)
    topWall = pygame.Rect(-10, 0, screenWidth + 20, 10)
    bottomWall = pygame.Rect(-10, screenHeight - 10, screenWidth + 20, 10)
    centerLine = []
    for i in range(0, screenHeight, 10):
        centerLine.append(pygame.Rect((screenWidth / 2) - 5, i, 5, 5))

    # Paddle properties and init
    paddleHeight = 50
    paddleWidth = 10
    paddleStartPosY = (screenHeight / 2) - (paddleHeight / 2)
    leftPaddle = Paddle(pygame.Rect(10, paddleStartPosY, paddleWidth, paddleHeight))
    rightPaddle = Paddle(pygame.Rect(screenWidth - 20, paddleStartPosY, paddleWidth, paddleHeight))

    ball = Ball(pygame.Rect(screenWidth / 2, screenHeight / 2, 5, 5), -5, 0)

    if playerPaddle == "left":
        opponentPaddleObj = rightPaddle
        playerPaddleObj = leftPaddle
    else:
        opponentPaddleObj = leftPaddle
        playerPaddleObj = rightPaddle

    lScore = 0
    rScore = 0
    sync = 0

    # Start background thread to receive server updates
    receive_thread = threading.Thread(target=receive_from_server, args=(client,), daemon=True)
    receive_thread.start()

    while True:
        # Wiping the screen
        screen.fill((0, 0, 0))

        # Getting keypress events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                client.close()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    playerPaddleObj.moving = "down"
                elif event.key == pygame.K_UP:
                    playerPaddleObj.moving = "up"
            elif event.type == pygame.KEYUP:
                playerPaddleObj.moving = ""

        # =========================================================================================
        # NETWORKING: Send update to server
        # =========================================================================================
        try:
            # Prepare data to send to server
            client_data = {
                "paddle_y": playerPaddleObj.rect.y,
                "sync": sync,
                "ball_x": ball.rect.x,
                "ball_y": ball.rect.y,
                "ball_xvel": ball.xVel,
                "ball_yvel": ball.yVel,
                "left_score": lScore,
                "right_score": rScore
            }
            
            # Send as JSON with newline delimiter
            message = json.dumps(client_data) + "\n"
            client.send(message.encode())
            
        except Exception as e:
            print(f"[ERROR] Failed to send to server: {e}")
            pygame.quit()
            sys.exit()
        
        # =========================================================================================
        # NETWORKING: Apply received state from server
        # =========================================================================================
        with state_lock:
            # Update opponent paddle position from server
            opponentPaddleObj.rect.y = received_state["opponent_paddle_y"]
            
            # Update ball position from server (server is authoritative)
            ball.rect.x = received_state["ball_x"]
            ball.rect.y = received_state["ball_y"]
            ball.xVel = received_state["ball_xvel"]
            ball.yVel = received_state["ball_yvel"]
            
            # Update scores from server
            lScore = received_state["left_score"]
            rScore = received_state["right_score"]

        # =========================================================================================
        # Update the player paddle location on the screen
        # =========================================================================================
        if playerPaddleObj.moving == "down":
            if playerPaddleObj.rect.bottomleft[1] < screenHeight - 10:
                playerPaddleObj.rect.y += playerPaddleObj.speed
        elif playerPaddleObj.moving == "up":
            if playerPaddleObj.rect.topleft[1] > 10:
                playerPaddleObj.rect.y -= playerPaddleObj.speed

        # =========================================================================================
        # If the game is over, display the win message
        # =========================================================================================
        if lScore > 4 or rScore > 4:
            winText = "Player 1 Wins! " if lScore > 4 else "Player 2 Wins! "
            textSurface = winFont.render(winText, False, WHITE, (0, 0, 0))
            textRect = textSurface.get_rect()
            textRect.center = ((screenWidth / 2), screenHeight / 2)
            winMessage = screen.blit(textSurface, textRect)
        else:
            # ==== Ball Logic =====================================================================
            # Note: Ball physics are calculated locally but overridden by server updates
            ball.updatePos()

            # If the ball makes it past the edge of the screen, update score
            if ball.rect.x > screenWidth:
                lScore += 1
                pointSound.play()
                ball.reset(nowGoing="left")
            elif ball.rect.x < 0:
                rScore += 1
                pointSound.play()
                ball.reset(nowGoing="right")

            # If the ball hits a paddle
            if ball.rect.colliderect(playerPaddleObj.rect):
                bounceSound.play()
                ball.hitPaddle(playerPaddleObj.rect.center[1])
            elif ball.rect.colliderect(opponentPaddleObj.rect):
                bounceSound.play()
                ball.hitPaddle(opponentPaddleObj.rect.center[1])

            # If the ball hits a wall
            if ball.rect.colliderect(topWall) or ball.rect.colliderect(bottomWall):
                bounceSound.play()
                ball.hitWall()

            pygame.draw.rect(screen, WHITE, ball)
            # ==== End Ball Logic =================================================================

        # Drawing the dotted line in the center
        for i in centerLine:
            pygame.draw.rect(screen, WHITE, i)

        # Drawing the paddles
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            pygame.draw.rect(screen, WHITE, paddle)

        pygame.draw.rect(screen, WHITE, topWall)
        pygame.draw.rect(screen, WHITE, bottomWall)
        scoreRect = updateScore(lScore, rScore, screen, WHITE, scoreFont)
        pygame.display.update([topWall, bottomWall, ball, leftPaddle, rightPaddle, scoreRect, winMessage])
        clock.tick(60)

        sync += 1


# =================================================================================================
# Author: Original + Instructor modifications  
# Purpose: Connect to server and get initial game configuration
# Pre: IP and port strings from GUI, error label and app window for UI updates
# Post: If successful, closes GUI and starts game
# =================================================================================================
def joinServer(ip: str, port: str, errorLabel: tk.Label, app: tk.Tk) -> None:
    """
    This function is called when the user clicks "Join" in the GUI.
    It connects to the server, receives initial configuration, then starts the game.
    """
    
    # Validate inputs
    if not ip or not port:
        errorLabel.config(text="Please enter both IP and Port")
        errorLabel.update()
        return
    
    try:
        port_num = int(port)
    except ValueError:
        errorLabel.config(text="Port must be a number")
        errorLabel.update()
        return
    
    # Create TCP socket
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        errorLabel.config(text=f"Connecting to {ip}:{port}...")
        errorLabel.update()
        
        # Connect to server
        client.connect((ip, port_num))
        
        errorLabel.config(text="Connected! Waiting for game info...")
        errorLabel.update()
        
        # Receive initial configuration from server
        # Server sends: screen_width, screen_height, player_paddle
        data = client.recv(1024).decode()
        
        if not data:
            errorLabel.config(text="Server closed connection")
            errorLabel.update()
            return
        
        # Parse JSON response
        try:
            init_data = json.loads(data.strip())
            screenWidth = init_data["screen_width"]
            screenHeight = init_data["screen_height"]
            playerPaddle = init_data["player_paddle"]
            
            errorLabel.config(text=f"Starting game as {playerPaddle} paddle...")
            errorLabel.update()
            
            # Give user a moment to read the message
            app.after(1000)
            
            # Close GUI and start game
            app.withdraw()
            playGame(screenWidth, screenHeight, playerPaddle, client)
            app.quit()
            
        except (json.JSONDecodeError, KeyError) as e:
            errorLabel.config(text=f"Invalid server response: {e}")
            errorLabel.update()
            client.close()
            
    except ConnectionRefusedError:
        errorLabel.config(text="Connection refused. Is the server running?")
        errorLabel.update()
    except socket.timeout:
        errorLabel.config(text="Connection timed out")
        errorLabel.update()
    except Exception as e:
        errorLabel.config(text=f"Error: {str(e)}")
        errorLabel.update()


# =================================================================================================
# Author: Original (unchanged)
# Purpose: Display the initial GUI for entering server connection info
# =================================================================================================
def startScreen():
    app = tk.Tk()
    app.title("Server Info")

    image = tk.PhotoImage(file="./assets/images/logo.png")

    titleLabel = tk.Label(image=image)
    titleLabel.grid(column=0, row=0, columnspan=2)

    ipLabel = tk.Label(text="Server IP:")
    ipLabel.grid(column=0, row=1, sticky="W", padx=8)

    ipEntry = tk.Entry(app)
    ipEntry.grid(column=1, row=1)
    ipEntry.insert(0, "127.0.0.1")  # Default to localhost

    portLabel = tk.Label(text="Server Port:")
    portLabel.grid(column=0, row=2, sticky="W", padx=8)

    portEntry = tk.Entry(app)
    portEntry.grid(column=1, row=2)
    portEntry.insert(0, "5000")  # Default port

    errorLabel = tk.Label(text="")
    errorLabel.grid(column=0, row=4, columnspan=2)

    joinButton = tk.Button(text="Join", command=lambda: joinServer(ipEntry.get(), portEntry.get(), errorLabel, app))
    joinButton.grid(column=0, row=3, columnspan=2)

    app.mainloop()


if __name__ == "__main__":
    startScreen()
    
    # For testing without server, uncomment this:
    # playGame(640, 480, "left", socket.socket(socket.AF_INET, socket.SOCK_STREAM))