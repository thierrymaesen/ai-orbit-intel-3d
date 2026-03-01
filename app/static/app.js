/* ================================================================
   AI-Orbit Intelligence 3D — Globe.gl Application (Sprint 7)

   Full-scale catalogue, orbit-type filters, logarithmic visual
   altitude compression, interactive anomaly list.

   Sprint 7: Toggle Vectors, Top 10, Wiki Enrichment,
             Active Selection (RED), Footer, Paths to Earth.

   Uses Globe.gl built-in pointsData + pathsData.
   ================================================================ */

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------
var API_URL        = "/api/positions";
var REFRESH_MS     = 5000;
var COLOR_NORMAL   = "#4DA6FF";
var COLOR_ANOMALY  = "#F2C641";
var COLOR_SELECTED = "#FF0000";
var COLOR_RING     = "rgba(242, 198, 65, 0.35)";

// -------------------------------------------------------------------
// Global state
// -------------------------------------------------------------------
var currentFilter       = "ALL";
var showVectors         = true;
var selectedSatelliteId = null;
var currentData         = [];

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
var elWikiContent = document.getElementById("wiki-content");

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
    .ringAltitude(function(d) {
               return visualAltitude(d.altitude);
    })
    .ringColor(function() { return COLOR_RING; })
    .ringMaxRadius(2)
    .ringPropagationSpeed(2)
    .ringRepeatPeriod(1400);

// Slow auto-rotation
myGlobe.controls().autoRotate = true;
myGlobe.controls().autoRotateSpeed = 0.3;

// -------------------------------------------------------------------
// Filter buttons
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
// Toggle Vectors button
// -------------------------------------------------------------------
var toggleVectorsBtn = document.getElementById("toggle-vectors-btn");
if (toggleVectorsBtn) {
       toggleVectorsBtn.addEventListener("click", function() {
                  showVectors = !showVectors;
                  toggleVectorsBtn.style.background = showVectors
                      ? "rgba(242,198,65,0.2)"
                                 : "";

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
// Wikipedia enrichment
// -------------------------------------------------------------------
async function fetchWikipediaInfo(satelliteName) {
       // Clean name: remove trailing parenthetical like " (1)" and tags
    var cleanName = satelliteName
           .replace(/\s*\(\d+\)\s*$/, "")
           .replace(/\s*\[.*?\]\s*$/, "")
           .trim();

    elWikiTitle.textContent = cleanName;
       elWikiContent.textContent = "Loading Wikipedia data...";
       elWikiModal.style.display = "block";

    try {
               var url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
                       + encodeURIComponent(cleanName);
               var res = await fetch(url);

           if (res.status === 404 || !res.ok) {
                          elWikiContent.textContent =
                                             "No historical data found for this object in Wikipedia.";
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
       {
                      lat: d.lat,
                      lng: d.lng,
                      altitude: visualAltitude(d.altitude || d.alt) + 0.5
       },
               1000
           );

    // Fetch Wikipedia info
    fetchWikipediaInfo(d.name);

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
               '<div style="font-family:Helvetica,Arial,sans-serif;'
               + 'font-size:12px;line-height:1.5;padding:6px 10px;'
               + 'background:rgba(2,24,89,0.92);border-radius:6px;'
               + 'border:1px solid ' + nameColor + ';">'
               + '<b style="color:' + nameColor + ';">' + s.name + '</b><br>'
               + '<span style="opacity:0.7;">NORAD:</span> ' + s.norad_id + '<br>'
               + '<span style="opacity:0.7;">Orbit:</span> ' + s.orbit_type + '<br>'
               + '<span style="opacity:0.7;">Alt:</span> ' + s.alt.toFixed(0) + ' km<br>'
               + '<span style="opacity:0.7;">AI Score:</span> '
               + '<span style="color:'
               + (s.anomaly_score > 0.5 ? COLOR_ANOMALY : COLOR_NORMAL)
               + ';font-weight:700;">'
               + s.anomaly_score.toFixed(4)
               + '</span>'
               + '</div>'
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
                                 '<div class="anomaly-item" '
                      + 'data-lat="' + s.lat + '" '
                      + 'data-lon="' + s.lng + '" '
                      + 'data-alt="' + s.altitude + '" '
                      + 'data-norad="' + s.norad_id + '" '
                      + 'data-name="' + s.name + '">'
                      + '<div class="anomaly-item-name">' + s.name + '</div>'
                      + '<div class="anomaly-item-details">'
                      + s.orbit_type + ' \u00B7 '
                      + s.alt.toFixed(0) + ' km \u00B7 '
                      + 'Score: <span class="anomaly-item-score">'
                      + s.anomaly_score.toFixed(4)
                      + '</span></div></div>';
       });

    elAnomaliesList.innerHTML = html;

    // Bind click on each anomaly item in the side panel
    var items = elAnomaliesList.querySelectorAll(".anomaly-item");
       items.forEach(function(item) {
                  item.addEventListener("click", function() {
                                 var lat     = parseFloat(item.getAttribute("data-lat"));
                                 var lon     = parseFloat(item.getAttribute("data-lon"));
                                 var alt     = parseFloat(item.getAttribute("data-alt"));
                                 var noradId = parseInt(item.getAttribute("data-norad"), 10);
                                 var name    = item.getAttribute("data-name");

                                                    handleSatelliteClick({
                                                                       lat: lat,
                                                                       lng: lon,
                                                                       altitude: alt,
                                                                       alt: alt,
                                                                       norad_id: noradId,
                                                                       name: name
                                                    });
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

           var data = res.json ? await res.json() : {};

           var total     = data.total_satellites;
                  var anomalies = data.satellites.filter(function(s) {
                                 return s.is_anomaly;
                  });

           elTotalSats.textContent      = total.toLocaleString();
                  elAnomaliesCount.textContent = anomalies.length.toLocaleString();
                  elStatus.textContent         = "Live \u2014 " + new Date().toLocaleTimeString();

           // Points data for Globe.gl built-in points layer
           var points = data.satellites.map(function(s) {
                          return {
                                             lat:           s.lat,
                                             lng:           s.lon,
                                             altitude:      s.alt,
                                             is_anomaly:    s.is_anomaly,
                                             orbit_type:    s.orbit_type,
                                             anomaly_score: s.anomaly_score,
                                             name:          s.name,
                                             norad_id:      s.norad_id,
                                             alt:           s.alt
                          };
           });

           var rings = anomalies.map(function(s) {
                          return { lat: s.lat, lng: s.lon, altitude: s.alt };
           });

           // Store globally for selection refresh
           currentData = points;

           myGlobe.pointsData(points);
                  myGlobe.ringsData(rings);

           // Build and update paths (vector lines)
           var paths = buildPathsData(points);
                  myGlobe.pathsData(paths);

           // Build anomalies panel from points (already mapped)
           var anomalyPoints = points.filter(function(p) {
                          return p.is_anomaly;
           });
                  buildAnomaliesPanel(anomalyPoints);

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
