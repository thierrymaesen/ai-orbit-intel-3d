# 🌍 AI-Orbit Intelligence 3D

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

## Description

Real-time 3D Satellite Visualization & Orbital Anomaly Detection using AI (Isolation Forest) and CelesTrak TLE data.

This project demonstrates senior-level software engineering skills combining orbital mechanics (SGP4 via Skyfield), unsupervised Machine Learning (Isolation Forest via scikit-learn), and interactive 3D visualization — all built with a clean, production-grade Python architecture.

## Data Disclaimer

> Orbital data provided by [CelesTrak](https://celestrak.org/). Used for educational and portfolio demonstration purposes.

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Pydantic
- **Orbital Mechanics**: Skyfield (SGP4 propagation)
- **Machine Learning**: scikit-learn (Isolation Forest)
- **Data Processing**: Pandas
- **Frontend**: Jinja2 + Three.js (3D visualization)
- **Scheduling**: schedule (periodic TLE ingestion)

## Installation

```bash
# Clone the repository
git clone https://github.com/thierrymaesen/ai-orbit-intel-3d.git
cd ai-orbit-intel-3d

# Install dependencies with Poetry
poetry install

# Run the application
poetry run uvicorn app.main:app --reload
```

## Project Structure

```
ai-orbit-intel-3d/
├── src/
│   └── orbit_intel/
│       └── __init__.py
├── app/
│   ├── static/
│   └── templates/
├── tests/
├── data/
├── .github/
│   └── workflows/
├── pyproject.toml
├── .gitignore
├── .python-version
├── LICENSE
└── README.md
```

## Status

🚧 **Sprint 0/10 Completed** — Initial project configuration and scaffolding.

## Author

**Thierry Maesen** — [GitHub](https://github.com/thierrymaesen)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
