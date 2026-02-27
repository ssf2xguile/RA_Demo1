# Project Overview

This repository provides a lightweight environment to reproduce a specific performance / failure scenario in a connected car system.

The connected car system consists of four main components:

- **mobile_app**: Smartphone application  
- **nginx**: Reverse proxy server  
- **app_server**: Application server  
- **connected_car**: Connected car (simulator)

In addition to these, there is an **AI agent system** (`ai_agent` directory).  
The AI agent analyzes a unified log file that combines source code, configuration files, and runtime logs from each component, in order to:

- identify the root cause of failures, and  
- generate recovery (repair) plans.

Furthermore, there is a **timeout monitor application** (`timeout_monitor` directory) as an auxiliary tool to evaluate the connected car system. It visualizes the evolution of timeout counts over a period of 300 seconds from system startup as a bar chart, and can save the result as a screenshot (PNG) or a video (MP4).
---

# Directory Structure

```text
D:.
│  .gitignore
│  docker-compose.yaml
│  README.md
│
├─ai_agent
│      Dockerfile
│      main.py
│      requirements.txt
│
├─app_server
│      Dockerfile
│      main.py
│      requirements.txt
│
├─connected_car
│      Dockerfile
│      simulator.py
│
├─logs
│      app.log
│      monitor.log
│
├─mobile_app
│      Dockerfile
│      launcher.py
│      send_command.py
│
├─nginx
│      Dockerfile
│      nginx.conf
│
└─timeout_monitor
       requirements.txt
       timeout_monitor_recorder.py
       timeout_monitor_snapshot.py
```

Component mapping:

- `ai_agent`: AI agent system  
- `mobile_app`: Smartphone application  
- `nginx`: Reverse proxy server  
- `app_server`: Application server  
- `connected_car`: Connected car simulator  

---

# How to Run (Startup, Log Collection, Metrics)

This README explains:

- how to start the connected car system  
- how to collect runtime logs  
- how to fetch metrics from `app_server/main.py` via an HTTP API  

## Prerequisites

- Docker and Docker Compose are available  
- All commands are executed from the **repository root**  
- `./logs` directory exists (if not, please create it)

You will typically use up to **four terminals**:

- **Terminal 1 (cmd)**: Start / stop the connected car system  
- **Terminal 2 (cmd)**: Collect application logs into `app.log`  
- **Terminal 3 (PowerShell on Windows)**: Collect container resource usage into `monitor.log`
- **Terminal 4 (cmd)**: Fetch metrics via `curl` or run the timeout monitor application  

On Windows, note that **Terminal 4 must be PowerShell**, not Command Prompt, for the `monitor.log` script.
---

## 1. Start Connected Car System and Collect Logs

Open two terminals and move to the repository directory in each of them. Example:

```cmd
D:\>cd D:\Programming\MyPython\RA_Demo1
```

### Terminal 1 — Start the Connected Car System

Start four containers (the connected car system) in the background:

```cmd
docker compose --profile app up --build -d
```

### Terminal 2 — Start Log Collection

Record the output of all running containers into `./logs/app.log` in real time.  
Right after running the command in Terminal 1, run the following command in Terminal 2:

```cmd
docker compose --profile app logs --follow > ./logs/app.log
```

This command keeps tailing the logs, so **keep this terminal open** while the system is running.

---

## 2. Reproducing the Error Scenario

`mobile_app/send_command.py` sends an increasing number of requests over time, putting load on the system and eventually causing timeout errors.

- Watch the logs in Terminal 2 and **wait for about 2.5 minutes**.  
- You should start seeing logs like  
  `Client: ... ERROR! Operation timed out.`  
  being appended to `app.log`.  
- In total, let the system run for about **5 minutes** so that enough timeout events are captured.

---

## Stop Log Collection and Shut Down the Connected Car System

Once enough error logs have been collected, stop in the following order:

1. **Terminal 2 – Stop log collection**

   Press `Ctrl + C` to stop log monitoring in Terminal 2.  
   This flushes and finalizes writes to `./logs/app.log`.

2. **Terminal 1 – Stop and remove the connected car containers**

   ```cmd
   docker compose --profile app down
   ```

---
## [Optional] Collect Resource Usage of Containers (monitor.log)

`monitor.log` records resource usage (CPU percentage, memory usage, etc.) for each container every second.  
It is created by processing the output of `docker stats` and writing it to `./logs/monitor.log`.

Here we use **Terminal 3** and create `monitor.log` depending on your environment.

On Windows, you **must** use **PowerShell** (not Command Prompt) to run the script for `monitor.log`.

### Bash (Linux / macOS / WSL)

In Terminal 3 (bash), move to the repository root and run:

```bash
cd /path/to/RA_Demo1
while true; do
  docker stats --no-stream --format "{{.Name}}, {{.CPUPerc}}, {{.MemUsage}}" | while read line; do
    echo "$(date '+%Y/%m/%d %H:%M:%S.%2N'), $line"
  done >> ./logs/monitor.log
  sleep 1
done
```

This command also continuously collects logs, so **keep this terminal open** while monitoring.

### PowerShell (Windows)

1. Open a new **Windows PowerShell** window  
   (make sure it is PowerShell, **not** Command Prompt).
2. Move to the repository root:

   ```powershell
   cd D:\Programming\MyPython\RA_Demo1
   ```

3. Run the following script:

   ```powershell
   while($true) {
       $stats = docker stats --no-stream --format "{{.Name}}, {{.CPUPerc}}, {{.MemUsage}}"
       $timestamp = Get-Date -Format "yyyy/MM/dd HH:mm:ss.ff"
       foreach($line in $stats) {
           "$timestamp, $line" | Out-File -FilePath ./logs/monitor.log -Append -Encoding UTF8
       }
       Start-Sleep -Seconds 1
   }
   ```

This PowerShell window must also remain open while you are collecting `monitor.log`.

After you stop the connected car system (see below), press `Ctrl + C` in this PowerShell window to stop the loop and finalize `monitor.log`.

The AI agent and any later analysis may use both `app.log` and `monitor.log`, so collect both if you want full information.

---

## 3. Analysis by the AI Agent

The AI agent runs independently from the four connected car components.  
Start the AI agent (this launches the `ai_agent` container and runs `main.py`):

```cmd
docker compose --profile agent up --build
```

The agent automatically loads:

- Source code of relevant components  
  - currently: reverse proxy server and application server  
- `./logs/app.log`

Then it starts the analysis.  
When processing finishes, the following results are printed to the terminal:

- Root-cause analysis of the error  
- Concrete recovery / repair plan (including code-level suggestions)

---

## 4. [Evaluation] Retrieve Application Server Metrics via API

If you want to check the internal metrics of `app_server/main.py`, use another terminal (**Terminal 4**) while the containers are running (Terminal 1).

Example (Windows PowerShell / CMD):

```cmd
curl -s http://localhost:8080/metrics
```

**Example response**:

- timestamp  
- number of pending requests  
- total processed requests  
- total arrived requests  
- total timeouts  

```json
{
  "timestamp_epoch": 1772199286.840296,
  "timestamp_iso": "2026-02-27T13:34:46.840299+00:00",
  "uptime_s": 300.07,
  "pending": 2923,
  "done": 6168,
  "timeouts": 3932,
  "errors": 3932,
  "arrived_total": 13023,
  "session_count": 240,
  "reserved_mb": 240,
  "recent_arrivals": 179,
  "recent_timeouts": 75,
  "recent_timeout_ratio": 0.419,
  "per_session_bytes": 1048576,
  "max_sessions": 240,
  "session_ttl": 10,
  "app_queue_timeout_s": 60,
  "log_chunk_kb": 1,
  "httpx_max": 2,
  "sticky_on_timeout_s": 10
}
```

Note: For this command, the working directory of Terminal 4 does **not** matter; it can be executed from anywhere.

---

## 5. [Evaluation] Monitoring Timeout Events in Real Time

The `timeout_monitor` directory contains utilities for visualizing timeout events on the application server in real time as bar charts.

- `timeout_monitor_snapshot.py`  
  Displays a real-time bar chart and saves the 300-second timeline as a **PNG snapshot**.

- `timeout_monitor_recorder.py`  
  Displays a real-time bar chart and saves the 300-second timeline as an **MP4 video**.

These scripts are intended to be run **directly on the host OS** using Python, not inside a Docker container.

---

### 5.1 Setup: Virtual Environment for `timeout_monitor`

Assuming Python 3.x is installed.

We create a virtual environment `tm-env` inside `timeout_monitor`.

#### (1) Move to the `timeout_monitor` directory

Example:

```cmd
cd D:\Programming\MyPython\RA_Demo1\timeout_monitor
```

#### (2) Create the virtual environment (first time only)

```cmd
python -m venv tm-env
```

Now you have `timeout_monitor\tm-env`.

#### (3) Activate the virtual environment

On Windows Command Prompt:

```cmd
.\tm-env\Scripts\Activate
```

If `(tm-env)` appears in your prompt, the environment is active.

#### (4) Install dependencies

```cmd
pip install -r .\requirements.txt
```

From now on, when working in this directory:

1. `cd D:\Programming\MyPython\RA_Demo1\timeout_monitor`  
2. `.\tm-env\Scripts\Activate`

After finishing, you can deactivate the environment with:

```cmd
deactivate
```

---

### 5.2 Snapshot Monitor (Static PNG)

Use **Terminal 4** for this, and make sure the virtual environment is active.

1. Ensure the connected car system is running (containers started in Terminal 1).  
2. Run:

   ```cmd
   python timeout_monitor_snapshot.py
   ```

3. After around 2.5 minutes, a bar chart showing the evolution of timeouts appears.  
4. When you close the window, the program terminates and a static image file (e.g., `timeout_graph.png`) is saved in the same directory.

---

### 5.3 Recorder Monitor (MP4 Video)

Again, use Terminal 4 and ensure `tm-env` is active.

1. Ensure the connected car system is running (containers started in Terminal 1).  
2. Run:

   ```cmd
   python timeout_monitor_recorder.py
   ```

3. A graph window appears, and timeout counts are recorded for 300 seconds.  
4. When recording finishes (or when you close the window), the program terminates and an MP4 video (e.g., `RA_plan1.mp4`) is saved in the same directory.

---

### 5.4 Connection Between Monitor and API

The monitor scripts periodically fetch metrics from the application server’s metrics API. For example:

```python
API_URL = "http://localhost:8080/metrics"
```

If you change the port or path of the metrics endpoint, make sure to update `API_URL` in both:

- `timeout_monitor_snapshot.py`  
- `timeout_monitor_recorder.py`  

so that they continue to point to the correct endpoint.