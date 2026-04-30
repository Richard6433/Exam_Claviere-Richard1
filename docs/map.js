// Burkina Faso conflict-activity map.
// Loads two small JSON files prepared by scripts/02_prepare_map_data.py
// and renders region polygons (17 new regions) plus circle markers per
// region centroid sized by total events in the last 12 months.

const BF_CENTER = [12.4, -1.5];
const BF_ZOOM = 7;

const map = L.map("map", { zoomControl: true }).setView(BF_CENTER, BF_ZOOM);

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

function popupHtml(r, maxBreakdown) {
    const rows = Object.entries(r.breakdown)
        .map(([name, count]) => {
            const pct = (count / maxBreakdown) * 100;
            return `
                <div class="bar-row">
                    <span class="name" title="${name}">${name}</span>
                    <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
                    <span class="count">${fmt(count)}</span>
                </div>`;
        })
        .join("");

    const pop = r.school_age_pop;
    const rate = pop ? (r.events / pop) * 100_000 : null;
    const popRow = pop
        ? `<div class="children-row">
               <strong>${fmt(pop)}</strong> school-age children (5-14) in this region
               · <strong>${rate.toFixed(1)}</strong> events per 100,000 children
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
            <div class="breakdown-title">By cause</div>
            ${rows}
        </div>`;
}

Promise.all([
    fetch("data/regions.geojson").then((r) => r.json()),
    fetch("data/events_by_region.json").then((r) => r.json()),
]).then(([regions, events]) => {
    const totalChildren = events.regions.reduce(
        (sum, r) => sum + (r.school_age_pop || 0), 0,
    );
    document.getElementById("period-line").textContent =
        `${fmtDate(events.period_start)} → ${fmtDate(events.period_end)} · ` +
        `${fmt(totalChildren)} school-age children (5-14) live across these regions · ` +
        `click a region for the breakdown`;

    L.geoJSON(regions, {
        style: {
            color: "#9ca3af",
            weight: 1,
            fillColor: "#e5e7eb",
            fillOpacity: 0.35,
        },
        onEachFeature: (feature, layer) => {
            layer.bindTooltip(feature.properties.name, {
                sticky: true,
                className: "region-label",
            });
        },
    }).addTo(map);

    const maxEvents = Math.max(...events.regions.map((r) => r.events));

    events.regions.forEach((r) => {
        const maxBreakdown = Math.max(...Object.values(r.breakdown));
        L.circleMarker([r.lat, r.lon], {
            radius: radiusFor(r.events, maxEvents),
            color: "#7f1d1d",
            weight: 1,
            fillColor: "#dc2626",
            fillOpacity: 0.7,
        })
            .bindPopup(popupHtml(r, maxBreakdown), { maxWidth: 320 })
            .addTo(map);
    });
});
