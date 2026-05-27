---
title: Pavement Fatigue Simulator
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: Dockerfile
pinned: false
---

# Pavement Fatigue Simulator

**Website:** [sourabh00809-pavement-simulator.hf.space](https://sourabh00809-pavement-simulator.hf.space/)

Rainflow-based fatigue analysis of rigid concrete pavements. Uses Westergaard edge stress theory with thermal, moisture, and traffic loading. Supports synthetic weather, CSV upload, and real-time data from the Open-Meteo API.

## Workflow

1. **Configure parameters** -- slab geometry, material properties, fatigue SN curve, and weather/traffic sources.
2. **Run simulation** -- the FastAPI backend computes hourly/daily stress time series using the core engine (`src/engine.py`).
3. **Rainflow counting** -- stress cycles are extracted via ASTM E1049 rainflow algorithm.
4. **Fatigue damage** -- Palmgren-Miner linear damage rule with an SN curve.
5. **Visualize** -- interactive charts (Chart.js) for temperature, moisture, load, stress, and cycle distribution.
6. **Export** -- rainflow cycle data as CSV.

## Architecture

```
backend/main.py         FastAPI application (API + static file serving)
frontend/index.html     Single-page application
frontend/js/app.js      Chart.js frontend logic
frontend/css/style.css  Stylesheet
src/engine.py           Core simulation engine (PavementSimulator class)
src/weather_fetcher.py  Open-Meteo archive + forecast API integration
Dockerfile              Hugging Face Spaces container definition
requirements.txt        Python dependencies
```
