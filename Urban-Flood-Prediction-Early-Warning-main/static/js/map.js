/**
 * Urban Flood Prediction and Early Warning System
 * Leaflet.js & OpenStreetMap Integration - Karnataka Geographic Bounds Locked
 */

const KARNATAKA_CENTER = [13.6, 75.8];
const KARNATAKA_BOUNDS = L.latLngBounds([11.4, 73.8], [15.8, 78.4]);

const RISK_COLOR_MAP = {
    "Low Risk": {
        primary: "#10b981",
        secondary: "rgba(16, 185, 129, 0.25)",
        badgeClass: "badge-low"
    },
    "Medium Risk": {
        primary: "#f59e0b",
        secondary: "rgba(245, 158, 11, 0.25)",
        badgeClass: "badge-med"
    },
    "High Risk": {
        primary: "#f72585",
        secondary: "rgba(247, 37, 133, 0.35)",
        badgeClass: "badge-high"
    }
};

/**
 * Creates a custom SVG / DivIcon marker in Leaflet matching the risk color.
 */
function createRiskMarkerIcon(riskLevel) {
    const config = RISK_COLOR_MAP[riskLevel] || RISK_COLOR_MAP["Low Risk"];
    const color = config.primary;

    const html = `
        <div style="
            position: relative;
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
        ">
            <div style="
                position: absolute;
                width: 100%;
                height: 100%;
                border-radius: 50%;
                background-color: ${color};
                opacity: 0.45;
                animation: pulse 1.6s infinite ease-out;
            "></div>
            <div style="
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background-color: ${color};
                border: 3px solid #ffffff;
                box-shadow: 0 3px 10px rgba(0,0,0,0.5);
            "></div>
        </div>
    `;

    return L.divIcon({
        className: "custom-risk-pin",
        html: html,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -18]
    });
}

/**
 * Renders the single interactive Leaflet map on result.html centered on the Karnataka place.
 * @param {Array} hotspots - Optional flood hotspot objects [{name,lat,lon,note}]
 */
function renderSingleLocationMap(lat, lon, locationName, riskLevel, rainfall, probability, basinDesc = "", hotspots = []) {
    const mapContainer = document.getElementById("map");
    if (!mapContainer) return;

    const theme = RISK_COLOR_MAP[riskLevel] || RISK_COLOR_MAP["Low Risk"];

    // Initialize Leaflet map centered directly on the exact Karnataka location
    const map = L.map("map", {
        zoomControl: true,
        scrollWheelZoom: false,
        minZoom: 7,
        maxBounds: KARNATAKA_BOUNDS.pad(0.2)
    }).setView([lat, lon], 14);   // Zoom 14 = street-level accuracy

    // OpenStreetMap Free Tile Layer
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        minZoom: 6,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Hazard radius circle (High: 3200m, Med: 2000m, Low: 1200m)
    const radiusMeters = riskLevel === "High Risk" ? 3200 : (riskLevel === "Medium Risk" ? 2000 : 1200);

    L.circle([lat, lon], {
        color: theme.primary,
        fillColor: theme.secondary,
        fillOpacity: 0.45,
        weight: 2,
        radius: radiusMeters
    }).addTo(map);

    // Custom colored pin marker
    const marker = L.marker([lat, lon], {
        icon: createRiskMarkerIcon(riskLevel)
    }).addTo(map);

    // Popup content with basin details
    const popupContent = `
        <div style="font-family: 'Poppins', sans-serif; min-width: 210px; padding: 6px;">
            <div style="font-size: 14px; font-weight: 700; color: #1e293b; margin-bottom: 4px;">
                ${locationName}
            </div>
            ${basinDesc ? `<div style="font-size: 11px; color: #3b82f6; font-weight: 600; margin-bottom: 6px;">🌊 ${basinDesc}</div>` : ''}
            <div style="margin-bottom: 6px;">
                <span style="
                    display: inline-block;
                    padding: 3px 10px;
                    border-radius: 999px;
                    font-size: 11px;
                    font-weight: 700;
                    background-color: ${theme.primary};
                    color: #ffffff;
                ">${riskLevel}</span>
                <span style="font-size: 12px; color: #64748b; margin-left: 6px; font-weight: 600;">${probability}%</span>
            </div>
            <div style="font-size: 12px; color: #475569;">
                Precipitation: <strong>${rainfall} mm</strong>
            </div>
        </div>
    `;

    marker.bindPopup(popupContent).openPopup();

    // ── Flood Hotspot Markers (e.g. Bharat Cancer Hospital drainage area) ─────
    if (hotspots && hotspots.length > 0) {
        const drainageIcon = L.divIcon({
            className: "drainage-warning-pin",
            html: `<div style="
                width: 28px; height: 28px;
                border-radius: 50%;
                background: #f97316;
                border: 3px solid #ffffff;
                display: flex; align-items: center; justify-content: center;
                font-size: 13px;
                box-shadow: 0 2px 8px rgba(249,115,22,0.65);
                cursor: pointer;
            ">\u26A0\uFE0F</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            popupAnchor: [0, -16]
        });

        hotspots.forEach(hs => {
            const hMarker = L.marker([hs.lat, hs.lon], { icon: drainageIcon }).addTo(map);
            hMarker.bindPopup(`
                <div style="font-family:'Poppins',sans-serif;min-width:200px;padding:6px;">
                    <div style="font-size:13px;font-weight:700;color:#c2410c;margin-bottom:4px;">
                        \u26A0\uFE0F Flood Hotspot
                    </div>
                    <div style="font-size:12px;font-weight:600;color:#1e293b;margin-bottom:4px;">
                        ${hs.name}
                    </div>
                    <div style="font-size:11px;color:#64748b;line-height:1.5;">
                        ${hs.note}
                    </div>
                    <div style="margin-top:6px;font-size:10px;color:#94a3b8;">
                        ${hs.lat.toFixed(4)}\u00B0N, ${hs.lon.toFixed(4)}\u00B0E
                    </div>
                </div>
            `);

            L.circle([hs.lat, hs.lon], {
                color: "#f97316",
                fillColor: "rgba(249,115,22,0.18)",
                fillOpacity: 0.5,
                weight: 1.5,
                radius: 500,
                dashArray: "6,4"
            }).addTo(map);
        });

        // Legend
        const legend = L.control({ position: "bottomleft" });
        legend.onAdd = function () {
            const div = L.DomUtil.create("div");
            div.style.cssText = "background:rgba(255,255,255,0.96);padding:8px 12px;border-radius:8px;font-family:'Poppins',sans-serif;font-size:11px;box-shadow:0 2px 8px rgba(0,0,0,0.18);";
            div.innerHTML = `
                <div style="font-weight:700;color:#1e293b;margin-bottom:5px;">Map Legend</div>
                <div style="display:flex;align-items:center;gap:7px;margin-bottom:4px;">
                    <div style="width:12px;height:12px;border-radius:50%;background:${theme.primary};border:2px solid #fff;flex-shrink:0;"></div>
                    <span style="color:#475569;">${locationName}</span>
                </div>
                <div style="display:flex;align-items:center;gap:7px;">
                    <div style="width:12px;height:12px;border-radius:50%;background:#f97316;border:2px solid #fff;flex-shrink:0;"></div>
                    <span style="color:#c2410c;font-weight:600;">Flood Hotspot / Drainage Risk</span>
                </div>
            `;
            return div;
        };
        legend.addTo(map);
    }
}

/**
 * Renders multiple risk points on Admin Dashboard locked strictly to Karnataka state.
 */
function renderAdminOverviewMap(points) {
    const mapContainer = document.getElementById("admin-map");
    if (!mapContainer) return;

    // Center map directly on Karnataka state (not the entire world)
    const map = L.map("admin-map", {
        zoomControl: true,
        scrollWheelZoom: false,
        minZoom: 7,
        maxZoom: 14,
        maxBounds: KARNATAKA_BOUNDS.pad(0.1)
    }).setView(KARNATAKA_CENTER, 7);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        minZoom: 6,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    // Lock and fit strictly to Karnataka
    map.fitBounds(KARNATAKA_BOUNDS, { padding: [15, 15] });

    if (!points || points.length === 0) return;

    // Filter points so ONLY valid Karnataka coordinates are plotted
    points.forEach(pt => {
        if (!pt.latitude || !pt.longitude) return;
        const lat = parseFloat(pt.latitude);
        const lon = parseFloat(pt.longitude);

        // Karnataka state bounding check
        if (lat < 11.2 || lat > 16.0 || lon < 73.8 || lon > 78.6) {
            return; // Ignore any foreign / out-of-bounds coordinates
        }

        const theme = RISK_COLOR_MAP[pt.risk_level] || RISK_COLOR_MAP["Low Risk"];

        const marker = L.marker([lat, lon], {
            icon: createRiskMarkerIcon(pt.risk_level)
        }).addTo(map);

        L.circle([lat, lon], {
            color: theme.primary,
            fillColor: theme.secondary,
            fillOpacity: 0.35,
            weight: 1.5,
            radius: pt.risk_level === "High Risk" ? 2800 : (pt.risk_level === "Medium Risk" ? 1800 : 1000)
        }).addTo(map);

        marker.bindPopup(`
            <div style="font-family: 'Poppins', sans-serif; padding: 4px;">
                <strong style="color: #1e293b; font-size: 13px;">${pt.location_name}</strong><br/>
                <span style="color: ${theme.primary}; font-weight: 700; font-size: 12px;">● ${pt.risk_level}</span> (${pt.probability}%)<br/>
                Rainfall: <strong>${pt.rainfall} mm</strong><br/>
                <small style="color: #64748b;">${pt.created_at || ''}</small>
            </div>
        `);
    });
}
