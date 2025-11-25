# =================================================================================================
# Contributing Authors:	    Ehsanullah Dehzad, Fatima Fayazi, David Salas
# Email Addresses:          ede274@uky.edu, ffa241@uky.edu, davidsalas@uky.edu
# Date:                     Nov 25, 2025
# Purpose:                  This is the game client for multiplayer Pong. It connects to the server,
#                           renders the game using pygame, handles user input, and synchronizes
#                           game state with the server. The left player runs authoritative physics.
# Misc:                     Uses non-blocking sockets (0.01s timeout) to prevent game freezing.
#                           Tkinter GUI for initial connection. pygame for game rendering and audio.
# =================================================================================================

import pygame
import tkinter as tk
import sys
import socket

from assets.code.helperCode import *

# This is the main game loop.  For the most part, you will not need to modify this.  The sections
# where you should add to the code are marked.  Feel free to change any part of this project
# to suit your needs.
def playGame(screenWidth:int, screenHeight:int, playerPaddle:str, client:socket.socket) -> None:
    
    # Pygame inits
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.init()

    # Constants
    WHITE = (255,255,255)
    clock = pygame.time.Clock()
    scoreFont = pygame.font.Font("./assets/fonts/pong-score.ttf", 32)
    winFont = pygame.font.Font("./assets/fonts/visitor.ttf", 48)
    pointSound = pygame.mixer.Sound("./assets/sounds/point.wav")
    bounceSound = pygame.mixer.Sound("./assets/sounds/bounce.wav")

    # Display objects
    screen = pygame.display.set_mode((screenWidth, screenHeight))
    winMessage = pygame.Rect(0,0,0,0)
    topWall = pygame.Rect(-10,0,screenWidth+20, 10)
    bottomWall = pygame.Rect(-10, screenHeight-10, screenWidth+20, 10)
    centerLine = []
    for i in range(0, screenHeight, 10):
        centerLine.append(pygame.Rect((screenWidth/2)-5,i,5,5))

    # Paddle properties and init
    paddleHeight = 50
    paddleWidth = 10
    paddleStartPosY = (screenHeight/2)-(paddleHeight/2)
    leftPaddle = Paddle(pygame.Rect(10,paddleStartPosY, paddleWidth, paddleHeight))
    rightPaddle = Paddle(pygame.Rect(screenWidth-20, paddleStartPosY, paddleWidth, paddleHeight))

    ball = Ball(pygame.Rect(screenWidth/2, screenHeight/2, 5, 5), -5, 0)

    # Left player drives the core physics to give the server a single authority
    isBallAuthority = playerPaddle == "left"

    if playerPaddle == "left":
        opponentPaddleObj = rightPaddle
        playerPaddleObj = leftPaddle
    else:
        opponentPaddleObj = leftPaddle
        playerPaddleObj = rightPaddle

    lScore = 0
    rScore = 0

    sync = 0
    lastBallDX = 0
    lastBallDY = 0

    # Set socket to non-blocking mode with a small timeout to prevent game freeze
    client.settimeout(0.01)

    while True:
        # Wiping the screen
        screen.fill((0,0,0))

        # Getting keypress events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    playerPaddleObj.moving = "down"

                elif event.key == pygame.K_UP:
                    playerPaddleObj.moving = "up"

            elif event.type == pygame.KEYUP:
                playerPaddleObj.moving = ""

        # ==================================================================================
        # AUTHORITATIVE PHYSICS SECTION (Left Player Only)
        # Only the left client runs this code to compute game physics
        # This prevents desync issues from multiple clients calculating different results
        # ==================================================================================
        if isBallAuthority and lScore <= 4 and rScore <= 4:
            # Update ball position based on its velocity
            ball.updatePos()
            sync += 1  # Increment sync counter on every frame update

            # Top wall collision detection
            if ball.rect.top <= topWall.bottom:
                ball.rect.top = topWall.bottom  # Prevent ball from going through wall
                ball.hitWall()  # Reverse vertical velocity
                bounceSound.play()
                sync += 1  # Increment sync on collision event

            # Bottom wall collision detection
            if ball.rect.bottom >= bottomWall.top:
                ball.rect.bottom = bottomWall.top
                ball.hitWall()
                bounceSound.play()
                sync += 1

            # Left paddle collision (check xVel < 0 to ensure ball is moving left)
            if ball.rect.colliderect(leftPaddle.rect) and ball.xVel < 0:
                ball.rect.left = leftPaddle.rect.right  # Position ball at paddle edge
                ball.hitPaddle(leftPaddle.rect.centery)  # Bounce with angle based on hit position
                bounceSound.play()
                sync += 1

            # Right paddle collision (check xVel > 0 to ensure ball is moving right)
            if ball.rect.colliderect(rightPaddle.rect) and ball.xVel > 0:
                ball.rect.right = rightPaddle.rect.left
                ball.hitPaddle(rightPaddle.rect.centery)
                bounceSound.play()
                sync += 1

            # Left side scoring (right player scores)
            if ball.rect.left <= 0:
                rScore += 1
                pointSound.play()
                ball.reset("right")  # Reset ball to move toward right player
                lastBallDX = 0  # Reset delta tracking
                lastBallDY = 0
                sync += 1

            # Right side scoring (left player scores)
            if ball.rect.right >= screenWidth:
                lScore += 1
                pointSound.play()
                ball.reset("left")  # Reset ball to move toward left player
                lastBallDX = 0
                lastBallDY = 0
                sync += 1

        # Store ball position before server update for delta calculation
        # Used by right client to detect bounces for sound effects
        oldBallX = ball.rect.x
        oldBallY = ball.rect.y

        # =========================================================================================
        # CLIENT-SERVER COMMUNICATION SECTION
        # Send local state to server and receive authoritative game state
        # Protocol: CSV format with 6 fields
        # Send: paddleY,ballX,ballY,lScore,rScore,sync
        # Receive: oppPaddleY,ballX,ballY,lScore,rScore,sync
        # =========================================================================================
        
        try:
            # ===== SEND TO SERVER =====
            # Transmit our current game state to the server
            # The server will relay our paddle position to the opponent
            # and synchronize the ball/score state across both clients
            msg = f"{playerPaddleObj.rect.y},{ball.rect.x},{ball.rect.y},{lScore},{rScore},{sync}"
            client.send(msg.encode())  # Encode string to bytes for transmission
            
            # ===== RECEIVE FROM SERVER =====
            # Get the synchronized game state from the server
            # Server sends: opponent's paddle Y, authoritative ball position, scores, and sync counter
            try:
                response = client.recv(1024).decode()  # Receive up to 1024 bytes and decode
                parts = response.split(',')  # Parse CSV format
                
                # Validate we received all 6 expected fields
                if len(parts) == 6:
                    # Parse the server response into individual variables
                    oppPaddleY = float(parts[0])      # Opponent's paddle Y position
                    serverBallX = float(parts[1])     # Authoritative ball X position
                    serverBallY = float(parts[2])     # Authoritative ball Y position
                    serverLScore = int(parts[3])      # Left player score
                    serverRScore = int(parts[4])      # Right player score
                    serverSync = int(parts[5])        # Server's sync counter
                    
                    # ===== UPDATE LOCAL STATE FROM SERVER =====
                    # Server is authoritative for all game state
                    
                    # Update opponent paddle position (server relays this from the other client)
                    opponentPaddleObj.rect.y = oppPaddleY
                    
                    # Detect if a point was scored (for sound effect on right client)
                    scored = serverLScore > lScore or serverRScore > rScore
                    if scored and not isBallAuthority:
                        pointSound.play()  # Right client plays point sound when score changes

                    # Calculate ball movement delta for bounce detection
                    newDX = serverBallX - oldBallX
                    newDY = serverBallY - oldBallY

                    # Update ball position to server's authoritative position
                    ball.rect.x = serverBallX
                    ball.rect.y = serverBallY

                    # Right client: Detect bounces by checking for direction changes
                    # (Left client already plays sounds when computing physics)
                    if not isBallAuthority and not scored:
                        # Detect horizontal direction change (paddle bounce)
                        if (lastBallDX > 0 and newDX < 0) or (lastBallDX < 0 and newDX > 0):
                            bounceSound.play()
                        # Detect vertical direction change (wall bounce)
                        elif (lastBallDY > 0 and newDY < 0) or (lastBallDY < 0 and newDY > 0):
                            bounceSound.play()
                        lastBallDX = newDX  # Store for next frame comparison
                        lastBallDY = newDY
                    else:
                        # Reset delta tracking after scoring or if we're the authority
                        lastBallDX = 0
                        lastBallDY = 0

                    # Update local scores and sync counter from server
                    lScore = serverLScore
                    rScore = serverRScore
                    sync = serverSync
            except socket.timeout:
                # No data received this frame - continue with local state
                # This is normal behavior due to non-blocking socket
                pass
            except socket.error as e:
                # Socket error indicates connection problem - exit game loop
                print(f"Socket error: {e}")
                break
                    
        except Exception as e:
            # Catch-all for unexpected errors during server communication
            print(f"Error communicating with server: {e}")
            break
            
        # =========================================================================================

        # ===== PADDLE MOVEMENT =====
        # Update paddle positions based on their movement state
        # Boundary checking prevents paddles from moving off-screen
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            if paddle.moving == "down":
                # Check bottom boundary (leave 10px margin for wall)
                if paddle.rect.bottomleft[1] < screenHeight-10:
                    paddle.rect.y += paddle.speed
            elif paddle.moving == "up":
                # Check top boundary (leave 10px margin for wall)
                if paddle.rect.topleft[1] > 10:
                    paddle.rect.y -= paddle.speed

        # ===== GAME OVER CHECK =====
        # First player to reach 5 points wins
        if lScore > 4 or rScore > 4:
            winText = "Player 1 Wins! " if lScore > 4 else "Player 2 Wins! "
            textSurface = winFont.render(winText, False, WHITE, (0,0,0))
            textRect = textSurface.get_rect()
            textRect.center = ((screenWidth/2), screenHeight/2)
            winMessage = screen.blit(textSurface, textRect)
        else:
            # ===== BALL RENDERING =====
            # Ball position comes from server (authoritative)
            # Left client: Renders its own computed position (which it sent to server)
            # Right client: Renders the position received from server
            # This ensures both clients display synchronized ball movement
            pygame.draw.rect(screen, WHITE, ball)

        # ===== RENDER ALL GAME ELEMENTS =====
        # Draw the dotted center line
        for i in centerLine:
            pygame.draw.rect(screen, WHITE, i)
        
        # Draw both paddles at their current positions
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            pygame.draw.rect(screen, WHITE, paddle)

        # Draw walls
        pygame.draw.rect(screen, WHITE, topWall)
        pygame.draw.rect(screen, WHITE, bottomWall)
        
        # Update score display
        scoreRect = updateScore(lScore, rScore, screen, WHITE, scoreFont)
        
        # Update only the regions that changed (more efficient than full screen update)
        pygame.display.update([topWall, bottomWall, ball, leftPaddle, rightPaddle, scoreRect, winMessage])
        
        # Cap framerate at 60 FPS for consistent game speed
        clock.tick(60)
        # =========================================================================================
        # End of main game loop




# This is where you will connect to the server to get the info required to call the game loop.  Mainly
# the screen width, height and player paddle (either "left" or "right")
# If you want to hard code the screen's dimensions into the code, that's fine, but you will need to know
# which client is which
def joinServer(ip:str, port:str, errorLabel:tk.Label, app:tk.Tk) -> None:
    """
    Connects to the game server and initiates the game session.
    Called when the user clicks the Join button in the connection GUI.
    
    Args:
        ip (str): IP address of the server to connect to (e.g., "127.0.0.1")
        port (str): Port number the server is listening on (e.g., "5555")
        errorLabel (tk.Label): Tkinter label widget for displaying status/error messages
        app (tk.Tk): Tkinter window object to be closed once game starts
    
    Connection Protocol:
        1. Client connects via TCP socket
        2. Server sends: "screenWidth,screenHeight,playerSide" (e.g., "640,480,left")
        3. Client parses this and starts the game with assigned side
    """
    try:
        # ===== SOCKET INITIALIZATION =====
        # Create TCP socket (SOCK_STREAM) with IPv4 addressing (AF_INET)
        # TCP is used for reliable, ordered delivery of game state
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip, int(port)))  # Establish connection to server

        # ===== INITIAL HANDSHAKE =====
        # Receive configuration from server to determine our role in the game
        # Server assigns "left" or "right" based on connection order
        data = client.recv(1024).decode()  # Receive and decode configuration string
        parts = data.split(',')  # Parse CSV format: [width, height, side]480", "left"]
        
        # Extract configuration values
        screenWidth = int(parts[0])   # Game window width in pixels
        screenHeight = int(parts[1])  # Game window height in pixels
        playerPaddle = parts[2]       # Our assigned side: "left" or "right"

        # Update UI to show successful connection and assigned side
        errorLabel.config(text=f"Connected! Playing as {playerPaddle}")
        errorLabel.update()  # Force GUI update before hiding window

        # ===== START GAME =====
        # Hide connection window and launch game with server-provided configuration
        app.withdraw()  # Hide the tkinter window (keeps it in memory)
        playGame(screenWidth, screenHeight, playerPaddle, client)  # Enter main game loop
        app.quit()  # Destroy the tkinter window after game ends
        
    except Exception as e:
        # Display error message if connection fails
        errorLabel.config(text=f"Error: {e}")
        errorLabel.update()


# This displays the opening screen, you don't need to edit this (but may if you like)
def startScreen() -> None:
    app = tk.Tk()
    app.title("Server Info")

    image = tk.PhotoImage(file="./assets/images/logo.png")

    titleLabel = tk.Label(image=image)
    titleLabel.grid(column=0, row=0, columnspan=2)

    ipLabel = tk.Label(text="Server IP:")
    ipLabel.grid(column=0, row=1, sticky="W", padx=8)

    ipEntry = tk.Entry(app)
    ipEntry.grid(column=1, row=1)

    portLabel = tk.Label(text="Server Port:")
    portLabel.grid(column=0, row=2, sticky="W", padx=8)

    portEntry = tk.Entry(app)
    portEntry.grid(column=1, row=2)

    errorLabel = tk.Label(text="")
    errorLabel.grid(column=0, row=4, columnspan=2)

    joinButton = tk.Button(text="Join", command=lambda: joinServer(ipEntry.get(), portEntry.get(), errorLabel, app))
    joinButton.grid(column=0, row=3, columnspan=2)

    app.mainloop()

if __name__ == "__main__":
    startScreen()
    
    # Uncomment the line below if you want to play the game without a server to see how it should work
    # the startScreen() function should call playGame with the arguments given to it by the server this is
    # here for demo purposes only
    # playGame(640, 480,"left",socket.socket(socket.AF_INET, socket.SOCK_STREAM))