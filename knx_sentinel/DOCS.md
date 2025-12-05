# KNX Sentinel Technical Documentation

## Overview
KNX Sentinel is designed to provide "Edge Intelligence" for KNX networks. It decouples monitoring from automation logic, ensuring that diagnostic data is preserved even if the automation layer fails.

## Core Components

### 1. Math Kernel (`math_kernel.py`)
A pure Python implementation of statistical functions, avoiding heavy dependencies like `numpy` or `pandas`.
- **Z-Score**: $Z = (x - \mu) / \sigma$
- **Linear Regression**: Least Squares Method for slope calculation.
- **Solar Elevation**: Grena/PSA algorithm for validating light sensors.

### 2. Connectivity Layer (`ha_client.py`)
- **Protocol**: WebSocket (`ws://supervisor/core/websocket`).
- **Resilience**: Infinite retry loop with exponential backoff (1s, 2s, 4s... 60s).
- **Authentication**: Uses `SUPERVISOR_TOKEN` injected by the HA Supervisor.

### 3. Logic Core
- **BusLoadMonitor**: Atomic counter for bus traffic.
- **AnomalyEngine**: Maintains rolling buffers (`deque`) for sensors and detects statistical outliers.
- **DiagnosticsEngine**: Performs physics-based checks (e.g., Solar Elevation).

### 4. Egress Layer (`egress.py`)
- **InfluxDB**: Uses Line Protocol over HTTP/S.
- **MQTT**: Uses JSON payloads over TCP.
- **Tagging**: Enforces `client_id` and `site_id` tagging on all metrics for multi-tenant segregation.

## Data Schema

### InfluxDB Line Protocol
```text
knx_metrics,client_id=c1,site_id=s1,metric_type=bus_load telegrams_per_min=42i <timestamp>
knx_diagnostics,client_id=c1,site_id=s1,entity_id=sensor.temp,type=anomaly value=25.5,z_score=3.2 <timestamp>
```

### MQTT JSON Payload
Topic: `knx-monitor/{site_id}/{measurement}`
```json
{
  "measurement": "knx_metrics",
  "tags": {
    "client_id": "c1",
    "site_id": "s1",
    "metric_type": "bus_load"
  },
  "fields": {
    "telegrams_per_min": 42
  },
  "timestamp": 1678900000
}
```
