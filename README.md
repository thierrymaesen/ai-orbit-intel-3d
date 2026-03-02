---
title: Ai Orbit Intel 3d
emoji: 🌍
colorFrom: blue
colorTo: yellow
sdk: docker
pinned: false
license: mit
---

# 🌍 AI Orbit Intel 3D — Advanced Space OSINT Platform

[![CI/CD Pipeline](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions/workflows/ci.yml/badge.svg)](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Live_Demo-yellow)](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 📖 Overview

AI Orbit Intel 3D is a comprehensive, open-source **Space OSINT (Open-Source Intelligence)** platform designed to provide actionable situational awareness of the orbital environment around Earth. The application ingests live Two-Line Element (TLE) data and the full SATCAT catalogue published by NORAD via [CelesTrak](https://celestrak.org/), covering more than **14,000 active satellites, rocket bodies, and tracked debris objects**. Every object is rendered in real time on an interactive WebGL-powered 3D globe, allowing analysts and enthusiasts to visually explore the entirety of the near-Earth space domain from any angle and zoom level.

Beyond pure visualisation, the platform embeds an **unsupervised Machine Learning pipeline** that executes automatically at server startup. An **Isolation Forest** model (scikit-learn) is trained on key orbital parameters — eccentricity, mean motion, B* drag term, and inclination — to identify satellites that exhibit statistically anomalous behaviour compared to the broader population. Each satellite receives a continuous anomaly severity score normalised between 0 and 1, enabling analysts to instantly surface the most unusual objects in orbit without any prior labelling or supervised training data.

The entire stack is built with a production-grade Python backend (FastAPI), a lightweight zero-build JavaScript frontend (Globe.gl on Three.js), and a fully containerised Docker deployment pipeline with automated CI/CD via GitHub Actions. It is deployed live on Hugging Face Spaces as a Docker SDK application.

---

## 🚀 Live Demo

Access the live application deployed on Hugging Face Spaces:

**➡️ [AI Orbit Intel 3D on Hugging Face Spaces](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)**

The demo loads the full satellite catalogue on startup, trains the anomaly detection model, and renders all objects on the 3D globe — the entire cold-start pipeline completes in under a minute.

---

## ✨ Key Features in Detail

*   🛰️ **Massive 3D Visualisation** — The frontend leverages [Globe.gl](https://globe.gl/) (built on Three.js and WebGL) to render the positions of 14,000+ tracked space objects simultaneously on a photorealistic 3D Earth. The rendering pipeline is optimised for smooth, interactive frame rates even at full catalogue scale, supporting pan, zoom, tilt, and rotation. Each point on the globe represents a real satellite whose position is computed from its orbital parameters.

*   🧠 **AI-Powered Anomaly Detection** — At server startup, the backend automatically fetches the latest TLE data, extracts four critical orbital features (inclination, eccentricity, mean motion, and B* drag term), normalises them using StandardScaler, and trains an Isolation Forest model with a configurable contamination rate (default 5%). The model assigns every satellite a continuous anomaly score from 0.0 (perfectly normal) to 1.0 (highly anomalous), along with a binary anomaly flag. Satellites with unusual orbital decay, eccentric orbits, or atypical mean motions are automatically surfaced without requiring any labelled training data.

*   🌍 **Strategic OSINT Filtering** — The platform downloads the full SATCAT (Satellite Catalogue) from CelesTrak at startup and enriches every satellite with its **owner/country code** (US, PRC, CIS, FR, UK, ESA, IND, JPN, and more) and its **object type** (PAYLOAD, DEBRIS, ROCKET BODY, TBA, UNKNOWN). The UI exposes dropdown filters for both dimensions, enabling analysts to isolate, for example, only Chinese debris or only French payloads within the global catalogue. These filters combine with the orbit-type and anomaly filters for powerful multi-dimensional OSINT queries.

*   ⏱️ **Real-Time Orbital Animation (Time-Travel)** — The client-side JavaScript implements a mathematical orbital simulation engine that animates every satellite in real time based on its actual mean motion (revolutions per day) and inclination (degrees) extracted directly from the TLE/SGP4 model. When the user activates the Play Orbit button, all 14,000+ objects begin orbiting the Earth at their true relative speeds, providing a dynamic, physics-grounded visualisation of orbital traffic. The animation runs at up to 60 FPS with a configurable time-warp multiplier.

*   📚 **Wikipedia Live Enrichment** — Clicking on any satellite on the globe triggers a dynamic lookup via the Wikimedia REST API. If a Wikipedia article exists for the selected object, the platform fetches and displays a summary of its historical and technical background directly in the UI sidebar. This allows analysts to quickly contextualise a flagged anomaly or learn about the mission, operator, and launch history of any object — all without leaving the application.

*   🎯 **Advanced UI/UX Controls** — The interface includes a Top 10 Anomalies quick-filter button that instantly displays only the ten satellites with the highest anomaly scores, sorted by severity. When a satellite is selected, it is highlighted in red with an enlarged marker for clear identification against the dense global backdrop. The Hedgehog Mode (Vector Lines) feature draws altitude-proportional lines from each satellite outward from the Earth's surface, providing an intuitive visual mapping of how far each object sits above the ground — making the distinction between LEO, MEO, and GEO orbits immediately apparent.

---

## 🏗️ Architecture & Tech Stack

The application follows a clean three-layer architecture separating data ingestion, machine learning, API serving, and frontend rendering.

### 1. Data Pipeline & Machine Learning (Backend)

The backend is written entirely in **Python 3.10** and structured as an installable package (`src/orbit_intel/`). The pipeline consists of four modules:

*   **`ingest.py`** — Downloads the latest active-satellite TLE file from CelesTrak and stores it locally in the `data/` directory. This module handles HTTP fetching, error handling, and file persistence.
*   **`dynamics.py`** — Parses the TLE file using **Skyfield** (SGP4 propagation), extracts orbital parameters for each satellite (inclination, eccentricity, mean motion, B* drag), and produces a structured **Pandas** DataFrame ready for machine learning.
*   **`anomaly.py`** — Implements the `OrbitalAnomalyDetector` class, which normalises features with **StandardScaler**, trains an **Isolation Forest** (scikit-learn) on the full dataset, and annotates every satellite with a binary anomaly flag and a continuous severity score in the 0–1 range.
*   **`api.py`** — The **FastAPI** application layer. Exposes RESTful endpoints for real-time satellite positions (`/api/positions`), anomaly reports (`/api/v1/anomalies`), individual satellite lookup (`/api/v1/satellite/{norad_id}`), health checks (`/health`), and the TLE ingestion/analysis pipeline. SATCAT enrichment (owner, object type) and orbital dynamics (mean motion, inclination) are computed at startup and served alongside every position response.

The **FastAPI lifespan** mechanism orchestrates the entire startup sequence: TLE loading → SATCAT download → feature extraction → Isolation Forest training → state initialisation, all before the first HTTP request is served.

### 2. Interactive 3D Frontend

The frontend is a lightweight, zero-build-step stack designed for instant deployment:

*   **HTML5 / Vanilla JavaScript / CSS3** — No frameworks, no bundlers, no node_modules. The entire frontend ships as static files served by FastAPI.
*   **Globe.gl** — A high-level declarative library for 3D globe visualisation, built on **Three.js** and **WebGL**. It handles the Earth texture, atmosphere rendering, point cloud management, and camera controls.
*   **`app.js`** — The main client-side application script. It fetches satellite positions from the API, populates the Globe.gl instance, implements the orbital animation loop (using mean motion and inclination), handles OSINT filter dropdowns (country, object type, orbit type, anomalies), manages satellite selection and highlighting, triggers Wikipedia enrichment, and controls the Hedgehog mode vector lines.
*   **`app.css`** — Responsive styling for the sidebar controls, anomaly panels, filter dropdowns, and satellite info cards.

### 3. DevOps & Infrastructure

*   **Docker** — The application is fully containerised in a production-optimised Dockerfile based on `python:3.10-slim`. It follows Hugging Face Spaces best practices: non-root user (`appuser`, UID 1000), port 7860 exposure, health checks, and cache-friendly layer ordering. The project package is installed in editable mode for seamless module resolution.
*   **GitHub Actions (CI/CD)** — A continuous integration pipeline runs on every push to `main`, executing the full Pytest test suite to validate API endpoints, data logic, and frontend serving. The workflow ensures that no broken code reaches the deployed environment.
*   **Pytest** — Automated tests cover the FastAPI endpoints using `TestClient`, verifying health checks, position responses, anomaly reports, and error handling.
*   **Hugging Face Spaces** — The production deployment target. The YAML frontmatter in this README configures the Space as a Docker SDK application, which triggers Hugging Face to build and run the Dockerfile automatically on every push.

---

## 📁 Project Structure

```
ai-orbit-intel-3d/
├── .github/
│   └── workflows/          # GitHub Actions CI/CD pipeline
├── app/
│   ├── static/
│   │   ├── app.js          # Globe.gl 3D client, orbital animation, OSINT filters
│   │   └── app.css         # UI styles
│   ├── templates/
│   │   └── index.html      # Main HTML page (Jinja2 template)
│   └── main.py             # FastAPI application entry point (Sprint 10)
├── src/
│   └── orbit_intel/
│       ├── __init__.py
│       ├── ingest.py        # CelesTrak TLE data fetcher
│       ├── dynamics.py      # TLE parser & orbital feature engineering
│       ├── anomaly.py       # Isolation Forest anomaly detector
│       └── api.py           # FastAPI routes & Pydantic models
├── tests/
│   └── test_api.py          # Pytest test suite
├── data/                    # TLE data directory (auto-populated at runtime)
├── Dockerfile               # Production container (HF Spaces compatible)
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata & package config
├── LICENSE                  # MIT License
└── README.md                # This file
```

---

## ⚙️ Installation & Setup

### Option 1: Local Python Environment

```bash
# Clone the repository
git clone https://github.com/thierrymaesen/ai-orbit-intel-3d.git
cd ai-orbit-intel-3d

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\\Scripts\\activate          # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install the project package (required for module imports)
pip install -e .

# Run the FastAPI server
python app/main.py
```

The application will start on **http://localhost:7860**. On first launch, it will automatically download the latest TLE data from CelesTrak, fetch the SATCAT catalogue, extract orbital features, and train the Isolation Forest model. This cold-start pipeline typically completes in 30–60 seconds depending on network speed.

### Option 2: Docker (Recommended)

```bash
# Build the Docker image
docker build -t ai-orbit-intel-3d .

# Run the container
docker run -p 7860:7860 ai-orbit-intel-3d
```

Open your browser at **http://localhost:7860** to access the 3D globe interface. The Docker image follows Hugging Face Spaces security standards with a non-root user and port 7860 exposure.

---

## 🖥️ Usage Guide

Once the application is running and the startup pipeline has completed:

1.  **Explore the Globe** — Use your mouse to rotate, zoom, and tilt the 3D Earth. Each coloured point represents a tracked space object. Anomalous satellites are coloured differently based on their severity score.

2.  **Filter by Country/Owner** — Use the Owner dropdown to isolate satellites belonging to a specific country or organisation (US, PRC, CIS, FR, ESA, IND, JPN, etc.).

3.  **Filter by Object Type** — Use the Object Type dropdown to show only PAYLOAD, DEBRIS, ROCKET BODY, or other categories from the SATCAT catalogue.

4.  **Filter by Orbit Type** — Switch between ALL, LEO, MEO, GEO, ANOMALIES, or TOP10 views to focus on specific orbital regimes or flagged anomalies.

5.  **Top 10 Anomalies** — Click the Top 10 button to instantly display only the ten most anomalous satellites, sorted by severity score.

6.  **Select a Satellite** — Click on any point to select it. The selected satellite is highlighted in red with an enlarged marker, and its details (name, NORAD ID, coordinates, altitude, orbit type, anomaly score, owner, object type) are displayed in the sidebar.

7.  **Wikipedia Enrichment** — When a satellite is selected, the application automatically queries the Wikimedia REST API to fetch a summary of the satellite's Wikipedia article (if available), providing instant historical and technical context.

8.  **Hedgehog Mode (Vectors)** — Toggle the Hedgehog mode to display altitude-proportional vector lines extending from each satellite toward space, providing a visual representation of orbital altitude distribution across LEO, MEO, and GEO bands.

9.  **Orbital Animation (Play/Pause)** — Click the Play Orbit button to start the real-time orbital animation. All satellites begin moving along their orbital paths based on their actual mean motion and inclination values, providing a dynamic view of orbital traffic patterns.

---

## 🧪 Running the Tests

The project includes a Pytest-based test suite that validates the API endpoints and application logic:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov=src
```

The CI/CD pipeline (GitHub Actions) executes these tests automatically on every push to ensure code quality and prevent regressions.

---

## 🔌 API Reference

The FastAPI backend exposes the following endpoints (interactive docs available at `/docs`):

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the 3D Globe UI (HTML frontend) |
| `/health` | GET | Health check with satellite count and anomaly stats |
| `/api/positions` | GET | Real-time positions for all satellites (supports `filter_type`, `owner`, `object_type` query params) |
| `/api/v1/anomalies` | GET | Top N anomalous satellites (supports `top_n`, `min_score` params) |
| `/api/v1/satellite/{norad_id}` | GET | Anomaly details for a single satellite by NORAD ID |
| `/api/v1/ingest` | POST | Trigger TLE data re-download from CelesTrak |
| `/api/v1/analyse` | POST | Re-run the Isolation Forest anomaly detection pipeline |

---

## 👨‍💻 Author & Credits

**Thierry Maesen**

*   GitHub: [@thierrymaesen](https://github.com/thierrymaesen)
*   Location: Flemalle, Wallonia, Belgium (BE)

**Data Sources:**

*   Orbital data (TLE & SATCAT) provided by [NORAD / CelesTrak](https://celestrak.org/). Used for educational and portfolio demonstration purposes.
*   Satellite background information provided by [Wikipedia](https://www.wikipedia.org/) via the Wikimedia REST API.

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
