/* ================================================================
   AI-Orbit Intelligence 3D — Globe.gl Application  (Sprint 6)

   Full-scale catalogue, orbit-type filters, logarithmic visual
   altitude compression, interactive anomaly list, spherical points.
   ================================================================ */

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------
var API_URL   = "/api/positions";
var REFRESH_MS = 5000;           // 5 s refresh for 10k+ satellites

var COLOR_NORMAL  = "#0442BF";   // Brilliant Blue
var COLOR_ANOMALY = "#F2C641";   // Golden Yellow
var COLOR_RING    = "rgba(242, 198, 65, 0.35)";

// -------------------------------------------------------------------
// Global state
// -------------------------------------------------------------------
var currentFilter = "ALL";

// -------------------------------------------------------------------
// DOM refs
// -------------------------------------------------------------------
var elTotalSats     = document.getElementById("total-sats");
var elAnomaliesCount = document.getElementById("anomalies-count");
var elStatus        = document.getElementById("status-text");
var elAnomaliesList = document.getElementById("anomalies-list");

// -------------------------------------------------------------------
// Visual altitude: logarithmic compression
// -------------------------------------------------------------------
// LEO  (~400 km)  -> log10(401)  / 5 ~ 0.52  -> visible close to globe
// MEO  (~20k km)  -> log10(20001)/ 5 ~ 0.86
// GEO  (~35786)   -> log10(35787)/ 5 ~ 0.91  -> still on screen
// -------------------------------------------------------------------
function visualAltitude(altKm) {
    return Math.log10(altKm + 1) / 5;
}

// -------------------------------------------------------------------
// Globe initialisation — spherical points (no lines / hedgehog)
// -------------------------------------------------------------------
var myGlobe = Globe()(document.getElementById("globeViz"))
    .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
    .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
    .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
    .showAtmosphere(true)
    .atmosphereColor("#0442BF")
    .atmosphereAltitude(0.25)

    // Points layer (satellites) — spherical dots, no lines
    .pointsData([])
    .pointLat("lat")
    .pointLng("lng")
    .pointAltitude(function (d) {
        return visualAltitude(d.altitude);
    })
    .pointRadius(function (d) {
        return d.is_anomaly ? 0.05 : 0.02;
    })
    .pointColor(function (d) {
        return d.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL;
    })
    .pointLabel(function (d) {
        return d.labelHtml;
    })
    .onPointClick(function (d) {
        myGlobe.pointOfView(
            {
                lat: d.lat,
                lng: d.lng,
                altitude: visualAltitude(d.altitude) + 0.5
            },
            1000
        );
    })

    // Rings layer (anomaly pulse)
    .ringsData([])
    .ringLat("lat")
    .ringLng("lng")
    .ringAltitude(function (d) {
        return visualAltitude(d.altitude);
    })
    .ringColor(function () {
        return COLOR_RING;
    })
    .ringMaxRadius(2)
    .ringPropagationSpeed(2)
    .ringRepeatPeriod(1400);

// Slow auto-rotation
myGlobe.controls().autoRotate = true;
myGlobe.controls().autoRotateSpeed = 0.3;

// -------------------------------------------------------------------
// Filter buttons — wiring
// -------------------------------------------------------------------
var filterButtons = document.querySelectorAll(".filter-btn");

filterButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
        // Update active class
        filterButtons.forEach(function (b) {
            b.classList.remove("active");
        });
        btn.classList.add("active");

        // Update global filter and refetch
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
        '<span style="color:' + (s.anomaly_score > 0.5 ? COLOR_ANOMALY : COLOR_NORMAL) + ';font-weight:700;">' +
        s.anomaly_score.toFixed(4) + '</span>' +
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

    // Sort by score descending, show top 50
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
            '</div>' +
            '</div>';
    });

    elAnomaliesList.innerHTML = html;

    // Attach click-to-zoom
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

        // Counters
        var total = data.total_satellites;
        var anomalies = data.satellites.filter(function (s) {
            return s.is_anomaly;
        });

        elTotalSats.textContent = total.toLocaleString();
        elAnomaliesCount.textContent = anomalies.length.toLocaleString();
        elStatus.textContent = "Live \u2014 " + new Date().toLocaleTimeString();

        // Format for Globe.gl — spherical points
        var points = data.satellites.map(function (s) {
            return {
                lat: s.lat,
                lng: s.lon,
                altitude: s.alt,
                is_anomaly: s.is_anomaly,
                orbit_type: s.orbit_type,
                anomaly_score: s.anomaly_score,
                name: s.name,
                labelHtml: buildTooltip(s)
            };
        });

        // Rings only on anomalies
        var rings = anomalies.map(function (s) {
            return {
                lat: s.lat,
                lng: s.lon,
                altitude: s.alt
            };
        });

        myGlobe.pointsData(points);
        myGlobe.ringsData(rings);

        // Build anomalies list panel
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
