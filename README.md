---
title: Pavement Fatigue Simulator
emoji: 🛣️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6
app_file: app.py
pinned: true
---

# Pavement Fatigue Simulator

Rainflow-based fatigue analysis of rigid concrete pavements with real climate data from Open-Meteo.

## Features

- **Three weather data modes**: synthetic seasonal forcing, CSV upload, or live Open-Meteo API (historical + forecast)
- **Two load modes**: constant wheel load or CSV upload
- **Westergaard stress analysis** with interior, edge, and corner stress computation
- **First-order thermal and moisture response** modeling with slab lag effects
- **Rainflow cycle counting** with ASTM-standard algorithm
- **S-N fatigue damage accumulation** (Miner's rule)
- **Interactive plots** for temperature, moisture, load, stress, and full time series
- **Cycle table** with sortable data
- **CSV export** of rainflow cycle data

## Usage

1. Set slab geometry and material properties
2. Choose a weather source (Synthetic / CSV / Open-Meteo API)
3. Choose a load source (Constant / CSV)
4. Click "Run Simulation"
5. View results in the output tabs

## Open-Meteo Integration

When using the Open-Meteo API mode, the app fetches hourly weather data from two endpoints:

- **Archive API**: historical data up to ~2 days ago
- **Forecast API**: future forecast data

The datasets are automatically merged into a continuous hourly time series. Soil temperature and moisture data are included but not currently used in the simulation.

## CSV Formats

### Weather CSV
Required columns: `time`, `temperature_2m`, `relative_humidity_2m`
Optional columns: `rain`, `precipitation`

### Load CSV
Recommended columns: `timestep`, `axle_load_kN`

## Dependencies

- numpy
- pandas
- matplotlib
- gradio
- requests
