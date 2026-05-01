// Burkina Faso conflict-activity map.
// Loads two small JSON files prepared by scripts/02_prepare_map_data.py
// and renders region polygons (17 new regions) plus circle markers per
// region centroid sized by total events in the last 12 months.

const BF_CENTER = [12.4, -1.5];
const BF_ZOOM = 7;

const map = L.map("map", { zoomControl: true }).setView(BF_CENTER, BF_ZOOM);

// A canvas renderer keeps the 5,000+ school dots fast.
const schoolsCanvas = L.canvas({ padding: 0.3 });

L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
        'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 18,
}).addTo(map);

function fmt(n) {
    return n.toLocaleString("en-US");
}

function fmtDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
        day: "numeric", month: "short", year: "numeric",
    });
}

// Square-root scaling so a region with 4x events has 2x radius — visually fair.
function radiusFor(events, maxEvents) {
    const minR = 6, maxR = 36;
    return minR + (maxR - minR) * Math.sqrt(events / maxEvents);
}

function fmtFullDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
        day: "numeric", month: "long", year: "numeric",
    });
}

// Triangle marker for displacement events. Size scales with `figure`
// (number of people displaced) using a square-root mapping for fairness.
function displacementIcon(figure, maxFigure) {
    const minH = 12, maxH = 26;
    const h = minH + (maxH - minH) * Math.sqrt(figure / maxFigure);
    const w = h * 1.1;
    const halfW = w / 2;
    return L.divIcon({
        className: "displacement-icon-wrap",
        html: `<div class="displacement-tri"
                    style="border-left-width:${halfW}px;
                           border-right-width:${halfW}px;
                           border-bottom-width:${h}px"></div>`,
        iconSize: [w, h],
        iconAnchor: [halfW, h],
    });
}

function displacementPopupHtml(e) {
    return `
        <div class="popup popup-disp">
            <div class="disp-date">${fmtFullDate(e.date)}</div>
            <h3>${fmt(e.figure)} displaced</h3>
            <div class="disp-loc">${e.location}</div>
            <div class="disp-tag">${e.type}</div>
            <p class="disp-desc">${e.description}…</p>
        </div>`;
}

function popupHtml(r) {
    const pop = r.school_age_pop;
    const schools = r.schools_osm;
    const rate = pop ? (r.events / pop) * 100_000 : null;
    const schoolsLine = schools
        ? ` · <strong>${fmt(schools)}</strong> schools mapped (OSM)`
        : "";
    const popRow = pop
        ? `<div class="children-row">
               <strong>${fmt(pop)}</strong> school-age children (5-14)
               · <strong>${rate.toFixed(1)}</strong> events per 100,000 children
               ${schoolsLine}
           </div>`
        : "";

    return `
        <div class="popup">
            <h3>${r.region}</h3>
            <div class="period">${fmtDate(r.period_start)} — ${fmtDate(r.period_end)}</div>
            <div class="stats">
                <div class="stat">
                    <div class="num">${fmt(r.events)}</div>
                    <div class="label">events</div>
                </div>
                <div class="stat">
                    <div class="num">${fmt(r.fatalities)}</div>
                    <div class="label">fatalities</div>
                </div>
            </div>
            ${popRow}
        </div>`;
}

Promise.all([
    fetch("data/regions.geojson").then((r) => r.json()),
    fetch("data/events_by_region.json").then((r) => r.json()),
    fetch("data/schools.json").then((r) => r.json()),
    fetch("data/displacement.json").then((r) => r.json()),
]).then(([regions, events, schools, displacement]) => {
    const totalChildren = events.regions.reduce(
        (sum, r) => sum + (r.school_age_pop || 0), 0,
    );
    document.getElementById("period-line").textContent =
        `${fmtDate(events.period_start)} → ${fmtDate(events.period_end)} · ` +
        `${fmt(totalChildren)} school-age children (5-14) · ` +
        `${fmt(displacement.total_displaced)} newly displaced ` +
        `(${displacement.events.length} reported events, ` +
        `${fmtDate(displacement.period_start)} → ${fmtDate(displacement.period_end)})`;

    L.geoJSON(regions, {
        style: {
            color: "#475569",
            weight: 1.1,
            fillColor: "#f1f5f9",
            fillOpacity: 0.55,
            opacity: 0.85,
        },
        onEachFeature: (feature, layer) => {
            layer.bindTooltip(feature.properties.name, {
                sticky: true,
                className: "region-label",
            });
            layer.on({
                mouseover: (e) => e.target.setStyle({ weight: 2, color: "#1e293b" }),
                mouseout: (e) => e.target.setStyle({ weight: 1.1, color: "#475569" }),
            });
        },
    }).addTo(map);

    // Schools layer — small subtle blue dots, drawn on canvas under the
    // conflict markers so the red circles remain the visual headline.
    schools.forEach(([lat, lon]) => {
        L.circleMarker([lat, lon], {
            renderer: schoolsCanvas,
            radius: 2,
            stroke: false,
            fillColor: "#1d4ed8",
            fillOpacity: 0.45,
        }).addTo(map);
    });

    const maxEvents = Math.max(...events.regions.map((r) => r.events));

    events.regions.forEach((r) => {
        if (!r.events) return;
        L.circleMarker([r.lat, r.lon], {
            radius: radiusFor(r.events, maxEvents),
            color: "#7f1d1d",
            weight: 1,
            fillColor: "#dc2626",
            fillOpacity: 0.7,
        })
            .bindPopup(popupHtml(r), { maxWidth: 320 })
            .addTo(map);
    });

    // Displacement events — sit on top of the conflict circles, smaller
    // amber triangles tied to specific lat/lon and dates.
    const maxFigure = Math.max(...displacement.events.map((e) => e.figure));
    displacement.events.forEach((e) => {
        L.marker([e.lat, e.lon], {
            icon: displacementIcon(e.figure, maxFigure),
        })
            .bindPopup(displacementPopupHtml(e), { maxWidth: 320 })
            .addTo(map);
    });
});
