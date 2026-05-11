# MECOS Home-Server Deployment Guide

This guide explains how to deploy MECOS on your laptop-turned-server for 24/7 autonomous operation.

---

## 1. Prerequisites

### Hardware
- **CPU**: 4+ cores recommended
- **RAM**: 8GB+ (16GB+ preferred for local LLMs)
- **Storage**: 50GB+ SSD recommended

### Software
- **OS**: Ubuntu 22.04+ (or any modern Linux distro)
- **Python**: 3.10+
- **Docker**: (Optional, for Phase 4 sandboxing)

---

## 2. Setting Up the "Brain" (Local LLM)

MECOS is configured to use an OpenAI-compatible local server. We recommend **Ollama** for its ease of use on Linux.

### Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Pull the Default Model
```bash
ollama pull llama3
```

### Verify the Server
Ollama runs on port `11434` by default. MECOS will connect to `http://localhost:11434/v1`.

---

## 3. Installing MECOS

### Clone and Setup
```bash
git clone https://github.com/0ssy/MECOS.git
cd MECOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration
Edit `config.py` or create a `.env` file to match your hardware:
```env
LOCAL_LLM_URL=http://localhost:11434/v1
DEFAULT_MODEL=llama3
LOW_RESOURCE_MODE=True
```

---

## 4. 24/7 Operation (Systemd)

To ensure MECOS starts automatically and stays running, set it up as a systemd service.

### Create the Service File
```bash
sudo nano /etc/systemd/system/mecos.service
```

### Paste the following (adjust paths):
```ini
[Unit]
Description=MECOS Autonomous Engine
After=network.target

[Service]
User=your_username
WorkingDirectory=/home/your_username/MECOS
ExecStart=/home/your_username/MECOS/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable mecos
sudo systemctl start mecos
```

---

## 5. Monitoring

### View Logs
```bash
tail -f logs/engine.log
```

### Check System Status
```bash
sudo systemctl status mecos
```

---

## 6. Laptop-Specific Tips

- **Lid Closing**: Ensure the laptop doesn't sleep when the lid is closed.
  - Edit `/etc/systemd/logind.conf`
  - Set `HandleLidSwitch=ignore`
  - Run `sudo systemctl restart systemd-logind`
- **Power Management**: Keep the laptop plugged in. Use `powertop` to monitor consumption if needed.
- **Thermal Management**: Ensure good airflow, as local LLM inference can be CPU/GPU intensive.
