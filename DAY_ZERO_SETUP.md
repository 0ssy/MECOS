# MECOS: Day Zero Setup Guide

This guide will take you from a fresh laptop-server to a fully autonomous, distributed MECOS system.

---

## Part 1: The Server Laptop (The Brain)
*This machine does the heavy thinking.*

### 1. Install Linux (If not already done)
We recommend **Ubuntu 22.04 LTS**.

### 2. Install Ollama (The LLM Engine)
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 3. Enable Remote Access
Allow your main laptop to talk to the server:
1.  `sudo systemctl edit ollama.service`
2.  Add these lines:
    ```ini
    [Service]
    Environment="OLLAMA_HOST=0.0.0.0"
    ```
3.  Restart:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    ```

### 4. Pull the MECOS Base Model
```bash
ollama pull llama3
```

### 5. Find the Server IP
```bash
hostname -I
# Note this IP (e.g., 192.168.1.50)
```

---

## Part 2: The Main Laptop (The Body)
*This machine runs the agent and interacts with your work.*

### 1. Install Python & Git
Ensure you have Python 3.10+ installed.

### 2. Setup MECOS
1.  Extract the `MECOS_DayZero_v1.2.zip` file.
2.  Open a terminal in the `MECOS` folder.
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### 3. Link to the Server
Open `config.py` and change the `SERVER_IP`:
```python
SERVER_IP: str = "192.168.1.50"  # Use your Server IP from Part 1
```

---

## Part 3: Launching MECOS

### Mode A: Interactive (Talk to MECOS)
```bash
python main.py
```

### Mode B: Away Mode (Autonomous Dreaming)
Run this when you go to work or school. MECOS will set its own goals and learn.
```bash
python main.py away
```

---

## Part 4: Tips for Success
- **Keep the Server Plugged In**: LLM inference uses significant power.
- **Lid Switch**: On the server, run `sudo nano /etc/systemd/logind.conf` and set `HandleLidSwitch=ignore` so it doesn't sleep when closed.
- **Logs**: Watch MECOS think in real-time: `tail -f logs/engine.log`.
