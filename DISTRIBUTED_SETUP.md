# MECOS Distributed Setup Guide

This guide explains how to run MECOS in a distributed mode:
- **Server Laptop**: Hosts the LLM (Ollama) and heavy compute.
- **Main Laptop**: Runs the MECOS Agent logic, perception, and actions.

---

## 1. Server Laptop Setup (The Brain)

### Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Configure Ollama for Remote Access
By default, Ollama only listens on `localhost`. You must enable it to listen on all interfaces.

1. Edit the Ollama service configuration:
   ```bash
   sudo systemctl edit ollama.service
   ```
2. Add the following lines:
   ```ini
   [Service]
   Environment="OLLAMA_HOST=0.0.0.0"
   ```
3. Restart Ollama:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart ollama
   ```

### Pull the Model
```bash
ollama pull llama3
```

### Find the Server IP
```bash
hostname -I
# Note the IP address (e.g., 192.168.1.50)
```

---

## 2. Main Laptop Setup (The Body)

### Install MECOS
```bash
git clone https://github.com/0ssy/MECOS.git
cd MECOS
pip install -r requirements.txt
```

### Configure Connection
Edit `config.py` or set the `SERVER_IP` environment variable:
```bash
export SERVER_IP=192.168.1.50  # Replace with your server's IP
```

### Run MECOS
```bash
python main.py
```

---

## 3. Why This Works
- **Offloaded Compute**: Your main laptop's CPU/GPU stays free for your work.
- **Local Privacy**: Data stays on your local network, never hitting the cloud.
- **Persistent Memory**: The server laptop can keep the vector database and learning state alive even if you close your main laptop.

---

## 4. Troubleshooting
- **Firewall**: Ensure port `11434` is open on the server laptop.
  ```bash
  sudo ufw allow 11434/tcp
  ```
- **Ping**: Ensure your main laptop can ping the server laptop.
  ```bash
  ping 192.168.1.50
  ```
