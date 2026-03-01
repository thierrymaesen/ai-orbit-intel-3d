---
title: Ai Orbit Intel 3d
emoji: 🌍
colorFrom: blue
colorTo: yellow
sdk: docker
pinned: false
license: mit
---

# 🌍 AI Orbit Intel 3D

[![CI/CD Pipeline](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions/workflows/ci.yml/badge.svg)](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Live_Demo-yellow)](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

AI Orbit Intel 3D is an advanced open-source Space OSINT (Open-Source Intelligence) platform. It provides real-time 3D visualization of over 14,000 active satellites and space debris, enriched with Machine Learning to automatically detect orbital anomalies.

---

## 🚀 Live Demo

Try the application here: [AI Orbit Intel 3D on Hugging Face Spaces](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)

---

## ✨ Key Features

*   🛰️ Massive 3D Rendering: Smooth visualization of 14,000+ space objects using Globe.gl.

*   🧠 AI Anomaly Detection: Automated Machine Learning pipeline Isolation Forest via Scikit-Learn) that runs on server startup to flag satellites with abnormal orbital behaviors (eccentricity, mean motion, etc.).

*   🌍 Strategic OSINT Filters: Filter the global satellite catalog by Owner/Country (USA, China, Russia, France, etc.) and Object Type (Payload, Debris, Rocket Body).

*   ⏱️ Real-Time Orbital Simulation: Client-side mathematical calculation to animate satellites orbiting the Earth based on their real mean_motion and inclination.

*   📚 Wikipedia Enrichment: Click on any satellite to dynamically fetch its historical and technical background via the Wikimedia REST API.

*   🎯 Advanced UI/UX: "Top 10 Anomalies" quick-filter, Active Selection highlighting, and a "Hedgehog" mode (Vector lines) mapping altitude distances to Earth.

---

## 🏗️ Architecture & Tech Stack

Backend: Python 3.10, FastAPI, Scikit-Learn (Unsupervised ML), Pandas, CelesTrak API.  
Frontend: HTML5, Vanilla JS, CSS3, Globe.gl (Three.js WebGL).  
DevOps & CI/CD: Pytest, GitHub Actions, Docker, Hugging Face Spaces.

---

## 👨‍💻 Author

Thierry Maesen

*   GitHub: [@thierrymaesen](https://github.com/thierrymaesen)
*   Location: Seraing, Wallonia, BE
