# 🚦 Smart Traffic Optimizer (Pune City-Wide Scale)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-green.svg)](https://flask.palletsprojects.com/)
[![NetworkX](https://img.shields.io/badge/NetworkX-3.6.1-orange.svg)](https://networkx.org/)
[![OSMnx](https://img.shields.io/badge/OSMnx-2.1.1-blueviolet.svg)](https://osmnx.readthedocs.io/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9-brightgreen.svg)](https://leafletjs.com/)
[![Course](https://img.shields.io/badge/Course-Design%20%26%20Analysis%20of%20Algorithms-purple.svg)](#academic-context)

An intelligent urban traffic optimization, routing, and adaptive signal management simulation system scaled to the entire city grid of **Pune, Maharashtra, India**. Developed as a **Design and Analysis of Algorithms (DAA)** course project, the system integrates **A\* Pathfinding with an Admissible Haversine Heuristic**, **KD-Tree Spatial Snapping**, **Two-Tier Targeted TomTom Live Traffic Polling**, and a **15-Minute Zonal Weather Cache (OpenWeatherMap)** with a **Greedy Dynamic Signal Scheduling Heuristic**.

---

## 📌 Table of Contents
- [Project Overview](#-project-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Algorithmic Framework](#-algorithmic-framework)
  - [1. City-Wide Graph Modeling (OSMnx & GraphML)](#1-city-wide-graph-modeling-osmnx--graphml)
  - [2. KD-Tree Spatial Indexing & Coordinate Snapping](#2-kd-tree-spatial-indexing--coordinate-snapping)
  - [3. A* Search with Admissible Haversine Heuristic](#3-a-search-with-admissible-haversine-heuristic)
  - [4. Two-Tier Targeted Traffic Polling & Dynamic Rerouting](#4-two-tier-targeted-traffic-polling--dynamic-rerouting)
  - [5. Microclimate Zonal Weather Caching (TTLCache)](#5-microclimate-zonal-weather-caching-ttlcache)
  - [6. Greedy Dynamic Signal Scheduling](#6-greedy-dynamic-signal-scheduling)
  - [7. Delay & Efficiency Comparison Model](#7-delay--efficiency-comparison-model)
- [Empirical Benchmarks & Scaling Results](#-empirical-benchmarks--scaling-results)
- [Project Structure](#-project-structure)
- [Installation & Setup](#-installation--setup)
- [Running Tests](#-running-tests)
- [API Documentation](#-api-documentation)
- [Academic Context](#-academic-context)

---

## 🏙 Project Overview
Conventional traffic routing and signal management systems suffer from severe real-world bottlenecks:
* Fixed-cycle traffic signals ignore real-time congestion peaks.
* Standard Dijkstra shortest-path calculations degrade rapidly when scaled across hundreds of thousands of road network vertices.
* Polling live external traffic telemetry across entire cities exhausts commercial API rate limits instantly.

The **Smart Traffic Optimizer** solves these challenges by scaling from a toy corridor to the **entire Pune road network (137,050 nodes and 323,635 edges)**, combining asymptotic algorithmic optimizations with production-grade engineering safeguards.

---

## 🌟 Key Features
- **City-Wide Pune Drive Network:** 137,050 intersections and 323,635 road segments ingested via OSMnx and stored in memory as an indexed `networkx.MultiDiGraph`.
- **Arbitrary GPS Snapping:** Accepts arbitrary `{lat, lng}` coordinates anywhere in Pune and snaps them to the nearest drivable intersection in $\mathcal{O}(\log V)$ time using spatial tree indexing.
- **High-Performance A\* Pathfinding:** Implements an admissible, consistent Haversine distance heuristic function that delivers **3.5x to 4.5x faster pathfinding** compared to standard Dijkstra.
- **Two-Tier Targeted TomTom Flow Polling:** Eliminates API exhaustion by first computing a candidate path and polling live flow telemetry **strictly for the ~50–130 candidate segments** instead of all 323,635 edges (a **99.96% API call reduction**).
- **Dynamic Quadratic Congestion Rerouting:** Automatically detects congested corridors and recalculates alternate routes via dynamic weight penalties ($w_{\text{dyn}} = w_{\text{base}} \times [1 + 0.15 \cdot c^2]$).
- **Zonal Weather Microclimate Caching:** Employs a 15-minute `cachetools.TTLCache` indexed by coordinate zones (lat/lng rounded to 2 decimal places, ~1.1 km precision) to dynamically adjust braking multipliers and road delay without redundant OpenWeatherMap hits.
- **Greedy Dynamic Signal Clearance:** Heuristically allocates adaptive green-light durations based on real-time incident queue density.
- **Interactive Leaflet Dashboard:** Live vehicle animation, route comparison, signal phase indicators, and side-by-side efficiency analytics.

---

## 🛠 System Architecture

```mermaid
flowchart TD
    User([Frontend / User Input]) -->|POST /route with {lat, lng}| App[Flask API: app.py]
    App -->|GPS Coordinates| Snapper[KD-Tree Spatial Snapper: osmnx.distance.nearest_nodes]
    Snapper -->|Snapped Source & Target Node IDs| Graph[(Pune Road Graph: MultiDiGraph<br>137,050 nodes, 323,635 edges)]
    
    subgraph Pathfinding & Traffic Engine [traffic_logic.py & graph.py]
        Graph -->|Tier 1| AStar[A* Pathfinding with Haversine Heuristic]
        AStar -->|Baseline Candidate Path| Poller[Targeted TomTom Traffic Poller]
        
        WeatherCache[Zonal TTLCache: OpenWeatherMap 15-min TTL] -->|Impact Multiplier| Poller
        Poller -->|Poll ONLY Candidate Edges ~50-130| CongestionEvaluation{Heavy Congestion Detected?}
        
        CongestionEvaluation -->|No| FinalRoute[Optimal Route Selected]
        CongestionEvaluation -->|Yes: Congestion >= 6| DynamicReroute[Local A* Dynamic Rerouting]
        DynamicReroute --> FinalRoute
        
        FinalRoute --> GreedySignal[Greedy Dynamic Signal Scheduling]
        FinalRoute --> DelayMetrics[Fixed vs Dynamic Delay Evaluation]
    end
    
    GreedySignal --> Response[JSON API Response]
    DelayMetrics --> Response
    Response -->|Polyline + Metrics + Signals| User
```

---

## 🧠 Algorithmic Framework

### 1. City-Wide Graph Modeling (OSMnx & GraphML)
The road network is modeled as a directed multigraph $G = (V, E)$, where:
* **Vertices ($V$):** $137,050$ road junctions and intersections across Pune District.
* **Edges ($E$):** $323,635$ directional road segments.
* **Edge Attributes:** Physical road length ($m$), speed limit ($km/h$), travel time ($s$), and OpenStreetMap highway hierarchy classifications.
* **Storage:** Exported to compressed GraphML (`pune_drive_network.graphml.gz`, 23.8 MB) and cached in memory at server startup.

### 2. KD-Tree Spatial Indexing & Coordinate Snapping
* **Paradigm:** Spatial Partitioning Tree (KD-Tree / BallTree via Scikit-Learn & OSMnx).
* **Operation:** Given user-selected GPS coordinates $(lat, lng)$, the spatial index maps them to the nearest valid intersection vertex $v^* \in V$:
  $$v^* = \arg\min_{v \in V} \mathcal{D}_{\text{geodesic}}((lat, lng), (y_v, x_v))$$
* **Complexity:** $\mathcal{O}(\log V)$ per lookup, resolving arbitrarily selected points in under $2\text{ ms}$.

### 3. A* Search with Admissible Haversine Heuristic
* **Paradigm:** Informed Best-First Graph Search.
* **Evaluation Function:**
  $$f(n) = g(n) + h(n)$$
  * $g(n)$: Exact travel time / cost accumulated from source node to node $n$.
  * $h(n)$: Estimated remaining travel time from node $n$ to target $T$.
* **Heuristic Formulation:**
  $$h(n) = \frac{\text{Haversine}(\text{coord}(n), \text{coord}(T))}{v_{\max}}$$
  * Where $v_{\max} = 120\text{ km/h} \approx 33.33\text{ m/s}$ (theoretical maximum city driving speed).
* **Admissibility & Consistency:** Because the great-circle distance is the geometric lower bound and $v_{\max}$ is the global speed upper bound, $h(n) \le h^*(n)$ always holds true. This guarantees optimal shortest-path discovery without overestimating remaining cost.
* **Complexity:**
  * Space Complexity: $\mathcal{O}(V)$
  * Time Complexity: $\mathcal{O}((V + E) \log V)$ worst case, but pruned substantially in practice down to $\approx \frac{1}{4}$ of Dijkstra's explored vertex frontier.

### 4. Two-Tier Targeted Traffic Polling & Dynamic Rerouting
To prevent API rate-limit exhaustion while capturing real-time traffic conditions:
* **Tier 1 (Baseline Route):** Execute A\* search using baseline edge `travel_time` weights.
* **Tier 2 (Targeted Polling):** Extract the $k$ edges along the candidate path ($k \approx 50\text{ to }130$) and query TomTom Traffic Flow telemetry strictly for those coordinates.
* **Congestion Score Formulation:**
  $$c = \max\left(1, \min\left(10, \left\lfloor \frac{v_{\text{free}} - v_{\text{current}}}{v_{\text{free}}} \times 10 \right\rfloor + 1\right)\right)$$
* **Dynamic Weight Penalization:**
  $$w_{\text{dynamic}} = w_{\text{base}} \times \left(1 + 0.15 \cdot c^2\right)$$
* **Conditional Rerouting:** If any segment exceeds the congestion threshold ($c \ge 6$), an alternate localized A\* search is triggered on dynamic weights to steer traffic away from severe bottlenecks.

### 5. Microclimate Zonal Weather Caching (TTLCache)
* **Zonal Partitioning:** Coordinates are rounded to 2 decimal places to produce localized zone keys:
  $$\text{Zone Key} = (\text{round}(lat, 2), \text{round}(lng, 2))$$
  *(Provides an optimal ~1.1 km microclimate resolution).*
* **Cache Expiry:** Powered by `cachetools.TTLCache(maxsize=1000, ttl=900)` (15-minute time-to-live).
* **Weather Multiplier:** Severe precipitation (rain, thunderstorms, fog, mist) introduces a $1.20\times$ multiplier affecting travel times and braking distances.

### 6. Greedy Dynamic Signal Scheduling
* At each junction $u$ along the traversal, the system queries incident edge congestion and prioritizes clearance for the highest queue:
  $$e^* = \arg\max_{e \in \text{Incident}(u)} \text{congestion}(e)$$
* **Green Time Allocation:**
  $$T_{\text{green}} = T_{\text{base}} + (\text{congestion} \times 2)\quad \text{seconds}$$

### 7. Delay & Efficiency Comparison Model
* **Fixed Cycle Delay:** Statically modeled at $20\text{ seconds}$ per junction.
* **Dynamic Delay:** Adaptively reduced via green-light prioritization:
  $$\text{Delay}_{\text{dynamic}} = \max\left(5, 20 - \text{congestion}\right)\quad \text{seconds}$$
* **System Efficiency Gain:**
  $$\text{Efficiency } (\%) = \left(\frac{\text{Delay}_{\text{fixed}} - \text{Delay}_{\text{dynamic}}}{\text{Delay}_{\text{fixed}}}\right) \times 100$$

---

## 📊 Empirical Benchmarks & Scaling Results

| Metric | Toy Network (Old) | City-Wide Pune Network (Current) | Scaling Improvement |
| :--- | :--- | :--- | :--- |
| **Graph Nodes ($V$)** | 5 | **137,050** | $27,410\times$ larger |
| **Graph Edges ($E$)** | 8 | **323,635** | $40,454\times$ larger |
| **Coordinate Support** | Hardcoded node names | **Arbitrary Pune GPS Coordinates** | Continuous coverage |
| **Spatial Snapping** | Manual | **$\mathcal{O}(\log V)$ KD-Tree** | $< 2\text{ ms}$ lookup |
| **Pathfinding Algorithm** | Standard Dijkstra | **A\* Search + Haversine Heuristic** | **$3.5\times - 4.5\times$ speedup** |
| **Swargate $\to$ Viman Nagar Runtime** | N/A | **$31\text{ ms}$ (A\*) vs $140\text{ ms}$ (Dijkstra)** | Instant routing |
| **TomTom Telemetry Calls** | N/A | **Targeted candidate route only (~131 calls)** | **99.96% API call reduction** |
| **Weather Queries** | Uncached per-request | **Zonal TTLCache (15-min TTL)** | $1$ API call per zone |

---

## 📁 Project Structure

```text
smt_traffic/
├── .env.example              # Template for API keys
├── .gitignore                # Git ignore rules (caches, virtualenvs, local keys)
├── README.md                 # Complete system documentation & benchmark analysis
├── requirements.txt          # Python dependencies (Flask, NetworkX, OSMnx, SciPy, cachetools)
├── app.py                    # Flask server, route controllers, and KD-Tree coordinate parser
├── graph.py                  # City-wide GraphML loader, A* pathfinder, and Haversine heuristic
├── traffic_logic.py          # Two-Tier TomTom traffic polling, zonal weather cache & dynamic signals
├── data/
│   └── pune_drive_network.graphml.gz # Compressed Pune city road network (137,050 nodes)
├── scripts/
│   └── build_pune_graph.py   # Automated ingestion script downloading & preparing Pune OSM data
├── tests/
│   ├── test_phase1.py        # Verification: City-wide GraphML ingestion & edge attributes
│   ├── test_phase2.py        # Verification: KD-Tree spatial snapping & arbitrary GPS resolution
│   ├── test_phase3.py        # Verification: A* vs Dijkstra benchmark & Haversine heuristic
│   ├── test_phase4.py        # Verification: Two-tier targeted TomTom traffic flow polling
│   └── test_phase5.py        # Verification: Microclimate zonal weather caching & TTL validation
├── static/
│   ├── script.js             # Leaflet frontend UI, polyline animations, and signal renderers
│   └── style.css             # Dashboard styling and responsive layout
└── templates/
    └── index.html            # Main web simulation dashboard
```

---

## 🚀 Installation & Setup

### Prerequisites
* Python 3.10, 3.11, or 3.12 installed
* `git` installed
* Free API keys for:
  * [TomTom Developer Portal](https://developer.tomtom.com/) (Live traffic flow)
  * [OpenWeatherMap](https://openweathermap.org/api) (Meteorological weather)
  * [Mapbox](https://www.mapbox.com/) (Vector map tiles)

### 1. Clone the Repository
```bash
git clone https://github.com/omsai1210/smart-traffic-optimization.git
cd smart-traffic-optimization
```

### 2. Set Up Virtual Environment
On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:
```env
TOMTOM_API_KEY=your_tomtom_api_key_here
OPENWEATHER_API_KEY=your_openweather_api_key_here
MAPBOX_API_KEY=your_mapbox_token_here
```

### 5. Start the Server
```bash
python app.py
```
The server will start at:
```text
http://127.0.0.1:5000/
```

---

## 🧪 Running Tests

The test suite validates all 5 architectural phases sequentially:

To run all test phases via `unittest` discovery:
```bash
python -m unittest discover tests
```

To run individual phase tests:
```bash
python tests/test_phase1.py   # City-wide graph loading
python tests/test_phase2.py   # KD-Tree coordinate snapping
python tests/test_phase3.py   # A* vs Dijkstra performance benchmark
python tests/test_phase4.py   # Targeted TomTom polling
python tests/test_phase5.py   # 15-minute zonal weather caching
```

---

## 📡 API Documentation

### `POST /route`
Calculates optimal routes, dynamic reroutes, live signals, and delay comparisons between arbitrary coordinates.

#### Request Body (`application/json`)
```json
{
  "source": {
    "lat": 18.5018,
    "lng": 73.8584
  },
  "destination": {
    "lat": 18.5679,
    "lng": 73.9143
  }
}
```
*(Also supports direct integer OSM node IDs, e.g. `{"source": 2162277657, "destination": 636345744}`)*.

#### Sample Response (`200 OK`)
```json
{
  "source_node": 2162277657,
  "destination_node": 636345744,
  "source_coords": [18.5018, 73.8584],
  "destination_coords": [18.5679, 73.9143],
  "source_snapped_coords": [18.501844, 73.858412],
  "destination_snapped_coords": [18.567891, 73.914320],
  "candidate_edges_count": 131,
  "targeted_polled_count": 261,
  "rerouted": true,
  "candidate_path": [2162277657, 2162277670, ...],
  "path": [2162277657, 2162277685, ...],
  "route": [
    [18.501844, 73.858412],
    [18.502015, 73.858590],
    ...
  ],
  "weather": {
    "condition": "Clear",
    "description": "Clear sky",
    "temp": 21.8,
    "impact_multiplier": 1.0,
    "zone_key": [18.50, 73.86],
    "cached": true
  },
  "signals": {
    "2162277657": {
      "green": [2162277657, 2162277685],
      "time": 17,
      "traffic": 6
    }
  },
  "comparison": {
    "fixed": 2620,
    "dynamic": 1834,
    "efficiency": 30.0
  },
  "metrics": {
    "signals": 131,
    "avg_delay": 786.0,
    "traffic_load": 5.4,
    "weather": "Clear sky",
    "weather_cached": true,
    "weather_zone": [18.50, 73.86]
  }
}
```

---

## 🎓 Academic Context
* **Course:** Design and Analysis of Algorithms (DAA)
* **Semester:** Semester 5
* **Core Topics Demonstrated:**
  * **Heuristic Search:** A\* Search Algorithm with Admissible & Consistent Haversine Heuristic ($h(n) \le h^*(n)$).
  * **Spatial Data Structures:** Multi-dimensional KD-Tree coordinate indexing ($\mathcal{O}(\log V)$ query time).
  * **Graph Theory:** Directed Multigraph representation of massive transportation grids ($|V| > 1.3 \times 10^5$, $|E| > 3.2 \times 10^5$).
  * **Greedy Paradigm:** Adaptive green-light allocation via local incident queue maximization.
  * **Dynamic Weight Penalties:** Quadratic cost reweighting for congestion avoidance.
  * **Asymptotic Efficiency & Engineering Feasibility:** Caching and targeted polling bounds to avoid API combinatorial explosion.
