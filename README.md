# Pong Multiplayer Game

A multiplayer Pong game implemented in Python using `pygame` for the game engine and standard `socket` libraries for networking.

## Architecture

This project follows a client-server model where:

- The **server** manages the game state and synchronizes two clients
- **Clients** handle rendering, user input, and local simulation
- Communication uses TCP sockets with a custom CSV-style protocol

## Prerequisites

- Python 3.x
- pip (Python package manager)

## Installation

1. Clone or download this repository. If downloaded, unzip it.

2. Install the required dependencies:

```bash
pip3 install -r requirements.txt
```

## How to Run

### Step 1: Start the Server

Open a terminal and run:

```bash
python3 pong/pongServer.py
```

The server will start listening on `127.0.0.1:5555` (localhost) and wait for two clients to connect.

### Step 2: Start the First Client

Open a **second terminal** and run:

```bash
python3 pong/pongClient.py
```

A GUI window will appear asking for connection details:

- **IP Address**: Enter `127.0.0.1` (for local testing)
- **Port**: Enter `5555` (default server port)
- Click **Join**

This client will be assigned the **left paddle**.

### Step 3: Start the Second Client

Open a **third terminal** and run:

```bash
python3 pong/pongClient.py
```

Enter the same connection details (`127.0.0.1` and `5555`).

This client will be assigned the **right paddle**.

### Step 4: Play!

Once both clients are connected, the game will start automatically:

- Use `↑` (up) and `↓` (down) to move your paddle
- First to score 5 wins!

## Project Structure

```
.
├── pong/
│   ├── pongClient.py          # Client game logic and rendering
│   ├── pongServer.py          # Server for state management
│   └── assets/
│       ├── code/
│       │   └── helperCode.py  # Shared game entities (Paddle, Ball)
│       ├── fonts/             # Game fonts
│       ├── images/            # Game images
│       └── sounds/            # Game sounds
├── requirements.txt           # Python dependencies
├── report.pdf                 # Project report
└── README.md                  # This file
```

## Troubleshooting

### Connection Issues

- Make sure the server is running before starting clients
- Verify the IP address and port match between server and clients
- Check that port 5555 is not blocked by a firewall

### Performance Issues

- Close other applications to free up resources
- The game runs at 60 FPS; lag may occur on slower systems

## Network Configuration

### Playing Over a Network (Not Local)

To play over a network instead of localhost:

1. Find the server computer's IP address:

   ```bash
   # On macOS/Linux:
   ifconfig | grep inet

   # On Windows:
   ipconfig
   ```

2. Start the server on that machine

3. Clients should enter the server's IP address (e.g., `192.168.1.100`) instead of `127.0.0.1`

4. Ensure the server's firewall allows incoming connections on port 5555
