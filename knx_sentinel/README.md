# KNX Sentinel

KNX Sentinel is a robust, lightweight, and autonomous diagnostics agent for KNX installations, designed to run as a Home Assistant Add-on.

## Features
- **Bus Load Monitoring**: Tracks telegram traffic per minute.
- **Anomaly Detection**: Uses Z-Score statistical analysis to detect outliers in sensor data (Temperature, Voltage, etc.).
- **Diagnostics**: Validates sensor health (e.g., Solar Elevation vs Lux).
- **Dual-Mode Egress**: Supports both InfluxDB (Serverless) and MQTT (Self-Hosted) backends.
- **Resilient**: Implements Dead Man's Switch and exponential backoff for connection reliability.

## Installation
1. Add this repository to your Home Assistant Add-on Store.
2. Install "KNX Sentinel".
3. Configure the Add-on via the "Configuration" tab.

## Configuration
### Options
| Option | Description | Example |
| :--- | :--- | :--- |
| `client_id` | Unique Customer ID | `customer_001` |
| `site_id` | Unique Site ID | `site_nyc_01` |
| `mode` | Egress mode (`influxdb_cloud` or `mqtt`) | `influxdb_cloud` |

### InfluxDB Configuration
Required if `mode` is `influxdb_cloud`.
- `host`: URL of InfluxDB instance.
- `token`: Auth token.
- `org`: Organization name.
- `bucket`: Target bucket.

### MQTT Configuration
Required if `mode` is `mqtt`.
- `broker`: IP or Hostname of MQTT broker.
- `port`: Port (default 1883).
- `topic_prefix`: Root topic (default `knx-monitor`).

## Architecture
The agent runs as a standalone Docker container. It connects to the Home Assistant Core via WebSocket to listen for `knx_event` traffic. It processes data locally using a pure Python Math Kernel and pushes normalized metrics to the configured backend.
