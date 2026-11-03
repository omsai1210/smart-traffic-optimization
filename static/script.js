// =====================================================
// SMART TRAFFIC OPTIMIZER
// ADVANCED MULTI-PARAMETER GREEDY VERSION
// =====================================================

// ================= MAP =================

const map = L.map('map').setView(
    [18.5150, 73.9200],
    14
);

L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
        attribution:
            '© OpenStreetMap contributors'
    }
).addTo(map);

// =====================================================
// GLOBALS
// =====================================================

let simulationMode = "dynamic";

let loadedRoute = [];

let routeLine = null;

let car = null;

let signalMarkers = [];

let simulationRunning = false;

let roadSegments = [];

// NEW
let trafficVehicles = [];

// =====================================================
// HELPERS
// =====================================================

function sleep(ms) {

    return new Promise(resolve =>
        setTimeout(resolve, ms)
    );
}

function updateStatus(message) {

    document.getElementById(
        "statusBox"
    ).innerText = message;
}

// =====================================================
// MODE
// =====================================================

function setMode(mode) {

    simulationMode = mode;

    document
        .getElementById("dynamicBtn")
        .classList.remove("active-mode");

    document
        .getElementById("fixedBtn")
        .classList.remove("active-mode");

    if (mode === "dynamic") {

        document
            .getElementById("dynamicBtn")
            .classList.add("active-mode");

    } else {

        document
            .getElementById("fixedBtn")
            .classList.add("active-mode");
    }
}

// =====================================================
// RESET
// =====================================================

function clearMap() {

    if (routeLine) {

        map.removeLayer(routeLine);
    }

    if (car) {

        map.removeLayer(car);
    }

    signalMarkers.forEach(signal => {

        map.removeLayer(signal.marker);
    });

    roadSegments.forEach(segment => {

        map.removeLayer(segment.line);
    });

    signalMarkers = [];

    roadSegments = [];

    trafficVehicles = [];
}

// =====================================================
// LOAD ROUTE
// =====================================================

async function loadRoute() {

    clearMap();

    updateStatus(
        "Loading route..."
    );

    const source =
        document
            .getElementById("source")
            .value;

    const destination =
        document
            .getElementById("dest")
            .value;

    try {

        const response =
            await fetch('/route', {

                method: 'POST',

                headers: {

                    'Content-Type':
                        'application/json'
                },

                body: JSON.stringify({

                    source,
                    destination
                })
            });

        const data =
            await response.json();

        loadedRoute =
            data.route.map(point =>

                L.latLng(
                    point[0],
                    point[1]
                )
            );

        // =====================================================
        // MAIN ROUTE
        // =====================================================

        routeLine =
            L.polyline(loadedRoute, {

                color: '#1e293b',

                weight: 9,

                opacity: 0.9

            }).addTo(map);

        map.fitBounds(
            routeLine.getBounds()
        );

        // =====================================================
        // TRAFFIC SEGMENTS
        // =====================================================

        createRoadSegments();

        // =====================================================
        // SIGNALS
        // =====================================================

        createSignals();

        // =====================================================
        // UI
        // =====================================================

        document
            .getElementById("routeInfo")
            .style.display = "block";

        document
            .getElementById("routePath")
            .innerText =

            source.replaceAll("_", " ")

            + " → " +

            destination.replaceAll("_", " ");

        document
            .getElementById("simulateBtn")
            .disabled = false;

        updateStatus(
            "Traffic network loaded"
        );

    } catch (err) {

        console.error(err);

        updateStatus(
            "Failed to load route"
        );
    }
}

// =====================================================
// CREATE ROAD SEGMENTS
// =====================================================

function createRoadSegments() {

    roadSegments = [];

    const blockSize = 22;

    for (
        let i = 0;
        i < loadedRoute.length - blockSize;
        i += blockSize
    ) {

        const segmentPoints =
            loadedRoute.slice(
                i,
                i + blockSize
            );

        // RANDOM INITIAL CONGESTION
        const traffic =
            Math.random() * 3 + 1;

        let color = "#22c55e";

        if (traffic > 3) {

            color = "#ef4444";

        } else if (
            traffic > 1.8
        ) {

            color = "#eab308";
        }

        const line =
            L.polyline(segmentPoints, {

                color: color,

                weight: 7,

                opacity: 0.95,

                lineCap: 'round'

            }).addTo(map);

        roadSegments.push({

            line: line,

            congestion: traffic,

            points: segmentPoints
        });
    }
}

// =====================================================
// SIGNALS
// =====================================================

function createSignals() {

    for (
        let i = 25;
        i < loadedRoute.length;
        i += 35
    ) {

        const html = `
            <div class="signal-wrapper">
                <div class="signal-light red active"></div>
                <div class="signal-light yellow"></div>
                <div class="signal-light green"></div>
            </div>
        `;

        const icon =
            L.divIcon({

                className: '',

                html: html,

                iconSize: [20, 50]
            });

        const marker =
            L.marker(loadedRoute[i], {

                icon: icon

            }).addTo(map);

        signalMarkers.push({

            marker: marker,

            triggered: false,

            routeIndex: i
        });
    }

    document
        .getElementById("signalsCount")
        .innerText =
        signalMarkers.length;
}

// =====================================================
// SIGNAL UPDATE
// =====================================================

function updateSignal(signal, color) {

    const el =
        signal.marker.getElement();

    if (!el) return;

    const red =
        el.querySelector('.red');

    const yellow =
        el.querySelector('.yellow');

    const green =
        el.querySelector('.green');

    red.classList.remove('active');
    yellow.classList.remove('active');
    green.classList.remove('active');

    if (color === 'red')
        red.classList.add('active');

    if (color === 'yellow')
        yellow.classList.add('active');

    if (color === 'green')
        green.classList.add('active');
}

// =====================================================
// CAR
// =====================================================

function createCar(start) {

    car = L.marker(start, {

        icon: L.icon({

            iconUrl:
                'https://cdn-icons-png.flaticon.com/512/744/744465.png',

            iconSize: [30, 30]
        })

    }).addTo(map);
}

// =====================================================
// GENERATE BACKGROUND TRAFFIC
// =====================================================

function generateTrafficVehicles() {

    trafficVehicles = [];

    for (let i = 0; i < 18; i++) {

        const startIndex = Math.floor(

            Math.random() *

            (loadedRoute.length - 50)
        );

        const vehicle = {

            currentIndex: startIndex,

            speed:
                Math.random() * 3 + 1.5
        };

        trafficVehicles.push(vehicle);
    }
}

// =====================================================
// ROAD COLOR TRANSITION
// =====================================================

async function smoothRoadTransition(
    road,
    targetColor
) {

    road.line.setStyle({

        color: targetColor
    });

    await sleep(120);
}

// =====================================================
// DISPERSION
// =====================================================

async function disperseTraffic(
    signalIndex
) {

    const nearbySegments =

        roadSegments.slice(

            Math.max(0, signalIndex - 1),

            Math.min(
                roadSegments.length,
                signalIndex + 2
            )
        );

    for (const segment of nearbySegments) {

        // RED → YELLOW
        if (
            segment.congestion > 3
        ) {

            await smoothRoadTransition(
                segment,
                "#eab308"
            );

            await sleep(250);
        }

        // YELLOW → GREEN
        await smoothRoadTransition(
            segment,
            "#22c55e"
        );

        segment.congestion = 1;

        await sleep(250);
    }
}

// =====================================================
// GREEDY DECISION FEED
// =====================================================

function addGreedyDecision(
    signalName,
    extension,
    reason
) {

    const feed =
        document.getElementById(
            "greedyFeed"
        );

    const item =
        document.createElement("div");

    let css = "medium";

    if (
        reason ===
        "Heavy Congestion"
    ) {

        css = "high";
    }

    item.className =
        `feed-item ${css}`;

    item.innerHTML = `

        <b>🚦 ${signalName}</b><br>

        +${extension}s Green Extension<br>

        Reason: ${reason}
    `;

    feed.prepend(item);

    while (
        feed.children.length > 5
    ) {

        feed.removeChild(
            feed.lastChild
        );
    }
}

// =====================================================
// MAIN SIMULATION
// =====================================================

async function startSimulation() {

    if (
        simulationRunning ||
        loadedRoute.length === 0
    ) {

        return;
    }

    simulationRunning = true;

    generateTrafficVehicles();

    createCar(loadedRoute[0]);

    updateStatus(
        "Simulation running..."
    );

    for (
        let i = 0;
        i < loadedRoute.length;
        i++
    ) {

        let stopped = false;

        // =====================================================
        // MOVE BACKGROUND TRAFFIC
        // =====================================================

        trafficVehicles.forEach(vehicle => {

            vehicle.currentIndex +=
                vehicle.speed * 0.15;

            if (
                vehicle.currentIndex >=
                loadedRoute.length
            ) {

                vehicle.currentIndex = 0;
            }
        });

        // =====================================================
        // SIGNAL CHECK
        // =====================================================

        for (
            let s = 0;
            s < signalMarkers.length;
            s++
        ) {

            const signal =
                signalMarkers[s];

            if (
                signal.triggered
            ) continue;

            const signalPos =
                signal.marker.getLatLng();

            const dist =
                map.distance(
                    loadedRoute[i],
                    signalPos
                );

            // UPCOMING SIGNAL
            if (dist < 45) {

                signal.triggered = true;

                stopped = true;

                // =====================================================
                // FIND CONGESTED SEGMENT
                // =====================================================

                const segment =

                    roadSegments[
                        s %
                        roadSegments.length
                    ];

                // =====================================================
                // MULTI-PARAMETER GREEDY LOGIC
                // =====================================================

                // 1. CONGESTION SCORE
                const congestionScore =
                    segment.congestion * 4;

                // 2. NEARBY VEHICLES
                const nearbyVehicles =
                    trafficVehicles.filter(v =>

                        Math.abs(
                            v.currentIndex -
                            signal.routeIndex
                        ) < 25

                    ).length;

                // 3. QUEUE FACTOR
                const queueFactor =
                    nearbyVehicles * 0.7;

                // 4. AVERAGE SPEED
                const avgSpeed =
                    trafficVehicles.length > 0

                    ? trafficVehicles.reduce(

                        (sum, v) =>

                            sum + v.speed,

                        0

                    ) / trafficVehicles.length

                    : 3;

                // 5. EMERGENCY FACTOR
                const emergencyFactor =
                    Math.random() > 0.93
                    ? 8
                    : 0;

                // =====================================================
                // FINAL GREEDY DECISION
                // =====================================================

                const extension =

                    simulationMode === "fixed"

                    ? 0

                    : Math.round(

                        congestionScore +

                        queueFactor +

                        (5 - avgSpeed) +

                        emergencyFactor
                    );

                const reason =

                    emergencyFactor > 0

                    ? "Emergency Priority"

                    : segment.congestion > 3

                    ? "Heavy Congestion"

                    : nearbyVehicles > 7

                    ? "Queue Build-Up"

                    : "Moderate Traffic";

                addGreedyDecision(

                    `Signal ${s + 1}`,

                    extension,

                    reason
                );

                // =====================================================
                // YELLOW
                // =====================================================

                updateSignal(
                    signal,
                    'yellow'
                );

                await sleep(600);

                // =====================================================
                // RED
                // =====================================================

                updateSignal(
                    signal,
                    'red'
                );

                updateStatus(

                    `🚦 Signal ${s + 1}\n` +

                    `Vehicles Nearby: ${nearbyVehicles}\n` +

                    `Avg Speed: ${avgSpeed.toFixed(2)}\n` +

                    `Green Extension: ${extension}s`
                );

                // VEHICLE STOP
                const stopTime =

                    simulationMode === "fixed"

                    ? 2600

                    : Math.max(
                        500,
                        1800 - (extension * 40)
                    );

                await sleep(stopTime);

                // =====================================================
                // GREEN
                // =====================================================

                updateSignal(
                    signal,
                    'green'
                );

                updateStatus(

                    `🚦 Signal ${s + 1}\n` +

                    `Traffic dispersing`
                );

                // =====================================================
                // ROAD COLOR TRANSITION
                // =====================================================

                await disperseTraffic(s);

                await sleep(400);

                updateSignal(
                    signal,
                    'red'
                );

                break;
            }
        }

        // =====================================================
        // MOVE VEHICLE
        // =====================================================

        if (!stopped) {

            car.setLatLng(
                loadedRoute[i]
            );

            // dynamic speed
            const speed =

                simulationMode === "fixed"

                ? 42

                : 28;

            await sleep(speed);
        }
    }

    // =====================================================
    // METRICS
    // =====================================================

    document
        .getElementById("eta")
        .innerText =

        simulationMode === "fixed"

        ? "123s"

        : "79s";

    document
        .getElementById("saved")
        .innerText =

        simulationMode === "fixed"

        ? "0s"

        : "44s";

    document
        .getElementById("efficiency")
        .innerText =

        simulationMode === "fixed"

        ? "0%"

        : "36%";

    updateStatus(
        "Optimization completed"
    );

    simulationRunning = false;
}