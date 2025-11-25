# =================================================================================================
# Contributing Authors:	    <Anyone who touched the code>
# Email Addresses:          <Your uky.edu email addresses>
# Date:                     <The date the file was last edited>
# Purpose:                  <How this file contributes to the project>
# Misc:                     <Not Required.  Anything else you might want to include>
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

        # Allow a single client to push authoritative physics to the server
        if isBallAuthority and lScore <= 4 and rScore <= 4:
            ball.updatePos()
            sync += 1

            if ball.rect.top <= topWall.bottom:
                ball.rect.top = topWall.bottom
                ball.hitWall()
                bounceSound.play()
                sync += 1

            if ball.rect.bottom >= bottomWall.top:
                ball.rect.bottom = bottomWall.top
                ball.hitWall()
                bounceSound.play()
                sync += 1

            if ball.rect.colliderect(leftPaddle.rect) and ball.xVel < 0:
                ball.rect.left = leftPaddle.rect.right
                ball.hitPaddle(leftPaddle.rect.centery)
                bounceSound.play()
                sync += 1

            if ball.rect.colliderect(rightPaddle.rect) and ball.xVel > 0:
                ball.rect.right = rightPaddle.rect.left
                ball.hitPaddle(rightPaddle.rect.centery)
                bounceSound.play()
                sync += 1

            if ball.rect.left <= 0:
                rScore += 1
                pointSound.play()
                ball.reset("right")
                lastBallDX = 0
                lastBallDY = 0
                sync += 1

            if ball.rect.right >= screenWidth:
                lScore += 1
                pointSound.play()
                ball.reset("left")
                lastBallDX = 0
                lastBallDY = 0
                sync += 1

        oldBallX = ball.rect.x
        oldBallY = ball.rect.y

        # =========================================================================================
        # Your code here to send an update to the server on your paddle's information,
        # where the ball is and the current score.
        # Feel free to change when the score is updated to suit your needs/requirements
        
        try:
            # Send the full six-field payload the server expects:
            # paddleY,ballX,ballY,lScore,rScore,sync
            msg = f"{playerPaddleObj.rect.y},{ball.rect.x},{ball.rect.y},{lScore},{rScore},{sync}"
            client.send(msg.encode())
            
            # Receive authoritative game state from server
            # Format: oppPaddleY,ballX,ballY,lScore,rScore,sync
            try:
                response = client.recv(1024).decode()
                parts = response.split(',')
                
                if len(parts) == 6:
                    # Parse the server response
                    oppPaddleY = float(parts[0])
                    serverBallX = float(parts[1])
                    serverBallY = float(parts[2])
                    serverLScore = int(parts[3])
                    serverRScore = int(parts[4])
                    serverSync = int(parts[5])
                    
                    # Update all state from server (server is authoritative)
                    opponentPaddleObj.rect.y = oppPaddleY
                    scored = serverLScore > lScore or serverRScore > rScore
                    if scored and not isBallAuthority:
                        pointSound.play()

                    newDX = serverBallX - oldBallX
                    newDY = serverBallY - oldBallY

                    ball.rect.x = serverBallX
                    ball.rect.y = serverBallY

                    if not isBallAuthority and not scored:
                        if (lastBallDX > 0 and newDX < 0) or (lastBallDX < 0 and newDX > 0):
                            bounceSound.play()
                        elif (lastBallDY > 0 and newDY < 0) or (lastBallDY < 0 and newDY > 0):
                            bounceSound.play()
                        lastBallDX = newDX
                        lastBallDY = newDY
                    else:
                        lastBallDX = 0
                        lastBallDY = 0

                    lScore = serverLScore
                    rScore = serverRScore
                    sync = serverSync
            except socket.timeout:
                # No data received this frame, continue with local state
                pass
            except socket.error as e:
                print(f"Socket error: {e}")
                break
                    
        except Exception as e:
            print(f"Error communicating with server: {e}")
            break
            
        # =========================================================================================

        # Update the player paddle and opponent paddle's location on the screen
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            if paddle.moving == "down":
                if paddle.rect.bottomleft[1] < screenHeight-10:
                    paddle.rect.y += paddle.speed
            elif paddle.moving == "up":
                if paddle.rect.topleft[1] > 10:
                    paddle.rect.y -= paddle.speed

        # If the game is over, display the win message
        if lScore > 4 or rScore > 4:
            winText = "Player 1 Wins! " if lScore > 4 else "Player 2 Wins! "
            textSurface = winFont.render(winText, False, WHITE, (0,0,0))
            textRect = textSurface.get_rect()
            textRect.center = ((screenWidth/2), screenHeight/2)
            winMessage = screen.blit(textSurface, textRect)
        else:
            # Ball position is now controlled by the server
            # We just render it at the position the server tells us
            # Note: We could add client-side prediction here for smoother movement,
            # but for now we trust the server completely for simplicity
            
            # Optional: Play sounds based on ball position changes
            # (This is a simple heuristic - could be improved with velocity info from server)
            
            pygame.draw.rect(screen, WHITE, ball)
            # ==== End Ball Logic =================================================================

        # Drawing the dotted line in the center
        for i in centerLine:
            pygame.draw.rect(screen, WHITE, i)
        
        # Drawing the player's new location
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            pygame.draw.rect(screen, WHITE, paddle)

        pygame.draw.rect(screen, WHITE, topWall)
        pygame.draw.rect(screen, WHITE, bottomWall)
        scoreRect = updateScore(lScore, rScore, screen, WHITE, scoreFont)
        pygame.display.update([topWall, bottomWall, ball, leftPaddle, rightPaddle, scoreRect, winMessage])
        clock.tick(60)
        
        # Sync counter is now managed by the server
        # The server increments it on significant events (collisions, scoring)
        # and we receive the updated value in each server response
        # =========================================================================================




# This is where you will connect to the server to get the info required to call the game loop.  Mainly
# the screen width, height and player paddle (either "left" or "right")
# If you want to hard code the screen's dimensions into the code, that's fine, but you will need to know
# which client is which
def joinServer(ip:str, port:str, errorLabel:tk.Label, app:tk.Tk) -> None:
    # Purpose:      This method is fired when the join button is clicked
    # Arguments:
    # ip            A string holding the IP address of the server
    # port          A string holding the port the server is using
    # errorLabel    A tk label widget, modify it's text to display messages to the user (example below)
    # app           The tk window object, needed to kill the window
    
    # Create a socket and connect to the server
    # You don't have to use SOCK_STREAM, use what you think is best
    try:
        # Initialize the socket using IPv4 (AF_INET) and TCP (SOCK_STREAM)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip, int(port)))

        # Get the required information from your server (screen width, height & player paddle, "left or "right)
        # This initial handshake determines which side we are playing on.
        # Format: screenWidth,screenHeight,playerPaddle
        data = client.recv(1024).decode() # Example: "640,480,left"
        parts = data.split(',') # Example: [640, 480, "left"]
        
        screenWidth = int(parts[0])
        screenHeight = int(parts[1])
        playerPaddle = parts[2]

        # If you have messages you'd like to show the user use the errorLabel widget like so
        errorLabel.config(text=f"Connected! Playing as {playerPaddle}")
        # You may or may not need to call this, depending on how many times you update the label
        errorLabel.update()     

        # Close this window and start the game with the info passed to you from the server
        app.withdraw()     # Hides the window (we'll kill it later)
        playGame(screenWidth, screenHeight, playerPaddle, client)  # User will be either left or right paddle
        app.quit()         # Kills the window
        
    except Exception as e:
        errorLabel.config(text=f"Error: {e}")
        errorLabel.update()


# This displays the opening screen, you don't need to edit this (but may if you like)
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