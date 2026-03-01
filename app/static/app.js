/* ================================================================
   AI-Orbit Intelligence 3D — Globe.gl Application (Sprint 9)

   Full-scale catalogue, orbit-type filters, logarithmic visual
   altitude compression, interactive anomaly list.
   Sprint 7: Toggle Vectors, Top 10, Wiki Enrichment, Active
             Selection (RED), Footer, Paths to Earth.
   Sprint 8: Strategic OSINT Filters (Owner & Object Type),
             SATCAT-enriched data display in tooltips & wiki modal.
   Sprint 9: Client-Side Orbital Animation (Play/Pause).
             Uses mean_motion & inclination from the API to animate
             satellite positions in real time via requestAnimationFrame.

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
var ORBIT_SPEED_FACTOR = 10; // Sprint 9: acceleration factor so motion is visible

// -------------------------------------------------------------------
// Global state
// -------------------------------------------------------------------
var currentFilter = "ALL";
var showVectors   = true;
var selectedSatelliteId = null;
var currentData = [];

// Sprint 9: orbital animation state
var isPlaying = false;
var animationFrameId = null;
var lastFrameTime = null;

// -------------------------------------------------------------------
// DOM refs
// -------------------------------------------------------------------
var elTotalSats      = document.getElementById("total-sats");
var elAnomaliesCount = document.getElementById("anomalies-count");
var elStatus         = document.getElementById("status-text");
var elAnomaliesList  = document.getElementById("anomalies-list");

// Wiki modal refs
var elWikiModal   = document.getElementById("wiki-modal");
var elWikiClose   = document.getElementById("wiki-close");
var elWikiTitle   = document.getElementById("wiki-title");
var elWikiOwnerType = document.getElementById("wiki-owner-type");
var elWikiContent = document.getElementById("wiki-content");

// Sprint 8: Strategic filter refs
var elFilterOwner = document.getElementById("filter-owner");
var elFilterType  = document.getElementById("filter-type");

// Sprint 9: Play/Pause button ref
var elPlayOrbitBtn = document.getElementById("play-orbit-btn");

// -------------------------------------------------------------------
// Visual altitude: logarithmic compression
// -------------------------------------------------------------------
function visualAltitude(altKm) {
  return Math.log10(altKm + 1) / 5;
}

// -------------------------------------------------------------------
// Build paths data: lines from Earth surface to satellite position
// Only generated when showVectors is true.
// -------------------------------------------------------------------
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

// -------------------------------------------------------------------
// Sprint 9: Update vectors helper (called during animation loop)
// -------------------------------------------------------------------
function updateVectors() {
  var paths = buildPathsData(currentData);
  myGlobe.pathsData(paths);
}

// -------------------------------------------------------------------
// Globe initialisation — using pointsData + pathsData
// -------------------------------------------------------------------
var myGlobe = Globe()(document.getElementById("globeViz"))
  .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
  .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
  .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
  .showAtmosphere(true)
  .atmosphereColor("#0442BF")
  .atmosphereAltitude(0.25)

  // Points layer: satellites as small 3D dots at altitude
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

  // Paths layer: vertical lines from Earth to satellite
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

  // Rings layer (anomaly pulse)
  .ringsData([])
  .ringLat("lat")
  .ringLng("lng")
  .ringAltitude(function(d) { return visualAltitude(d.altitude); })
  .ringColor(function() { return COLOR_RING; })
  .ringMaxRadius(2)
  .ringPropagationSpeed(2)
  .ringRepeatPeriod(1400);

// Slow auto-rotation
myGlobe.controls().autoRotate = true;
myGlobe.controls().autoRotateSpeed = 0.3;

// -------------------------------------------------------------------
// Filter buttons (orbit type / anomalies)
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

// -------------------------------------------------------------------
// Sprint 8: Strategic OSINT filter dropdowns
// -------------------------------------------------------------------
if (elFilterOwner) {
  elFilterOwner.addEventListener("change", function() {
    fetchData();
  });
}
if (elFilterType) {
  elFilterType.addEventListener("change", function() {
    fetchData();
  });
}

// -------------------------------------------------------------------
// Toggle Vectors button
// -------------------------------------------------------------------
var toggleVectorsBtn = document.getElementById("toggle-vectors-btn");
if (toggleVectorsBtn) {
  toggleVectorsBtn.addEventListener("click", function() {
    showVectors = !showVectors;
    toggleVectorsBtn.style.background = showVectors ? "rgba(242,198,65,0.2)" : "";

    // Update point altitude to show/hide the vertical offset
    myGlobe.pointAltitude(function(d) {
      return showVectors ? visualAltitude(d.altitude) : 0.01;
    });

    // Update paths: show or hide vector lines
    var paths = buildPathsData(currentData);
    myGlobe.pathsData(paths);
  });
}

// -------------------------------------------------------------------
// Sprint 9: Play/Pause Orbit Animation
// -------------------------------------------------------------------
if (elPlayOrbitBtn) {
  elPlayOrbitBtn.addEventListener("click", function() {
    isPlaying = !isPlaying;

    if (isPlaying) {
      // Performance guard: don't animate if too many satellites
      if (currentData.length >= 3000) {
        alert("Please use filters to reduce the number of satellites (e.g. LEO or TOP10) before playing animation for better performance.");
        isPlaying = false;
        return;
      }

      elPlayOrbitBtn.innerHTML = "\u23F8 Pause Orbit";
      elPlayOrbitBtn.style.background = "rgba(242,198,65,0.2)";
      lastFrameTime = performance.now();
      animationFrameId = requestAnimationFrame(animateOrbits);
    } else {
      elPlayOrbitBtn.innerHTML = "\u25B6 Play Orbit (Real-Time)";
      elPlayOrbitBtn.style.background = "";
      if (animationFrameId !== null) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
      lastFrameTime = null;
    }
  });
}

// -------------------------------------------------------------------
// Sprint 9: Orbital Animation Loop
// Uses requestAnimationFrame to update satellite positions each frame.
// Approximation: longitude changes based on mean_motion.
// A satellite with mean_motion = N revs/day moves N*360 degrees/day
// relative to an inertial frame. Earth rotates ~360°/day too, so the
// *ground-track* drift ≈ (mean_motion - 1) * 360° / 86400 per second.
// We multiply by ORBIT_SPEED_FACTOR so it's visually perceptible.
// Latitude oscillates using inclination for a simplified sinusoidal
// ground-track approximation.
// -------------------------------------------------------------------
function animateOrbits(timestamp) {
  if (!isPlaying) return;

  // Calculate elapsed seconds since last frame
  if (lastFrameTime === null) {
    lastFrameTime = timestamp;
  }
  var deltaSec = (timestamp - lastFrameTime) / 1000.0;
  lastFrameTime = timestamp;

  // Clamp delta to avoid huge jumps if tab was backgrounded
  if (deltaSec > 0.5) deltaSec = 0.016;

  for (var i = 0; i < currentData.length; i++) {
    var d = currentData[i];
    var mm = d.mean_motion || 0;
    var incl = d.inclination || 0;

    if (mm === 0) continue; // no orbital data, skip

    // Degrees per second that the satellite's ground-track longitude shifts
    // (mean_motion - 1) accounts for Earth's own rotation (~1 rev/day)
    var degPerSec = ((mm - 1) * 360.0) / 86400.0;

    // Apply accelerated delta
    d.lng += degPerSec * deltaSec * ORBIT_SPEED_FACTOR;

    // Wrap longitude to [-180, 180]
    if (d.lng > 180) d.lng -= 360;
    if (d.lng < -180) d.lng += 360;

    // Simplified latitude oscillation using inclination
    // We track a pseudo orbital phase per satellite; initialise if missing
    if (d._orbPhase === undefined) {
      // Initialise phase from current latitude and inclination
      if (incl > 0) {
        d._orbPhase = Math.asin(Math.max(-1, Math.min(1, d.lat / incl)));
      } else {
        d._orbPhase = 0;
      }
    }

    // Orbital angular velocity in rad/sec
    var orbAngVel = (mm * 2 * Math.PI) / 86400.0;
    d._orbPhase += orbAngVel * deltaSec * ORBIT_SPEED_FACTOR;

    // Keep phase bounded
    if (d._orbPhase > 2 * Math.PI) d._orbPhase -= 2 * Math.PI;

    // Latitude = inclination * sin(phase) — simplified ground-track
    d.lat = incl * Math.sin(d._orbPhase);

    // Clamp latitude to valid range
    if (d.lat > 90) d.lat = 90;
    if (d.lat < -90) d.lat = -90;
  }

  // Push updated positions to the globe
  myGlobe.pointsData(currentData);

  // Update vector lines if visible
  if (showVectors) {
    updateVectors();
  }

  // Request next frame
  animationFrameId = requestAnimationFrame(animateOrbits);
}

// -------------------------------------------------------------------
// Wikipedia enrichment
// -------------------------------------------------------------------
async function fetchWikipediaInfo(satelliteName, owner, objectType) {
  // Clean name: remove trailing parenthetical like " (1)" and tags
  var cleanName = satelliteName
    .replace(/\s*\(\d+\)\s*$/, "")
    .replace(/\s*\[.*?\]\s*$/, "")
    .trim();

  elWikiTitle.textContent = cleanName;

  // Sprint 8: show owner & object type under title
  if (elWikiOwnerType) {
    var metaText = "";
    if (owner && owner !== "UNKNOWN") metaText += "Owner: " + owner;
    if (objectType && objectType !== "UNKNOWN") {
      if (metaText) metaText += " \u00B7 ";
      metaText += "Type: " + objectType;
    }
    elWikiOwnerType.textContent = metaText || "";
  }

  elWikiContent.textContent = "Loading Wikipedia data...";
  elWikiModal.style.display = "block";

  try {
    var url = "https://en.wikipedia.org/api/rest_v1/page/summary/" +
      encodeURIComponent(cleanName);
    var res = await fetch(url);
    if (res.status === 404 || !res.ok) {
      elWikiContent.textContent = "No historical data found for this object in Wikipedia.";
      return;
    }
    var data = await res.json();
    elWikiTitle.textContent = data.title || cleanName;
    elWikiContent.textContent = data.extract ||
      "No historical data found for this object in Wikipedia.";
  } catch (err) {
    console.error("[orbit-intel] Wikipedia fetch error:", err);
    elWikiContent.textContent =
      "No historical data found for this object in Wikipedia.";
  }
}

// -------------------------------------------------------------------
// Close wiki modal
// -------------------------------------------------------------------
if (elWikiClose) {
  elWikiClose.addEventListener("click", function() {
    elWikiModal.style.display = "none";
    selectedSatelliteId = null;
    // Refresh colours to deselect
    myGlobe.pointsData(currentData);
    myGlobe.pathsData(buildPathsData(currentData));
  });
}

// -------------------------------------------------------------------
// Handle satellite click (globe point or anomaly panel)
// -------------------------------------------------------------------
function handleSatelliteClick(d) {
  selectedSatelliteId = d.norad_id;

  // Zoom to satellite
  myGlobe.pointOfView(
    { lat: d.lat, lng: d.lng, altitude: visualAltitude(d.altitude || d.alt) + 0.5 },
    1000
  );

  // Fetch Wikipedia info — pass owner & type (Sprint 8)
  fetchWikipediaInfo(d.name, d.owner || "", d.object_type || "");

  // Force refresh colours: selected satellite becomes RED
  myGlobe.pointsData(currentData);
  myGlobe.pathsData(buildPathsData(currentData));
}

// -------------------------------------------------------------------
// Build tooltip HTML
// -------------------------------------------------------------------
function buildTooltip(s) {
  var nameColor = s.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL;
  if (s.norad_id === selectedSatelliteId) nameColor = COLOR_SELECTED;
  return (
    '<div style="font-family:Helvetica,Arial,sans-serif;' +
    'font-size:12px;line-height:1.5;padding:6px 10px;' +
    'background:rgba(2,24,89,0.92);border-radius:6px;' +
    'border:1px solid ' + nameColor + ';">' +
    '<b style="color:' + nameColor + ';">' + s.name + '</b><br>' +
    '<span style="opacity:0.7;">NORAD:</span> ' + s.norad_id + '<br>' +
    '<span style="opacity:0.7;">Orbit:</span> ' + s.orbit_type + '<br>' +
    '<span style="opacity:0.7;">Alt:</span> ' + s.alt.toFixed(0) + ' km<br>' +
    '<span style="opacity:0.7;">Owner:</span> ' + (s.owner || 'UNKNOWN') + '<br>' +
    '<span style="opacity:0.7;">Type:</span> ' + (s.object_type || 'UNKNOWN') + '<br>' +
    '<span style="opacity:0.7;">Mean Motion:</span> ' + (s.mean_motion ? s.mean_motion.toFixed(2) + ' rev/d' : 'N/A') + '<br>' +
    '<span style="opacity:0.7;">Inclination:</span> ' + (s.inclination ? s.inclination.toFixed(2) + '\u00B0' : 'N/A') + '<br>' +
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
  var sorted = anomalies.slice().sort(function(a, b) {
    return b.anomaly_score - a.anomaly_score;
  });
  var top = sorted.slice(0, 50);

  var html = "";
  top.forEach(function(s) {
    html +=
      '<div class="anomaly-item" ' +
      'data-lat="' + s.lat + '" ' +
      'data-lon="' + s.lng + '" ' +
      'data-alt="' + s.altitude + '" ' +
      'data-norad="' + s.norad_id + '" ' +
      'data-name="' + s.name + '" ' +
      'data-owner="' + (s.owner || '') + '" ' +
      'data-objtype="' + (s.object_type || '') + '">' +
      '<div class="anomaly-item-name">' + s.name + '</div>' +
      '<div class="anomaly-item-details">' +
      s.orbit_type + ' \u00B7 ' + s.alt.toFixed(0) + ' km \u00B7 ' +
      (s.owner && s.owner !== 'UNKNOWN' ? s.owner + ' \u00B7 ' : '') +
      'Score: <span class="anomaly-item-score">' +
      s.anomaly_score.toFixed(4) + '</span></div></div>';
  });
  elAnomaliesList.innerHTML = html;

  // Bind click on each anomaly item in the side panel
  var items = elAnomaliesList.querySelectorAll(".anomaly-item");
  items.forEach(function(item) {
    item.addEventListener("click", function() {
      var lat = parseFloat(item.getAttribute("data-lat"));
      var lon = parseFloat(item.getAttribute("data-lon"));
      var alt = parseFloat(item.getAttribute("data-alt"));
      var noradId = parseInt(item.getAttribute("data-norad"), 10);
      var name = item.getAttribute("data-name");
      var owner = item.getAttribute("data-owner");
      var objtype = item.getAttribute("data-objtype");

      handleSatelliteClick({
        lat: lat,
        lng: lon,
        altitude: alt,
        alt: alt,
        norad_id: noradId,
        name: name,
        owner: owner,
        object_type: objtype
      });
    });
  });
}

// -------------------------------------------------------------------
// Data fetching — Sprint 8: includes owner & object_type params
// Sprint 9: also maps mean_motion & inclination from API response
// -------------------------------------------------------------------
async function fetchData() {
  try {
    var url = API_URL + "?filter_type=" + currentFilter;

    // Sprint 8: append strategic OSINT filters
    var ownerVal = elFilterOwner ? elFilterOwner.value : "";
    var typeVal  = elFilterType  ? elFilterType.value  : "";
    if (ownerVal) {
      url += "&owner=" + encodeURIComponent(ownerVal);
    }
    if (typeVal) {
      url += "&object_type=" + encodeURIComponent(typeVal);
    }

    var res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    var data = res.json ? await res.json() : {};

    var total = data.total_satellites;
    var anomalies = data.satellites.filter(function(s) { return s.is_anomaly; });

    elTotalSats.textContent = total.toLocaleString();
    elAnomaliesCount.textContent = anomalies.length.toLocaleString();
    elStatus.textContent = "Live \u2014 " + new Date().toLocaleTimeString();

    // Points data for Globe.gl built-in points layer
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
        // Sprint 9: orbital dynamics for client-side animation
        mean_motion: s.mean_motion || 0.0,
        inclination: s.inclination || 0.0
      };
    });

    var rings = anomalies.map(function(s) {
      return { lat: s.lat, lng: s.lon, altitude: s.alt };
    });

    // Store globally for selection refresh
    currentData = points;

    // Sprint 9: reset orbital phase tracking when new data arrives
    // (so animateOrbits re-initialises _orbPhase from new lat values)
    for (var i = 0; i < currentData.length; i++) {
      delete currentData[i]._orbPhase;
    }

    myGlobe.pointsData(points);
    myGlobe.ringsData(rings);

    // Build and update paths (vector lines)
    var paths = buildPathsData(points);
    myGlobe.pathsData(paths);

    // Build anomalies panel from points (already mapped)
    var anomalyPoints = points.filter(function(p) { return p.is_anomaly; });
    buildAnomaliesPanel(anomalyPoints);

    // Sprint 9: if animation is playing but new data exceeds limit, stop it
    if (isPlaying && currentData.length >= 3000) {
      isPlaying = false;
      if (animationFrameId !== null) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
      lastFrameTime = null;
      if (elPlayOrbitBtn) {
        elPlayOrbitBtn.innerHTML = "\u25B6 Play Orbit (Real-Time)";
        elPlayOrbitBtn.style.background = "";
      }
    }

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
