/* ================================================================
   AI-Orbit Intelligence 3D — Globe.gl Application (Sprint 11)
   Full-scale catalogue, orbit-type filters, logarithmic visual
   altitude compression, interactive anomaly list.
   Sprint 7: Toggle Vectors, Top 10, Wiki Enrichment, Active
             Selection (RED), Footer, Paths to Earth.
   Sprint 8: Strategic OSINT Filters (Owner & Object Type),
             SATCAT-enriched data display in tooltips & wiki modal.
   Sprint 9: Client-Side Orbital Animation (Play/Pause).
             Uses mean_motion & inclination from the API to animate
             satellite positions in real time via requestAnimationFrame.
   Sprint 10: Smart OSINT Fallback — generates a dynamic Telemetry
              Card when Wikipedia returns 404 or no extract.
              Auto-rotate disabled for stable camera during animation.
   Sprint 11: Search Bar (quick name/NORAD lookup with zoom) and
              Export CSV (client-side OSINT data download).
   Uses Globe.gl built-in pointsData + pathsData.
================================================================ */

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------
var API_URL     = "/api/positions";
var REFRESH_MS  = 5000;
var COLOR_NORMAL   = "#4DA6FF";
var COLOR_ANOMALY  = "#F2C641";
var COLOR_SELECTED = "#FF0000";
var COLOR_RING     = "rgba(242, 198, 65, 0.35)";
var ORBIT_SPEED_FACTOR = 10; 

// -------------------------------------------------------------------
// Global state
// -------------------------------------------------------------------
var currentFilter = "ALL";
var showVectors   = true;
var selectedSatelliteId = null;
var currentData = [];

var isPlaying = false;
var animationFrameId = null;
var lastFrameTime = null;

var isFetching = false;

// -------------------------------------------------------------------
// DOM refs
// -------------------------------------------------------------------
var elTotalSats      = document.getElementById("total-sats");
var elAnomaliesCount = document.getElementById("anomalies-count");
var elStatus         = document.getElementById("status-text");
var elAnomaliesList  = document.getElementById("anomalies-list");

var elWikiModal   = document.getElementById("wiki-modal");
var elWikiClose   = document.getElementById("wiki-close");
var elWikiTitle   = document.getElementById("wiki-title");
var elWikiOwnerType = document.getElementById("wiki-owner-type");
var elWikiContent = document.getElementById("wiki-content");

var elFilterOwner = document.getElementById("filter-owner");
var elFilterType  = document.getElementById("filter-type");

var elPlayOrbitBtn = document.getElementById("play-orbit-btn");

var elSearchInput     = document.getElementById("search-input");
var elSearchBtn       = document.getElementById("search-btn");

var elExportCsvBtn = document.getElementById("export-csv-btn");

// -------------------------------------------------------------------
// Visual altitude
// -------------------------------------------------------------------
function visualAltitude(altKm) {
    return Math.log10(altKm + 1) / 5;
}

function buildPathsData(points) {
    if (!showVectors) return [];
    return points.map(function(d) {
        return {
            coords: [
                [d.lat, d.lng, 0],
                [d.lat, d.lng, visualAltitude(d.altitude)]
            ],
            norad_id: d.norad_id,
            is_anomaly: d.is_anomaly
        };
    });
}

function updateVectors() {
    var paths = buildPathsData(currentData);
    myGlobe.pathsData(paths);
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
  .pointsData([])
  .pointLat("lat")
  .pointLng("lng")
  .pointAltitude(function(d) {
      return showVectors ? visualAltitude(d.altitude) : 0.01;
  })
  .pointRadius(function(d) {
      if (d.norad_id === selectedSatelliteId) return 0.18;
      return d.is_anomaly ? 0.15 : 0.1;
  })
  .pointColor(function(d) {
      if (d.norad_id === selectedSatelliteId) return COLOR_SELECTED;
      return d.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL;
  })
  .pointsMerge(false)
  .pointLabel(function(d) {
      return buildTooltip(d);
  })
  .onPointClick(function(d) {
      handleSatelliteClick(d);
  })
  .pathsData([])
  .pathPointLat(function(pnt) { return pnt[0]; })
  .pathPointLng(function(pnt) { return pnt[1]; })
  .pathPointAlt(function(pnt) { return pnt[2]; })
  .pathColor(function(d) {
      if (d.norad_id === selectedSatelliteId) return [COLOR_SELECTED, COLOR_SELECTED];
      return d.is_anomaly
        ? ["rgba(242,198,65,0.3)", "rgba(242,198,65,0.8)"]
        : ["rgba(77,166,255,0.1)", "rgba(77,166,255,0.4)"];
  })
  .pathStroke(0.4)
  .pathTransitionDuration(0)
  .pathDashLength(0.3)
  .pathDashGap(0.15)
  .pathDashAnimateTime(0)
  .ringsData([])
  .ringLat("lat")
  .ringLng("lng")
  .ringAltitude(function(d) { return visualAltitude(d.altitude); })
  .ringColor(function() { return COLOR_RING; })
  .ringMaxRadius(2)
  .ringPropagationSpeed(2)
  .ringRepeatPeriod(1400);

myGlobe.controls().autoRotate = false;
myGlobe.controls().autoRotateSpeed = 0.3;

// -------------------------------------------------------------------
// Events & Filters
// -------------------------------------------------------------------
var filterButtons = document.querySelectorAll(".filter-btn[data-filter]");
filterButtons.forEach(function(btn) {
    btn.addEventListener("click", function() {
        filterButtons.forEach(function(b) { b.classList.remove("active"); });
        btn.classList.add("active");
        currentFilter = btn.getAttribute("data-filter");
        fetchData();
    });
});

var _filterDebounceTimer = null;
function debouncedFetchData() {
    if (_filterDebounceTimer) clearTimeout(_filterDebounceTimer);
    _filterDebounceTimer = setTimeout(function() {
        fetchData();
    }, 150);
}

if (elFilterOwner) {
    elFilterOwner.addEventListener("change", function() { debouncedFetchData(); });
}
if (elFilterType) {
    elFilterType.addEventListener("change", function() { debouncedFetchData(); });
}

var toggleVectorsBtn = document.getElementById("toggle-vectors-btn");
if (toggleVectorsBtn) {
    toggleVectorsBtn.addEventListener("click", function() {
        showVectors = !showVectors;
        toggleVectorsBtn.style.background = showVectors ? "rgba(242,198,65,0.2)" : "";
        myGlobe.pointAltitude(function(d) {
            return showVectors ? visualAltitude(d.altitude) : 0.01;
        });
        var paths = buildPathsData(currentData);
        myGlobe.pathsData(paths);
    });
}

if (elPlayOrbitBtn) {
    elPlayOrbitBtn.addEventListener("click", function() {
        isPlaying = !isPlaying;
        if (isPlaying) {
            if (currentData.length >= 3000) {
                alert("Please use filters to reduce the number of satellites before playing animation.");
                isPlaying = false;
                return;
            }
            elPlayOrbitBtn.innerHTML = "⏸ Pause Orbit";
            elPlayOrbitBtn.style.background = "rgba(242,198,65,0.2)";
            lastFrameTime = performance.now();
            animationFrameId = requestAnimationFrame(animateOrbits);
        } else {
            elPlayOrbitBtn.innerHTML = "▶ Play Orbit (Real-Time)";
            elPlayOrbitBtn.style.background = "";
            if (animationFrameId !== null) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
            lastFrameTime = null;
        }
    });
}

function animateOrbits(timestamp) {
    if (!isPlaying) return;
    if (lastFrameTime === null) lastFrameTime = timestamp;
    var deltaSec = (timestamp - lastFrameTime) / 1000.0;
    lastFrameTime = timestamp;
    if (deltaSec > 0.5) deltaSec = 0.016;

    for (var i = 0; i < currentData.length; i++) {
        var d = currentData[i];
        var mm = d.mean_motion || 0;
        var incl = d.inclination || 0;
        if (mm === 0) continue; 
        var degPerSec = ((mm - 1) * 360.0) / 86400.0;
        d.lng += degPerSec * deltaSec * ORBIT_SPEED_FACTOR;
        if (d.lng > 180) d.lng -= 360;
        if (d.lng < -180) d.lng += 360;

        if (d._orbPhase === undefined) {
            if (incl > 0) d._orbPhase = Math.asin(Math.max(-1, Math.min(1, d.lat / incl)));
            else d._orbPhase = 0;
        }
        var orbAngVel = (mm * 2 * Math.PI) / 86400.0;
        d._orbPhase += orbAngVel * deltaSec * ORBIT_SPEED_FACTOR;
        if (d._orbPhase > 2 * Math.PI) d._orbPhase -= 2 * Math.PI;

        d.lat = incl * Math.sin(d._orbPhase);
        if (d.lat > 90) d.lat = 90;
        if (d.lat < -90) d.lat = -90;
    }
    myGlobe.pointsData(currentData);
    if (showVectors) updateVectors();
    animationFrameId = requestAnimationFrame(animateOrbits);
}

// -------------------------------------------------------------------
// Fallback Card
// -------------------------------------------------------------------
function buildOsintFallbackCard(satData) {
    var name = satData.name || "UNKNOWN OBJECT";
    var noradId = satData.norad_id || "N/A";
    var objectType = satData.object_type || "UNKNOWN";
    var owner = satData.owner || "UNKNOWN";
    var alt = satData.alt || satData.altitude || 0;
    var orbitType = satData.orbit_type || "N/A";
    var inclination = satData.inclination || 0;
    var meanMotion = satData.mean_motion || 0;
    var anomalyScore = satData.anomaly_score || 0;
    var isAnomaly = satData.is_anomaly || false;

    var statusClass = isAnomaly ? "osint-status-anomaly" : "osint-status-normal";
    var statusText = isAnomaly
        ? "🚨 ANOMALY DETECTED — Severity: " + anomalyScore.toFixed(4)
        : "✅ Normal — Score: " + anomalyScore.toFixed(4);

    return (
        '<div class="osint-card">' +
          '<div class="osint-header">' +
            '<span class="osint-tag">⚠️ OSINT TELEMETRY CARD</span>' +
            '<span class="osint-subtitle">No public historical data found — Displaying real-time intelligence</span>' +
          '</div>' +
          '<table class="osint-table">' +
            '<tr><td class="osint-label">Object</td><td class="osint-value">' + name + ' <span class="osint-norad">[NORAD ' + noradId + ']</span></td></tr>' +
            '<tr><td class="osint-label">Classification</td><td class="osint-value">' + objectType + '</td></tr>' +
            '<tr><td class="osint-label">Owner / Origin</td><td class="osint-value">' + owner + '</td></tr>' +
            '<tr><td class="osint-label">Orbit</td><td class="osint-value">' + orbitType + ' — ' + Math.round(alt) + ' km</td></tr>' +
            '<tr><td class="osint-label">Inclination</td><td class="osint-value">' + inclination.toFixed(2) + '°</td></tr>' +
            '<tr><td class="osint-label">Velocity</td><td class="osint-value">' + meanMotion.toFixed(4) + ' rev/day</td></tr>' +
            '<tr><td class="osint-label">AI Status</td><td class="osint-value ' + statusClass + '">' + statusText + '</td></tr>' +
          '</table>' +
        '</div>'
    );
}

async function fetchWikipediaInfo(satelliteName, satData) {
    var cleanName = satelliteName.replace(/\s*\(\d+\)\s*$/, "").replace(/\s*\[.*?\]\s*$/, "").trim();
    elWikiTitle.textContent = cleanName;

    if (elWikiOwnerType) {
        var metaText = "";
        var owner = (satData && satData.owner) || "";
        var objectType = (satData && satData.object_type) || "";
        if (owner && owner !== "UNKNOWN") metaText += "Owner: " + owner;
        if (objectType && objectType !== "UNKNOWN") {
            if (metaText) metaText += " · ";
            metaText += "Type: " + objectType;
        }
        elWikiOwnerType.textContent = metaText || "";
    }

    elWikiContent.innerHTML = '<span style="opacity:0.6;">Loading Wikipedia data...</span>';
    elWikiModal.style.display = "block";

    try {
        var url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + encodeURIComponent(cleanName);
        var res = await fetch(url);
        if (res.status === 404 || !res.ok) {
            if (satData) elWikiContent.innerHTML = buildOsintFallbackCard(satData);
            else elWikiContent.textContent = "No historical data found for this object.";
            return;
        }
        var data = await res.json();
        if (!data.extract || data.extract.trim().length === 0) {
            if (satData) {
                elWikiTitle.textContent = data.title || cleanName;
                elWikiContent.innerHTML = buildOsintFallbackCard(satData);
            } else {
                elWikiContent.textContent = "No historical data found for this object.";
            }
            return;
        }
        elWikiTitle.textContent = data.title || cleanName;
        elWikiContent.textContent = data.extract;
    } catch (err) {
        console.error("[orbit-intel] Wikipedia fetch error:", err);
        if (satData) elWikiContent.innerHTML = buildOsintFallbackCard(satData);
        else elWikiContent.textContent = "No historical data found for this object.";
    }
}

if (elWikiClose) {
    elWikiClose.addEventListener("click", function() {
        elWikiModal.style.display = "none";
        selectedSatelliteId = null;
        myGlobe.pointsData(currentData);
        myGlobe.pathsData(buildPathsData(currentData));
    });
}

function handleSatelliteClick(d) {
    selectedSatelliteId = d.norad_id;
    myGlobe.pointOfView({ lat: d.lat, lng: d.lng, altitude: visualAltitude(d.altitude || d.alt) + 0.5 }, 1000);
    fetchWikipediaInfo(d.name, d);
    myGlobe.pointsData(currentData);
    myGlobe.pathsData(buildPathsData(currentData));
}

function buildTooltip(s) {
    var nameColor = s.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL;
    if (s.norad_id === selectedSatelliteId) nameColor = COLOR_SELECTED;
    return (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;line-height:1.5;padding:6px 10px;background:rgba(2,24,89,0.92);border-radius:6px;border:1px solid ' + nameColor + ';">' +
        '<b style="color:' + nameColor + ';">' + s.name + '</b><br>' +
        '<span style="opacity:0.7;">NORAD:</span> ' + s.norad_id + '<br>' +
        '<span style="opacity:0.7;">Orbit:</span> ' + s.orbit_type + '<br>' +
        '<span style="opacity:0.7;">Alt:</span> ' + s.alt.toFixed(0) + ' km<br>' +
        '<span style="opacity:0.7;">Owner:</span> ' + (s.owner || 'UNKNOWN') + '<br>' +
        '<span style="opacity:0.7;">Type:</span> ' + (s.object_type || 'UNKNOWN') + '<br>' +
        '<span style="opacity:0.7;">Mean Motion:</span> ' + (s.mean_motion ? s.mean_motion.toFixed(2) + ' rev/d' : 'N/A') + '<br>' +
        '<span style="opacity:0.7;">Inclination:</span> ' + (s.inclination ? s.inclination.toFixed(2) + '°' : 'N/A') + '<br>' +
        '<span style="opacity:0.7;">AI Score:</span> ' +
        '<span style="color:' + (s.anomaly_score > 0.5 ? COLOR_ANOMALY : COLOR_NORMAL) + ';font-weight:700;">' + s.anomaly_score.toFixed(4) + '</span>' +
        '</div>'
    );
}

function buildAnomaliesPanel(anomalies) {
    if (anomalies.length === 0) {
        elAnomaliesList.innerHTML = '<p style="opacity:0.5;font-size:0.75rem;">No anomalies in current view.</p>';
        return;
    }
    var sorted = anomalies.slice().sort(function(a, b) { return b.anomaly_score - a.anomaly_score; });
    var top = sorted.slice(0, 50);
    var html = "";
    top.forEach(function(s) {
        html += '<div class="anomaly-item" data-lat="' + s.lat + '" data-lon="' + s.lng + '" data-alt="' + s.altitude + '" data-norad="' + s.norad_id + '" data-name="' + s.name + '" data-owner="' + (s.owner || '') + '" data-objtype="' + (s.object_type || '') + '" data-orbittype="' + (s.orbit_type || '') + '" data-inclination="' + (s.inclination || 0) + '" data-meanmotion="' + (s.mean_motion || 0) + '" data-anomalyscore="' + (s.anomaly_score || 0) + '" data-isanomaly="' + (s.is_anomaly ? '1' : '0') + '">' +
            '<div class="anomaly-item-name">' + s.name + '</div>' +
            '<div class="anomaly-item-details">' + s.orbit_type + ' · ' + s.alt.toFixed(0) + ' km · ' + (s.owner && s.owner !== 'UNKNOWN' ? s.owner + ' · ' : '') + 'Score: <span class="anomaly-item-score">' + s.anomaly_score.toFixed(4) + '</span></div></div>';
    });
    elAnomaliesList.innerHTML = html;
    var items = elAnomaliesList.querySelectorAll(".anomaly-item");
    items.forEach(function(item) {
        item.addEventListener("click", function() {
            handleSatelliteClick({
                lat: parseFloat(item.getAttribute("data-lat")),
                lng: parseFloat(item.getAttribute("data-lon")),
                altitude: parseFloat(item.getAttribute("data-alt")),
                alt: parseFloat(item.getAttribute("data-alt")),
                norad_id: parseInt(item.getAttribute("data-norad"), 10),
                name: item.getAttribute("data-name"),
                owner: item.getAttribute("data-owner"),
                object_type: item.getAttribute("data-objtype"),
                orbit_type: item.getAttribute("data-orbittype"),
                inclination: parseFloat(item.getAttribute("data-inclination")) || 0,
                mean_motion: parseFloat(item.getAttribute("data-meanmotion")) || 0,
                anomaly_score: parseFloat(item.getAttribute("data-anomalyscore")) || 0,
                is_anomaly: item.getAttribute("data-isanomaly") === "1"
            });
        });
    });
}

// -------------------------------------------------------------------
// Sprint 11: Search Bar Logic
// -------------------------------------------------------------------
function executeSearch() {
    if (!elSearchInput) return;
        var query = elSearchInput.value.trim().toUpperCase();
    if (!query) return;

    var match = currentData.find(function(s) {
        return s.name.toUpperCase().includes(query) || s.norad_id.toString() === query;
    });

    if (match) {
        handleSatelliteClick(match);
        elSearchInput.value = ""; 
    } else {
        alert("Object '" + query + "' not found in current view.");
    }
}

if (elSearchBtn) {
    elSearchBtn.addEventListener("click", executeSearch);
}
if (elSearchInput) {
    elSearchInput.addEventListener("keypress", function(e) {
        if (e.key === "Enter") executeSearch();
    });
}

// -------------------------------------------------------------------
// Sprint 11: Export CSV Logic
// -------------------------------------------------------------------
function exportToCSV() {
    if (currentData.length === 0) {
        alert("No data available to export.");
        return;
    }
    
    var headers = ["Name", "NORAD_ID", "Object_Type", "Owner", "Orbit_Type", "Altitude_km", "Inclination_deg", "Mean_Motion_rev_day", "Anomaly_Score", "Is_Anomaly"];
    
    var csvRows = [];
    csvRows.push(headers.join(","));
    
    currentData.forEach(function(s) {
        var row = [
            '"' + s.name + '"',
            s.norad_id,
            '"' + (s.object_type || 'UNKNOWN') + '"',
            '"' + (s.owner || 'UNKNOWN') + '"',
            '"' + (s.orbit_type || 'UNKNOWN') + '"',
            Math.round(s.alt || s.altitude),
            (s.inclination || 0).toFixed(4),
            (s.mean_motion || 0).toFixed(4),
            (s.anomaly_score || 0).toFixed(4),
            s.is_anomaly ? "TRUE" : "FALSE"
        ];
        csvRows.push(row.join(","));
    });
    
    var csvString = csvRows.join("\n");
    var blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    
    var link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "osint_orbit_data_" + new Date().toISOString().slice(0,10) + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

if (elExportCsvBtn) {
    elExportCsvBtn.addEventListener("click", exportToCSV);
}

// -------------------------------------------------------------------
// Data fetching
// -------------------------------------------------------------------
async function fetchData() {
    if (isFetching) return;
    isFetching = true;

    try {
        var url = API_URL + "?filter_type=" + currentFilter;
        var ownerVal = elFilterOwner ? elFilterOwner.value : "";
        var typeVal  = elFilterType  ? elFilterType.value  : "";
        if (ownerVal) url += "&owner=" + encodeURIComponent(ownerVal);
        if (typeVal) url += "&object_type=" + encodeURIComponent(typeVal);

        var res = await fetch(url);
        if (!res.ok) throw new Error("HTTP " + res.status);

        var data = res.json ? await res.json() : {};
        
        // --- PROTECTION (Évite l'erreur 'e.map is not a function' si le backend renvoie un objet vide) ---
        if (!data || !Array.isArray(data.satellites)) {
            console.warn("[orbit-intel] Backend returned invalid data. Skipping update.", data);
            throw new Error("Invalid data format received");
        }

        var total = data.total_satellites || 0;
        var anomalies = data.satellites.filter(function(s) { return s.is_anomaly; });

        elTotalSats.textContent = total.toLocaleString();
        elAnomaliesCount.textContent = anomalies.length.toLocaleString();
        elStatus.textContent = "Live — " + new Date().toLocaleTimeString();

        var points = data.satellites.map(function(s) {
            return {
                lat: s.lat,
                lng: s.lon,
                altitude: s.alt,
                is_anomaly: s.is_anomaly,
                orbit_type: s.orbit_type,
                anomaly_score: s.anomaly_score,
                name: s.name,
                norad_id: s.norad_id,
                alt: s.alt,
                owner: s.owner || "UNKNOWN",
                object_type: s.object_type || "UNKNOWN",
                mean_motion: s.mean_motion || 0.0,
                inclination: s.inclination || 0.0
            };
        });

        var rings = anomalies.map(function(s) {
            return { lat: s.lat, lng: s.lon, altitude: s.alt };
        });

        currentData = points;

        for (var i = 0; i < currentData.length; i++) {
            delete currentData[i]._orbPhase;
        }

        myGlobe.pointsData(points);
        myGlobe.ringsData(rings);

        var paths = buildPathsData(points);
        myGlobe.pathsData(paths);

        var anomalyPoints = points.filter(function(p) { return p.is_anomaly; });
        buildAnomaliesPanel(anomalyPoints);

        if (isPlaying && currentData.length >= 3000) {
            isPlaying = false;
            if (animationFrameId !== null) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
            lastFrameTime = null;
            if (elPlayOrbitBtn) {
                elPlayOrbitBtn.innerHTML = "▶ Play Orbit (Real-Time)";
                elPlayOrbitBtn.style.background = "";
            }
        }
    } catch (err) {
        console.error("[orbit-intel] fetch error:", err);
        elStatus.textContent = "Connection lost — retrying…";
    } finally {
        isFetching = false;
    }
}

// -------------------------------------------------------------------
// Bootstrap
// -------------------------------------------------------------------
fetchData();

function scheduleNextFetch() {
    setTimeout(function() {
        fetchData().then(scheduleNextFetch).catch(scheduleNextFetch);
    }, REFRESH_MS);
}
scheduleNextFetch();
