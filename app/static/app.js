/* ================================================================
   AI-Orbit Intelligence 3D — Globe.gl Application
   ================================================================ */

// Constants
const API_URL        = "http://localhost:8000/api/positions";
const EARTH_RADIUS   = 6371;          // km
const REFRESH_MS     = 3000;          // fetch interval (3 s)
const COLOR_NORMAL   = "#0442BF";     // Brilliant Blue
const COLOR_ANOMALY  = "#F2C641";     // Golden Yellow
const COLOR_RING     = "rgba(242, 198, 65, 0.35)";

// DOM refs
const elSatCount     = document.getElementById("sat-count");
const elAnomalyCount = document.getElementById("anomaly-count");
const elStatus       = document.getElementById("status-text");

// Globe initialisation
const myGlobe = Globe()(document.getElementById("globeViz"))
    .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
    .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
    .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
    .showAtmosphere(true)
    .atmosphereColor("#0442BF")
    .atmosphereAltitude(0.25)

    // Points layer (satellites)
    .pointsData([])
    .pointLat("lat")
    .pointLng("lng")
    .pointAltitude("altitude")
    .pointColor("color")
    .pointRadius(0.35)
    .pointLabel("label")

    // Rings layer (anomaly pulse)
    .ringsData([])
    .ringLat("lat")
    .ringLng("lng")
    .ringAltitude("altitude")
    .ringColor(function () { return COLOR_RING; })
    .ringMaxRadius(3)
    .ringPropagationSpeed(2)
    .ringRepeatPeriod(1200);

// Slow auto-rotation
myGlobe.controls().autoRotate = true;
myGlobe.controls().autoRotateSpeed = 0.4;

// Data fetching
async function fetchData() {
      try {
                var res = await fetch(API_URL);
                if (!res.ok) throw new Error("HTTP " + res.status);
                var data = await res.json();

          // Counters
          var total     = data.total_satellites;
                var anomalies = data.satellites.filter(function (s) { return s.is_anomaly; }).length;

          elSatCount.textContent     = total;
                elAnomalyCount.textContent = anomalies;
                elStatus.textContent       = "Live — " + new Date().toLocaleTimeString();

          // Format for Globe.gl
          var points = data.satellites.map(function (s) {
                        return {
                                          lat:      s.lat,
                                          lng:      s.lon,                           // API returns "lon"
                                          altitude: s.alt / EARTH_RADIUS,            // km to ratio
                                          color:    s.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL,
                                          label:    "<b style=\"color:" + (s.is_anomaly ? COLOR_ANOMALY : COLOR_NORMAL) + "\">"
                                                  + s.name + "</b><br>"
                                                  + "Score: " + s.anomaly_score.toFixed(2) + "<br>"
                                                  + "Alt: " + s.alt.toFixed(0) + " km"
                        };
          });

          // Rings only on anomalies
          var rings = data.satellites
                    .filter(function (s) { return s.is_anomaly; })
                    .map(function (s) {
                                      return {
                                                            lat:      s.lat,
                                                            lng:      s.lon,
                                                            altitude: s.alt / EARTH_RADIUS
                                      };
                    });

          myGlobe.pointsData(points);
                myGlobe.ringsData(rings);

      } catch (err) {
                console.error("[orbit-intel] fetch error:", err);
                elStatus.textContent = "Connection lost — retrying...";
      }
}

// Bootstrap
fetchData();
setInterval(fetchData, REFRESH_MS);
