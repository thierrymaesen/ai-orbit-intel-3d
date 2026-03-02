---
title: Ai Orbit Intel 3d
emoji: 🌍
colorFrom: blue
colorTo: yellow
sdk: docker
pinned: false
license: mit
---

<div align="center">

🇫🇷 [Version française](#french) | 🇬🇧 [English version](#english)

</div>

---

<a name="french"></a>

# 🇫🇷 Version Française

# 🌍 AI Orbit Intel 3D — Plateforme Avancée de Renseignement Spatial (OSINT)

[![CI/CD Pipeline](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions/workflows/ci.yml/badge.svg)](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Live_Demo-yellow)](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 📖 Présentation

AI Orbit Intel 3D est une plateforme complète et open-source de **Renseignement Spatial OSINT** (Open-Source Intelligence) conçue pour fournir une connaissance situationnelle exploitable de l'environnement orbital autour de la Terre.

L'application ingère en temps réel les données **Two-Line Element (TLE)** et le catalogue complet **SATCAT** publiés par le NORAD via CelesTrak, couvrant plus de **14 000 satellites actifs**, corps de fusées et débris suivis. Chaque objet est rendu en temps réel sur un **globe 3D interactif propulsé par WebGL**, permettant aux analystes et passionnés d'explorer visuellement l'intégralité du domaine spatial proche de la Terre sous tous les angles et niveaux de zoom.

Au-delà de la simple visualisation, la plateforme intègre un pipeline de **Machine Learning non supervisé** qui s'exécute automatiquement au démarrage du serveur. Un modèle **Isolation Forest** (scikit-learn) est entraîné sur des paramètres orbitaux clés — excentricité, mouvement moyen, terme de traînée B* et inclinaison — pour identifier les satellites présentant un **comportement statistiquement anormal** par rapport à la population globale. Chaque satellite reçoit un **score de sévérité d'anomalie continu** normalisé entre 0 et 1, permettant aux analystes de faire ressortir instantanément les objets les plus inhabituels en orbite sans aucun étiquetage préalable ni données d'entraînement supervisé.

L'ensemble de la pile technique est construit avec un backend Python de qualité production (**FastAPI**), un frontend JavaScript léger sans étape de build (**Globe.gl** sur Three.js), et un pipeline de déploiement entièrement conteneurisé avec **Docker** et CI/CD automatisé via **GitHub Actions**. L'application est déployée en production sur **Hugging Face Spaces** en tant qu'application Docker SDK.

## 🚀 Démo en Ligne

Accédez à l'application déployée sur Hugging Face Spaces :

➡️ **[AI Orbit Intel 3D sur Hugging Face Spaces](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)**

La démo charge le catalogue complet de satellites au démarrage, entraîne le modèle de détection d'anomalies et affiche tous les objets sur le globe 3D — l'ensemble du pipeline de démarrage à froid se termine en moins d'une minute.

## ✨ Fonctionnalités Clés en Détail

🛰️ **Visualisation 3D Massive** — Le frontend exploite Globe.gl (construit sur Three.js et WebGL) pour afficher les positions de plus de 14 000 objets spatiaux suivis simultanément sur une Terre 3D photoréaliste. Le pipeline de rendu est optimisé pour des taux de rafraîchissement fluides et interactifs même à l'échelle du catalogue complet, supportant panoramique, zoom, inclinaison et rotation. Chaque point sur le globe représente un satellite réel dont la position est calculée à partir de ses paramètres orbitaux.

🧠 **Détection d'Anomalies par IA** — Au démarrage du serveur, le backend récupère automatiquement les dernières données TLE, extrait quatre caractéristiques orbitales critiques (inclinaison, excentricité, mouvement moyen et terme de traînée B*), les normalise avec StandardScaler, et entraîne un modèle Isolation Forest avec un taux de contamination configurable (5% par défaut). Le modèle attribue à chaque satellite un score d'anomalie continu de 0.0 (parfaitement normal) à 1.0 (hautement anormal), ainsi qu'un indicateur binaire d'anomalie. Les satellites présentant une décroissance orbitale inhabituelle, des orbites excentriques ou des mouvements moyens atypiques sont automatiquement mis en évidence sans nécessiter de données d'entraînement étiquetées.

🌍 **Filtrage OSINT Stratégique** — La plateforme télécharge le catalogue complet SATCAT depuis CelesTrak au démarrage et enrichit chaque satellite avec son code pays/propriétaire (US, PRC, CIS, FR, UK, ESA, IND, JPN, etc.) et son type d'objet (PAYLOAD, DEBRIS, ROCKET BODY, TBA, UNKNOWN). L'interface expose des filtres déroulants pour les deux dimensions, permettant aux analystes d'isoler, par exemple, uniquement les débris chinois ou uniquement les charges utiles françaises au sein du catalogue global. Ces filtres se combinent avec les filtres de type d'orbite et d'anomalie pour des requêtes OSINT multi-dimensionnelles puissantes.

⏱️ **Animation Orbitale en Temps Réel (Voyage dans le Temps)** — Le JavaScript côté client implémente un moteur de simulation orbitale mathématique qui anime chaque satellite en temps réel en fonction de son mouvement moyen réel (révolutions par jour) et de son inclinaison (degrés) extraits directement du modèle TLE/SGP4. Lorsque l'utilisateur active le bouton Play Orbit, les 14 000+ objets commencent à orbiter autour de la Terre à leurs vitesses relatives réelles, offrant une visualisation dynamique et physiquement fondée du trafic orbital. L'animation fonctionne jusqu'à 60 FPS avec un multiplicateur de distorsion temporelle configurable.

📚 **Enrichissement Wikipedia en Direct** — Un clic sur n'importe quel satellite sur le globe déclenche une recherche dynamique via l'API REST de Wikimedia. Si un article Wikipedia existe pour l'objet sélectionné, la plateforme récupère et affiche un résumé de son contexte historique et technique directement dans la barre latérale de l'interface. Cela permet aux analystes de contextualiser rapidement une anomalie signalée ou de se renseigner sur la mission, l'opérateur et l'historique de lancement de n'importe quel objet — le tout sans quitter l'application.

🎯 **Contrôles UI/UX Avancés** — L'interface inclut un bouton de filtre rapide Top 10 Anomalies qui affiche instantanément uniquement les dix satellites ayant les scores d'anomalie les plus élevés, triés par sévérité. Lorsqu'un satellite est sélectionné, il est mis en surbrillance en rouge avec un marqueur agrandi pour une identification claire contre le fond dense du globe. Le mode Hérisson (Lignes Vectorielles) dessine des lignes proportionnelles à l'altitude depuis chaque satellite vers l'extérieur depuis la surface terrestre, fournissant une cartographie visuelle intuitive de la distance de chaque objet au-dessus du sol — rendant la distinction entre les orbites LEO, MEO et GEO immédiatement apparente.

## 🏗️ Architecture & Pile Technique

L'application suit une architecture propre à trois couches séparant l'ingestion de données, le machine learning, le service API et le rendu frontend.

### 1. Pipeline de Données & Machine Learning (Backend)

Le backend est entièrement écrit en Python 3.10 et structuré comme un package installable (`src/orbit_intel/`). Le pipeline se compose de quatre modules :

- **ingest.py** — Télécharge le dernier fichier TLE de satellites actifs depuis CelesTrak et le stocke localement dans le répertoire `data/`. Ce module gère la récupération HTTP, la gestion des erreurs et la persistance des fichiers.
- **dynamics.py** — Parse le fichier TLE en utilisant Skyfield (propagation SGP4), extrait les paramètres orbitaux de chaque satellite (inclinaison, excentricité, mouvement moyen, traînée B*), et produit un DataFrame Pandas structuré prêt pour le machine learning.
- **anomaly.py** — Implémente la classe `OrbitalAnomalyDetector`, qui normalise les caractéristiques avec StandardScaler, entraîne un Isolation Forest (scikit-learn) sur l'ensemble de données complet, et annote chaque satellite avec un indicateur binaire d'anomalie et un score de sévérité continu dans la plage 0–1.
- **api.py** — La couche applicative FastAPI. Expose des endpoints RESTful pour les positions satellites en temps réel (`/api/positions`), les rapports d'anomalies (`/api/v1/anomalies`), la recherche individuelle de satellite (`/api/v1/satellite/{norad_id}`), les vérifications de santé (`/health`), et le pipeline d'ingestion/analyse TLE. L'enrichissement SATCAT (propriétaire, type d'objet) et la dynamique orbitale (mouvement moyen, inclinaison) sont calculés au démarrage et servis avec chaque réponse de position.

Le mécanisme de cycle de vie FastAPI orchestre l'intégralité de la séquence de démarrage : chargement TLE → téléchargement SATCAT → extraction de caractéristiques → entraînement Isolation Forest → initialisation de l'état, le tout avant que la première requête HTTP ne soit servie.

### 2. Frontend 3D Interactif

Le frontend est une pile légère sans étape de build conçue pour un déploiement instantané :

- **HTML5 / JavaScript Vanilla / CSS3** — Pas de frameworks, pas de bundlers, pas de node_modules. L'ensemble du frontend est servi comme fichiers statiques par FastAPI.
- **Globe.gl** — Une bibliothèque déclarative de haut niveau pour la visualisation de globe 3D, construite sur Three.js et WebGL. Elle gère la texture terrestre, le rendu atmosphérique, la gestion du nuage de points et les contrôles de caméra.
- **app.js** — Le script principal de l'application côté client. Il récupère les positions satellites depuis l'API, peuple l'instance Globe.gl, implémente la boucle d'animation orbitale (utilisant le mouvement moyen et l'inclinaison), gère les filtres OSINT déroulants (pays, type d'objet, type d'orbite, anomalies), gère la sélection et la mise en surbrillance des satellites, déclenche l'enrichissement Wikipedia, et contrôle le mode Hérisson avec les lignes vectorielles.
- **app.css** — Stylisation responsive pour les contrôles de la barre latérale, les panneaux d'anomalies, les filtres déroulants et les cartes d'information satellite.

### 3. DevOps & Infrastructure

- **Docker** — L'application est entièrement conteneurisée dans un Dockerfile optimisé pour la production basé sur `python:3.10-slim`. Il suit les bonnes pratiques Hugging Face Spaces : utilisateur non-root (appuser, UID 1000), exposition du port 7860, health checks, et ordonnancement des couches favorable au cache. Le package du projet est installé en mode éditable pour une résolution de module transparente.
- **GitHub Actions (CI/CD)** — Un pipeline d'intégration continue s'exécute à chaque push sur main, exécutant la suite complète de tests Pytest pour valider les endpoints API, la logique de données et le service frontend. Le workflow garantit qu'aucun code cassé n'atteint l'environnement déployé.
- **Pytest** — Les tests automatisés couvrent les endpoints FastAPI avec TestClient, vérifiant les health checks, les réponses de position, les rapports d'anomalies et la gestion des erreurs.
- **Hugging Face Spaces** — La cible de déploiement en production. Le frontmatter YAML de ce README configure le Space comme une application Docker SDK, ce qui déclenche Hugging Face pour construire et exécuter le Dockerfile automatiquement à chaque push.

## 📁 Structure du Projet

```
ai-orbit-intel-3d/
├── .github/
│   └── workflows/          # Pipeline CI/CD GitHub Actions
├── app/
│   ├── static/
│   │   ├── app.js          # Client 3D Globe.gl, animation orbitale, filtres OSINT
│   │   └── app.css         # Styles UI
│   ├── templates/
│   │   └── index.html      # Page HTML principale (template Jinja2)
│   └── main.py             # Point d'entrée FastAPI (Sprint 10)
├── src/
│   └── orbit_intel/
│       ├── __init__.py
│       ├── ingest.py        # Récupérateur de données TLE CelesTrak
│       ├── dynamics.py      # Parseur TLE & ingénierie de caractéristiques orbitales
│       ├── anomaly.py       # Détecteur d'anomalies Isolation Forest
│       └── api.py           # Routes FastAPI & modèles Pydantic
├── tests/
│   └── test_api.py          # Suite de tests Pytest
├── data/                    # Répertoire de données TLE (auto-alimenté à l'exécution)
├── Dockerfile               # Conteneur de production (compatible HF Spaces)
├── requirements.txt         # Dépendances Python
├── pyproject.toml           # Métadonnées du projet & config du package
├── LICENSE                  # Licence MIT
└── README.md                # Ce fichier
```

## ⚙️ Installation & Configuration

### Option 1 : Environnement Python Local

```bash
# Cloner le dépôt
git clone https://github.com/thierrymaesen/ai-orbit-intel-3d.git
cd ai-orbit-intel-3d

# Créer et activer un environnement virtuel
python -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Installer le package du projet (requis pour les imports de modules)
pip install -e .

# Lancer le serveur FastAPI
python app/main.py
```

L'application démarre sur `http://localhost:7860`. Au premier lancement, elle télécharge automatiquement les dernières données TLE depuis CelesTrak, récupère le catalogue SATCAT, extrait les caractéristiques orbitales et entraîne le modèle Isolation Forest. Ce pipeline de démarrage à froid se termine généralement en 30 à 60 secondes selon la vitesse du réseau.

### Option 2 : Docker (Recommandé)

```bash
# Construire l'image Docker
docker build -t ai-orbit-intel-3d .

# Lancer le conteneur
docker run -p 7860:7860 ai-orbit-intel-3d
```

Ouvrez votre navigateur à l'adresse `http://localhost:7860` pour accéder à l'interface du globe 3D. L'image Docker suit les standards de sécurité Hugging Face Spaces avec un utilisateur non-root et l'exposition du port 7860.

## 🖥️ Guide d'Utilisation

Une fois l'application lancée et le pipeline de démarrage terminé :

- **Explorer le Globe** — Utilisez votre souris pour faire pivoter, zoomer et incliner la Terre 3D. Chaque point coloré représente un objet spatial suivi. Les satellites anormaux sont colorés différemment selon leur score de sévérité.
- **Filtrer par Pays/Propriétaire** — Utilisez le menu déroulant Propriétaire pour isoler les satellites appartenant à un pays ou une organisation spécifique (US, PRC, CIS, FR, ESA, IND, JPN, etc.).
- **Filtrer par Type d'Objet** — Utilisez le menu déroulant Type d'Objet pour afficher uniquement les PAYLOAD, DEBRIS, ROCKET BODY ou autres catégories du catalogue SATCAT.
- **Filtrer par Type d'Orbite** — Basculez entre les vues ALL, LEO, MEO, GEO, ANOMALIES ou TOP10 pour vous concentrer sur des régimes orbitaux spécifiques ou des anomalies signalées.
- **Top 10 Anomalies** — Cliquez sur le bouton Top 10 pour afficher instantanément uniquement les dix satellites les plus anormaux, triés par score de sévérité.
- **Sélectionner un Satellite** — Cliquez sur n'importe quel point pour le sélectionner. Le satellite sélectionné est mis en surbrillance en rouge avec un marqueur agrandi, et ses détails (nom, NORAD ID, coordonnées, altitude, type d'orbite, score d'anomalie, propriétaire, type d'objet) sont affichés dans la barre latérale.
- **Enrichissement Wikipedia** — Lorsqu'un satellite est sélectionné, l'application interroge automatiquement l'API REST de Wikimedia pour récupérer un résumé de l'article Wikipedia du satellite (si disponible), fournissant un contexte historique et technique instantané.
- **Mode Hérisson (Vecteurs)** — Activez le mode Hérisson pour afficher des lignes vectorielles proportionnelles à l'altitude s'étendant depuis chaque satellite vers l'espace, fournissant une représentation visuelle de la distribution d'altitude orbitale à travers les bandes LEO, MEO et GEO.
- **Animation Orbitale (Lecture/Pause)** — Cliquez sur le bouton Play Orbit pour démarrer l'animation orbitale en temps réel. Tous les satellites commencent à se déplacer le long de leurs trajectoires orbitales en fonction de leurs valeurs réelles de mouvement moyen et d'inclinaison, offrant une vue dynamique des schémas de trafic orbital.

## 🧪 Exécution des Tests

Le projet inclut une suite de tests basée sur Pytest qui valide les endpoints API et la logique applicative :

```bash
# Exécuter tous les tests
pytest tests/ -v

# Exécuter avec rapport de couverture
pytest tests/ -v --cov=app --cov=src
```

Le pipeline CI/CD (GitHub Actions) exécute ces tests automatiquement à chaque push pour garantir la qualité du code et prévenir les régressions.

## 🔌 Référence API

Le backend FastAPI expose les endpoints suivants (documentation interactive disponible sur `/docs`) :

| Endpoint | Méthode | Description |
|---|---|---|
| `/` | GET | Sert l'interface du Globe 3D (frontend HTML) |
| `/health` | GET | Vérification de santé avec nombre de satellites et statistiques d'anomalies |
| `/api/positions` | GET | Positions en temps réel de tous les satellites (supporte les paramètres `filter_type`, `owner`, `object_type`) |
| `/api/v1/anomalies` | GET | Top N satellites anormaux (supporte les paramètres `top_n`, `min_score`) |
| `/api/v1/satellite/{norad_id}` | GET | Détails d'anomalie pour un satellite par NORAD ID |
| `/api/v1/ingest` | POST | Déclencher le re-téléchargement des données TLE depuis CelesTrak |
| `/api/v1/analyse` | POST | Relancer le pipeline de détection d'anomalies Isolation Forest |

## 👨‍💻 Auteur & Crédits

**Thierry Maesen**
- GitHub : [@thierrymaesen](https://github.com/thierrymaesen)
- Localisation : Flemalle, Wallonie, Belgique (BE)
- Sources de données : Données orbitales (TLE & SATCAT) fournies par NORAD / CelesTrak. Utilisées à des fins éducatives et de démonstration de portfolio. Informations contextuelles sur les satellites fournies par Wikipedia via l'API REST de Wikimedia.

## 📜 Licence

Ce projet est sous licence MIT — voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

<a name="english"></a>

# 🇬🇧 English Version

# 🌍 AI Orbit Intel 3D — Advanced Space OSINT Platform

[![CI/CD Pipeline](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions/workflows/ci.yml/badge.svg)](https://github.com/thierrymaesen/ai-orbit-intel-3d/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Live_Demo-yellow)](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 📖 Overview

AI Orbit Intel 3D is a comprehensive, open-source **Space OSINT** (Open-Source Intelligence) platform designed to provide actionable situational awareness of the orbital environment around Earth.

The application ingests live **Two-Line Element (TLE)** data and the full **SATCAT** catalogue published by NORAD via CelesTrak, covering more than **14,000 active satellites**, rocket bodies, and tracked debris objects. Every object is rendered in real time on an interactive **WebGL-powered 3D globe**, allowing analysts and enthusiasts to visually explore the entirety of the near-Earth space domain from any angle and zoom level.

Beyond pure visualisation, the platform embeds an **unsupervised Machine Learning** pipeline that executes automatically at server startup. An **Isolation Forest** model (scikit-learn) is trained on key orbital parameters — eccentricity, mean motion, B* drag term, and inclination — to identify satellites that exhibit **statistically anomalous behaviour** compared to the broader population. Each satellite receives a **continuous anomaly severity score** normalised between 0 and 1, enabling analysts to instantly surface the most unusual objects in orbit without any prior labelling or supervised training data.

The entire stack is built with a production-grade Python backend (**FastAPI**), a lightweight zero-build JavaScript frontend (**Globe.gl** on Three.js), and a fully containerised **Docker** deployment pipeline with automated CI/CD via **GitHub Actions**. It is deployed live on **Hugging Face Spaces** as a Docker SDK application.

## 🚀 Live Demo

Access the live application deployed on Hugging Face Spaces:

➡️ **[AI Orbit Intel 3D on Hugging Face Spaces](https://huggingface.co/spaces/thierrymaesen/ai-orbit-intel-3d)**

The demo loads the full satellite catalogue on startup, trains the anomaly detection model, and renders all objects on the 3D globe — the entire cold-start pipeline completes in under a minute.

## ✨ Key Features in Detail

🛰️ **Massive 3D Visualisation** — The frontend leverages Globe.gl (built on Three.js and WebGL) to render the positions of 14,000+ tracked space objects simultaneously on a photorealistic 3D Earth. The rendering pipeline is optimised for smooth, interactive frame rates even at full catalogue scale, supporting pan, zoom, tilt, and rotation. Each point on the globe represents a real satellite whose position is computed from its orbital parameters.

🧠 **AI-Powered Anomaly Detection** — At server startup, the backend automatically fetches the latest TLE data, extracts four critical orbital features (inclination, eccentricity, mean motion, and B* drag term), normalises them using StandardScaler, and trains an Isolation Forest model with a configurable contamination rate (default 5%). The model assigns every satellite a continuous anomaly score from 0.0 (perfectly normal) to 1.0 (highly anomalous), along with a binary anomaly flag. Satellites with unusual orbital decay, eccentric orbits, or atypical mean motions are automatically surfaced without requiring any labelled training data.

🌍 **Strategic OSINT Filtering** — The platform downloads the full SATCAT (Satellite Catalogue) from CelesTrak at startup and enriches every satellite with its owner/country code (US, PRC, CIS, FR, UK, ESA, IND, JPN, and more) and its object type (PAYLOAD, DEBRIS, ROCKET BODY, TBA, UNKNOWN). The UI exposes dropdown filters for both dimensions, enabling analysts to isolate, for example, only Chinese debris or only French payloads within the global catalogue. These filters combine with the orbit-type and anomaly filters for powerful multi-dimensional OSINT queries.

⏱️ **Real-Time Orbital Animation (Time-Travel)** — The client-side JavaScript implements a mathematical orbital simulation engine that animates every satellite in real time based on its actual mean motion (revolutions per day) and inclination (degrees) extracted directly from the TLE/SGP4 model. When the user activates the Play Orbit button, all 14,000+ objects begin orbiting the Earth at their true relative speeds, providing a dynamic, physics-grounded visualisation of orbital traffic. The animation runs at up to 60 FPS with a configurable time-warp multiplier.

📚 **Wikipedia Live Enrichment** — Clicking on any satellite on the globe triggers a dynamic lookup via the Wikimedia REST API. If a Wikipedia article exists for the selected object, the platform fetches and displays a summary of its historical and technical background directly in the UI sidebar. This allows analysts to quickly contextualise a flagged anomaly or learn about the mission, operator, and launch history of any object — all without leaving the application.

🎯 **Advanced UI/UX Controls** — The interface includes a Top 10 Anomalies quick-filter button that instantly displays only the ten satellites with the highest anomaly scores, sorted by severity. When a satellite is selected, it is highlighted in red with an enlarged marker for clear identification against the dense global backdrop. The Hedgehog Mode (Vector Lines) feature draws altitude-proportional lines from each satellite outward from the Earth's surface, providing an intuitive visual mapping of how far each object sits above the ground — making the distinction between LEO, MEO, and GEO orbits immediately apparent.

## 🏗️ Architecture & Tech Stack

The application follows a clean three-layer architecture separating data ingestion, machine learning, API serving, and frontend rendering.

### 1. Data Pipeline & Machine Learning (Backend)

The backend is written entirely in Python 3.10 and structured as an installable package (`src/orbit_intel/`). The pipeline consists of four modules:

- **ingest.py** — Downloads the latest active-satellite TLE file from CelesTrak and stores it locally in the `data/` directory. This module handles HTTP fetching, error handling, and file persistence.
- **dynamics.py** — Parses the TLE file using Skyfield (SGP4 propagation), extracts orbital parameters for each satellite (inclination, eccentricity, mean motion, B* drag), and produces a structured Pandas DataFrame ready for machine learning.
- **anomaly.py** — Implements the `OrbitalAnomalyDetector` class, which normalises features with StandardScaler, trains an Isolation Forest (scikit-learn) on the full dataset, and annotates every satellite with a binary anomaly flag and a continuous severity score in the 0–1 range.
- **api.py** — The FastAPI application layer. Exposes RESTful endpoints for real-time satellite positions (`/api/positions`), anomaly reports (`/api/v1/anomalies`), individual satellite lookup (`/api/v1/satellite/{norad_id}`), health checks (`/health`), and the TLE ingestion/analysis pipeline. SATCAT enrichment (owner, object type) and orbital dynamics (mean motion, inclination) are computed at startup and served alongside every position response.

The FastAPI lifespan mechanism orchestrates the entire startup sequence: TLE loading → SATCAT download → feature extraction → Isolation Forest training → state initialisation, all before the first HTTP request is served.

### 2. Interactive 3D Frontend

The frontend is a lightweight, zero-build-step stack designed for instant deployment:

- **HTML5 / Vanilla JavaScript / CSS3** — No frameworks, no bundlers, no node_modules. The entire frontend ships as static files served by FastAPI.
- **Globe.gl** — A high-level declarative library for 3D globe visualisation, built on Three.js and WebGL. It handles the Earth texture, atmosphere rendering, point cloud management, and camera controls.
- **app.js** — The main client-side application script. It fetches satellite positions from the API, populates the Globe.gl instance, implements the orbital animation loop (using mean motion and inclination), handles OSINT filter dropdowns (country, object type, orbit type, anomalies), manages satellite selection and highlighting, triggers Wikipedia enrichment, and controls the Hedgehog mode vector lines.
- **app.css** — Responsive styling for the sidebar controls, anomaly panels, filter dropdowns, and satellite info cards.

### 3. DevOps & Infrastructure

- **Docker** — The application is fully containerised in a production-optimised Dockerfile based on `python:3.10-slim`. It follows Hugging Face Spaces best practices: non-root user (appuser, UID 1000), port 7860 exposure, health checks, and cache-friendly layer ordering. The project package is installed in editable mode for seamless module resolution.
- **GitHub Actions (CI/CD)** — A continuous integration pipeline runs on every push to main, executing the full Pytest test suite to validate API endpoints, data logic, and frontend serving. The workflow ensures that no broken code reaches the deployed environment.
- **Pytest** — Automated tests cover the FastAPI endpoints using TestClient, verifying health checks, position responses, anomaly reports, and error handling.
- **Hugging Face Spaces** — The production deployment target. The YAML frontmatter in this README configures the Space as a Docker SDK application, which triggers Hugging Face to build and run the Dockerfile automatically on every push.

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

## ⚙️ Installation & Setup

### Option 1: Local Python Environment

```bash
# Clone the repository
git clone https://github.com/thierrymaesen/ai-orbit-intel-3d.git
cd ai-orbit-intel-3d

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install the project package (required for module imports)
pip install -e .

# Run the FastAPI server
python app/main.py
```

The application will start on `http://localhost:7860`. On first launch, it will automatically download the latest TLE data from CelesTrak, fetch the SATCAT catalogue, extract orbital features, and train the Isolation Forest model. This cold-start pipeline typically completes in 30–60 seconds depending on network speed.

### Option 2: Docker (Recommended)

```bash
# Build the Docker image
docker build -t ai-orbit-intel-3d .

# Run the container
docker run -p 7860:7860 ai-orbit-intel-3d
```

Open your browser at `http://localhost:7860` to access the 3D globe interface. The Docker image follows Hugging Face Spaces security standards with a non-root user and port 7860 exposure.

## 🖥️ Usage Guide

Once the application is running and the startup pipeline has completed:

- **Explore the Globe** — Use your mouse to rotate, zoom, and tilt the 3D Earth. Each coloured point represents a tracked space object. Anomalous satellites are coloured differently based on their severity score.
- **Filter by Country/Owner** — Use the Owner dropdown to isolate satellites belonging to a specific country or organisation (US, PRC, CIS, FR, ESA, IND, JPN, etc.).
- **Filter by Object Type** — Use the Object Type dropdown to show only PAYLOAD, DEBRIS, ROCKET BODY, or other categories from the SATCAT catalogue.
- **Filter by Orbit Type** — Switch between ALL, LEO, MEO, GEO, ANOMALIES, or TOP10 views to focus on specific orbital regimes or flagged anomalies.
- **Top 10 Anomalies** — Click the Top 10 button to instantly display only the ten most anomalous satellites, sorted by severity score.
- **Select a Satellite** — Click on any point to select it. The selected satellite is highlighted in red with an enlarged marker, and its details (name, NORAD ID, coordinates, altitude, orbit type, anomaly score, owner, object type) are displayed in the sidebar.
- **Wikipedia Enrichment** — When a satellite is selected, the application automatically queries the Wikimedia REST API to fetch a summary of the satellite's Wikipedia article (if available), providing instant historical and technical context.
- **Hedgehog Mode (Vectors)** — Toggle the Hedgehog mode to display altitude-proportional vector lines extending from each satellite toward space, providing a visual representation of orbital altitude distribution across LEO, MEO, and GEO bands.
- **Orbital Animation (Play/Pause)** — Click the Play Orbit button to start the real-time orbital animation. All satellites begin moving along their orbital paths based on their actual mean motion and inclination values, providing a dynamic view of orbital traffic patterns.

## 🧪 Running the Tests

The project includes a Pytest-based test suite that validates the API endpoints and application logic:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov=src
```

The CI/CD pipeline (GitHub Actions) executes these tests automatically on every push to ensure code quality and prevent regressions.

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

## 👨‍💻 Author & Credits

**Thierry Maesen**
- GitHub: [@thierrymaesen](https://github.com/thierrymaesen)
- Location: Flemalle, Wallonia, Belgium (BE)
- Data Sources: Orbital data (TLE & SATCAT) provided by NORAD / CelesTrak. Used for educational and portfolio demonstration purposes. Satellite background information provided by Wikipedia via the Wikimedia REST API.

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
