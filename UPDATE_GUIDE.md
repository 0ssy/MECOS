# MECOS Server Update Guide

Follow these steps to apply the latest MECOS updates (Autonomous Dreaming & Custom LLM) to your server.

---

## 1. Transfer the Update
1.  Download the latest `MECOS_autonomous_v1.1.zip` to your main laptop.
2.  Transfer it to your server laptop (via SCP, USB, or shared folder).
    ```bash
    scp MECOS_autonomous_v1.1.zip user@server_ip:/home/user/
    ```

---

## 2. Apply the Update
On the **Server Laptop**:
1.  Stop the current MECOS service:
    ```bash
    sudo systemctl stop mecos
    ```
2.  Backup your current data (optional but recommended):
    ```bash
    cp -r ~/MECOS ~/MECOS_backup_$(date +%F)
    ```
3.  Extract the new version over the old one:
    ```bash
    unzip -o MECOS_autonomous_v1.1.zip -d ~/MECOS
    ```
4.  Update dependencies:
    ```bash
    cd ~/MECOS
    source venv/bin/activate
    pip install -r requirements.txt
    ```

---

## 3. Launch 'Away Mode'
To have MECOS run autonomously while you are at work or school:

### Manual Launch
```bash
python main.py away
```

### Systemd Update (Recommended)
Update your service file to use the `away` argument:
1.  `sudo nano /etc/systemd/system/mecos.service`
2.  Change the `ExecStart` line:
    ```ini
    ExecStart=/home/your_username/MECOS/venv/bin/python main.py away
    ```
3.  Reload and restart:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl restart mecos
    ```

---

## 4. Verify Autonomous Operation
Check the logs to see MECOS dreaming and setting its own goals:
```bash
tail -f logs/engine.log | grep "Dreaming"
```
You should see entries like:
- `MECOS is dreaming of new goals...`
- `MECOS has set a new autonomous goal: Research and implement...`
