/* ================================================================
   AI-Orbit Intelligence 3D — Globe.gl Application  (Sprint 6)

   Full-scale catalogue, orbit-type filters, logarithmic visual
   altitude compression, interactive anomaly list.
   Uses customLayerData + THREE.js sprites for true dot rendering
   (no hedgehog lines).
   ================================================================ */

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------
var API_URL    = "/api/positions";
var REFRESH_MS = 5000;

var COLOR_NORMAL  = "#0442BF";
var COLOR_ANOMALY = "#F2C641";
var COLOR_RING    = "rgba(242, 198, 65, 0.35)";

// -------------------------------------------------------------------
// Global state
// -------------------------------------------------------------------
var currentFilter = "ALL";

// -------------------------------------------------------------------
// DOM refs
// -------------------------------------------------------------------
var elTotalSats      = document.getElementById("total-sats");
var elAnomaliesCount = document.getElementById("anomalies-count");
var elStatus         = document.getElementById("status-text");
var elAnomaliesList  = document.getElementById("anomalies-list");

// -------------------------------------------------------------------
// Visual altitude: logarithmic compression
// -------------------------------------------------------------------
function visualAltitude(altKm) {
    return Math.log10(altKm + 1) / 5;
}

// -------------------------------------------------------------------
// THREE.js helpers — create a circle sprite texture
// -------------------------------------------------------------------
function createCircleTexture(color, size) {
    var canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    var ctx = canvas.getContext("2d");
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2 - 1, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    var tex = new THREE.CanvasTexture(canvas);
    return tex;
}

var texNormal  = null;
var texAnomaly = null;

function getTexture(isAnomaly) {
    if (isAnomaly) {
        if (!texAnomaly) texAnomaly = createCircleTexture(COLOR_ANOMALY, 64);
        return texAnomaly;
    }
    if (!texNormal) texNormal = createCircleTexture(COLOR_NORMAL, 64);
    return texNormal;
}

// -------------------------------------------------------------------
// Globe initialisation
// -------------------------------------------------------------------
var myGlobe = Globe()(document.getElementById("globeViz"))
    .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
    .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
    .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
    .showAtmosphere(true)
    .atmosphereColor("#0442BF")
    .atmosphereAltitude(0.25)

    // Custom layer: THREE.js sprites as true floating dots
    .customLayerData([])
    .customThreeObject(function (d) {
        var sprite = new THREE.Sprite(
            new THREE.SpriteMaterial({
                map: getTexture(d.is_anomaly),
                transparent: true,
                depthWrite: false
            })
        );
        var s = d.is_anomaly ? 1.8 : 0.7;
        sprite.scale.set(s, s, 1);
        sprite.__data = d;
        return sprite;
    })
    .customThreeObjectUpdate(function (obj, d) {
        Object.assign(obj.position, myGlobe.getCoords(d.lat, d.lng, visualAltitude(d.altitude)));
        var s = d.is_anomaly ? 1.8 : 0.7;
        obj.scale.set(s, s, 1);
        obj.__data = d;
    })
    .onCustomLayerClick(function (obj) {
        var d = obj.__data || obj;
        myGlobe.pointOfView(
            { lat: d.lat, lng: d.lng, altitude: visualAltitude(d.altitude) + 0.5 },
            1000
        );
    })
    .customLayerLabel(function (obj) {
        var d = obj.__data || obj;
        return buildTooltip(d);
    })

    // Rings layer (anomaly pulse)
    .ringsData([])
    .ringLat("lat")
    .ringLng("lng")
    .ringAltitude(function (d) {
        return visualAltitude(d.altitude);
    })
    .ringColor(function () { return COLOR_RING; })
    .ringMaxRadius(2)
    .ringPropagationSpeed(2)
    .ringRepeatPeriod(1400);

// Slow auto-rotation
myGlobe.controls().autoRotate = true;
myGlobe.controls().autoRotateSpeed = 0.3;

// -------------------------------------------------------------------
// Filter buttons
// -------------------------------------------------------------------
var filterButtons = document.querySelectorAll(".filter-btn");

filterButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
        filterButtons.forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        currentFilter = btn.getAttribute("data-filter");
        fetchData();
    });
});

// -------------------------------------------------------------------
// Build tooltip HTML
// -------------------------------------------------------------------
function buildTooltip(s) {
    var nameColor = s.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL;
    return (
        '<div style="font-family:Helvetica,Arial,sans-serif;' +
        'font-size:12px;line-height:1.5;padding:6px 10px;' +
        'background:rgba(2,24,89,0.92);border-radius:6px;' +
        'border:1px solid ' + nameColor + ';">' +
        '<b style="color:' + nameColor + ';">' + s.name + '</b><br>' +
        '<span style="opacity:0.7;">Orbit:</span> ' + s.orbit_type + '<br>' +
        '<span style="opacity:0.7;">Alt:</span> ' + s.alt.toFixed(0) + ' km<br>' +
        '<span style="opacity:0.7;">AI Score:</span> ' +
        '<span style="color:' + (s.anomaly_score > 0.5 ? COLOR_ANOMALY : COLOR_NORMAL) +
        ';font-weight:700;">' + s.anomaly_score.toFixed(4) + '</span>' +
        '</div>'
    );
}

// -------------------------------------------------------------------
// Build anomalies panel HTML
// -------------------------------------------------------------------
function buildAnomaliesPanel(anomalies) {
    if (anomalies.length === 0) {
        elAnomaliesList.innerHTML =
            '<p style="opacity:0.5;font-size:0.75rem;">No anomalies in current view.</p>';
        return;
    }

    var sorted = anomalies.slice().sort(function (a, b) {
        return b.anomaly_score - a.anomaly_score;
    });
    var top = sorted.slice(0, 50);

    var html = "";
    top.forEach(function (s) {
        html +=
            '<div class="anomaly-item" ' +
            'data-lat="' + s.lat + '" ' +
            'data-lon="' + s.lon + '" ' +
            'data-alt="' + s.alt + '">' +
            '<div class="anomaly-item-name">' + s.name + '</div>' +
            '<div class="anomaly-item-details">' +
            s.orbit_type + ' \u00B7 ' + s.alt.toFixed(0) + ' km \u00B7 ' +
            'Score: <span class="anomaly-item-score">' +
            s.anomaly_score.toFixed(4) + '</span>' +
            '</div></div>';
    });

    elAnomaliesList.innerHTML = html;

    var items = elAnomaliesList.querySelectorAll(".anomaly-item");
    items.forEach(function (item) {
        item.addEventListener("click", function () {
            var lat = parseFloat(item.getAttribute("data-lat"));
            var lon = parseFloat(item.getAttribute("data-lon"));
            var alt = parseFloat(item.getAttribute("data-alt"));
            myGlobe.pointOfView(
                { lat: lat, lng: lon, altitude: visualAltitude(alt) + 0.5 },
                1000
            );
        });
    });
}

// -------------------------------------------------------------------
// Data fetching
// -------------------------------------------------------------------
async function fetchData() {
    try {
        var url = API_URL + "?filter_type=" + currentFilter;
        var res = await fetch(url);
        if (!res.ok) throw new Error("HTTP " + res.status);
        var data = await res.json();

        var total = data.total_satellites;
        var anomalies = data.satellites.filter(function (s) {
            return s.is_anomaly;
        });

        elTotalSats.textContent = total.toLocaleString();
        elAnomaliesCount.textContent = anomalies.length.toLocaleString();
        elStatus.textContent = "Live \u2014 " + new Date().toLocaleTimeString();

        // Custom layer data: dots positioned at altitude
        var dots = data.satellites.map(function (s) {
            return {
                lat: s.lat,
                lng: s.lon,
                altitude: s.alt,
                is_anomaly: s.is_anomaly,
                orbit_type: s.orbit_type,
                anomaly_score: s.anomaly_score,
                name: s.name
            };
        });

        var rings = anomalies.map(function (s) {
            return { lat: s.lat, lng: s.lon, altitude: s.alt };
        });

        myGlobe.customLayerData(dots);
        myGlobe.ringsData(rings);

        buildAnomaliesPanel(anomalies);

    } catch (err) {
        console.error("[orbit-intel] fetch error:", err);
        elStatus.textContent = "Connection lost \u2014 retrying\u2026";
    }
}

// -------------------------------------------------------------------
// Bootstrap
// -------------------------------------------------------------------
fetchData();
setInterval(fetchData, REFRESH_MS);
