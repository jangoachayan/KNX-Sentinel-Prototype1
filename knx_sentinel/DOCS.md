# KNX Sentinel User Manual

Welcome to **KNX Sentinel**, an advanced diagnostics and anomaly detection agent for your KNX smart home.

## Features
-   **Bus Load Monitoring**: Tracks telegram traffic in real-time (telegrams/minute).
-   **Anomaly Detection**: Uses Z-Score statistical analysis to identify outliers in sensor data (e.g., unexpected temperature spikes).
-   **Diagnostics**: Physics-based validation for sensors (e.g., Solar Elevation vs. Lux).
-   **Dual-Mode Egress**:
    -   **InfluxDB**: Push metrics to InfluxDB Cloud or OSS (Serverless support).
    -   **MQTT**: Publish parsed telegrams and anomalies to your local broker.
-   **Resilient**: Includes "Dead Man's Switch" monitoring and exponential backoff connection logic.

---

## Installation

1.  **Add Repository**:
    -   Go to **Settings** > **Add-ons** > **Add-on Store**.
    -   Click the **three dots** (top right) > **Repositories**.
    -   Add this repository URL: `https://github.com/jangoachayan/KNX-Sentinel-Prototype1` (or your local path).
2.  **Install**:
    -   Find **KNX Sentinel** in the store.
    -   Click **Install**.
3.  **Start**:
    -   Configure the add-on (see below).
    -   Click **Start**.

---

## Configuration

Configuration is handled via the **Configuration** tab in the add-on.

### 1. Global Settings
| Option | Description | Default |
| :--- | :--- | :--- |
| `client_id` | Unique identifier for this customer/gateway. | `customer_001` |
| `site_id` | Unique identifier for this physical site. | `site_nyc_01` |
| `mode` | Egress mode: `influxdb_cloud` or `mqtt`. | `influxdb_cloud` |
| `autodiscovery` | Validates sensor data automatically using heuristics. | `true` |

### 2. Egress Options

#### InfluxDB (Cloud or OSS)
Required if `mode` is set to `influxdb_cloud`.
-   **host**: Full URL to your InfluxDB instance (e.g., `https://us-east-1-1.aws.cloud2.influxdata.com`).
-   **token**: Your API Token with write access.
-   **org**: Your Organization name.
-   **bucket**: The target bucket for metrics.

#### MQTT (Local Integration)
Required if `mode` is set to `mqtt`.
-   **broker**: IP address or hostname of your MQTT broker (e.g., `core-mosquitto` or `192.168.1.100`).
-   **port**: MQTT Port (default `1883`).
-   **topic_prefix**: Root topic for published messages (default `knx-monitor`).

### 3. Anomaly Detection
Enable or disable the intelligent monitoring engine.
-   **enabled**: `true` or `false`.
-   **sensors**: (Optional) List of specific entities to monitor with custom thresholds.

```yaml
anomaly_detection:
  enabled: true
  sensors:
    - entity_id: sensor.kitchen_temp
      method: z_score
      threshold: 3.0
```

---

## Data Visualization

### InfluxDB Data Schema
Metrics are written to the `knx_metrics` and `knx_diagnostics` measurements.
-   **Tags**: `client_id`, `site_id`, `metric_type`, `entity_id`.
-   **Fields**: `telegrams_per_min`, `value`, `z_score`.

### MQTT Topics
Data is published to `knx-monitor/{site_id}/{measurement}`.
-   **Payload**: JSON object containing tags, fields, and timestamp.

---

## Troubleshooting

### "Unknown Error" during Installation
If the installation fails with an unknown error, ensure you are running a supported architecture (aarch64/amd64) and that your Home Assistant Supervisor is up to date. We use `ghcr.io/home-assistant/{arch}-base-python:3.12-alpine3.20` base images.

### Check Logs
1.  Go to the **Log** tab in the add-on.
2.  Look for "Connected to Home Assistant" to confirm successful startup.
3.  Errors regarding "Connection refused" usually indicate incorrect MQTT broker IP or InfluxDB credentials.
