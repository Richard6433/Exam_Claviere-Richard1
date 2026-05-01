// Burkina Faso — conflict pressure on school-age population.
// Loads four small JSON files prepared by scripts/02_prepare_map_data.py
// and renders:
//   - 17 region polygons coloured by events per 100,000 children (choropleth)
//   - red circle markers per region sized by absolute event count
//   - small blue dots for OSM schools
//   - amber triangles for recent IDMC displacement events
// Plus a "highest pressure" panel listing the top 3 regions and a
// header strip showing total events / displaced / school-age children.

const BF_CENTER = [12.4, -1.5];
const BF_ZOOM = 7;

const map = L.map("map", { zoomControl: true }).setView(BF_CENTER, BF_ZOOM);
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

function fmtCompact(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(2).replace(/\.?0+$/, "") + "M";
    if (n >= 10_000) return (n / 1000).toFixed(0) + "k";
    return fmt(n);
}

function fmtDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
        day: "numeric", month: "short", year: "numeric",
    });
}

function fmtFullDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
        day: "numeric", month: "long", year: "numeric",
    });
}

function radiusFor(events, maxEvents) {
    const minR = 6, maxR = 32;
    return minR + (maxR - minR) * Math.sqrt(events / maxEvents);
}

// Sequential red ramp keyed to events per 100,000 school-age children.
function colorForRate(rate) {
    if (rate >= 100) return "#7f1d1d";
    if (rate >= 50) return "#dc2626";
    if (rate >= 30) return "#f87171";
    if (rate >= 10) return "#fecaca";
    if (rate > 0) return "#fef2f2";
    return "#f3f4f6";
}

function displacementIcon(figure, maxFigure) {
    const minH = 11, maxH = 24;
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
    const rate = pop ? (r.events / pop) * 100000 : null;
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
            <div class="hero-stat">
                <span class="num">${fmt(r.events)}</span>
                <span class="label">conflict events (last 12 months)</span>
            </div>
            ${popRow}
        </div>`;
}

function renderHotspots(events) {
    const ranked = events.regions
        .filter((r) => r.school_age_pop)
        .map((r) => ({
            ...r,
            rate: (r.events / r.school_age_pop) * 100000,
        }))
        .sort((a, b) => b.rate - a.rate)
        .slice(0, 3);

    const html = ranked
        .map(
            (r, i) => `
            <div class="hotspot-row">
                <span class="rank">${i + 1}</span>
                <span class="name">${r.region}</span>
                <span class="rate">${r.rate.toFixed(1)}</span>
            </div>`,
        )
        .join("");
    document.getElementById("hotspots-body").innerHTML = html;
}

function renderHeaderStats(events, displacement) {
    const totalEvents = events.regions.reduce((s, r) => s + r.events, 0);
    const totalChildren = events.regions.reduce(
        (s, r) => s + (r.school_age_pop || 0), 0,
    );
    document.getElementById("stat-events").textContent = fmt(totalEvents);
    document.getElementById("stat-displaced").textContent = fmt(displacement.total_displaced);
    document.getElementById("stat-children").textContent = fmtCompact(totalChildren);
    document.getElementById("header-period").textContent =
        `${fmtDate(events.period_start)} → ${fmtDate(events.period_end)} · 12-month window`;
}

function safe(label, fn) {
    try { fn(); } catch (e) { console.error(`[map] ${label} failed:`, e); }
}

Promise.all([
    fetch("data/regions.geojson").then((r) => r.json()),
    fetch("data/events_by_region.json").then((r) => r.json()),
    fetch("data/schools.json").then((r) => r.json()),
    fetch("data/displacement.json").then((r) => r.json()),
])
    .then(([regions, events, schools, displacement]) => {
        console.log("[map] data loaded:",
            regions.features.length, "regions /",
            events.regions.length, "events records /",
            schools.length, "schools /",
            displacement.events.length, "displacement events");

        safe("header", () => renderHeaderStats(events, displacement));
        safe("hotspots", () => renderHotspots(events));

        const byPcode = Object.fromEntries(
            events.regions.map((r) => [r.pcode, r]),
        );

        safe("regions", () => {
            L.geoJSON(regions, {
                style: (feature) => {
                    const r = byPcode[feature.properties.pcode];
                    const rate =
                        r && r.school_age_pop
                            ? (r.events / r.school_age_pop) * 100000
                            : 0;
                    return {
                        color: "#64748b",
                        weight: 0.8,
                        fillColor: colorForRate(rate),
                        fillOpacity: 0.78,
                        opacity: 0.9,
                    };
                },
                onEachFeature: (feature, layer) => {
                    const r = byPcode[feature.properties.pcode];
                    layer.bindTooltip(feature.properties.name, {
                        sticky: true,
                        className: "region-label",
                    });
                    if (r) layer.bindPopup(popupHtml(r), { maxWidth: 320 });
                    layer.on({
                        mouseover: (e) =>
                            e.target.setStyle({ weight: 1.8, color: "#0f172a" }),
                        mouseout: (e) =>
                            e.target.setStyle({ weight: 0.8, color: "#64748b" }),
                    });
                },
            }).addTo(map);
        });

        safe("schools", () => {
            schools.forEach(([lat, lon]) => {
                L.circleMarker([lat, lon], {
                    renderer: schoolsCanvas,
                    radius: 2,
                    stroke: false,
                    fillColor: "#1d4ed8",
                    fillOpacity: 0.55,
                }).addTo(map);
            });
        });

        safe("conflict markers", () => {
            const maxEvents = Math.max(
                ...events.regions.map((r) => r.events),
            );
            events.regions.forEach((r) => {
                if (!r.events) return;
                L.circleMarker([r.lat, r.lon], {
                    radius: radiusFor(r.events, maxEvents),
                    color: "#450a0a",
                    weight: 1.5,
                    fillColor: "#dc2626",
                    fillOpacity: 0.85,
                })
                    .bindPopup(popupHtml(r), { maxWidth: 320 })
                    .addTo(map);
            });
        });

        safe("displacement", () => {
            const maxFigure = Math.max(
                ...displacement.events.map((e) => e.figure),
            );
            displacement.events.forEach((e) => {
                L.marker([e.lat, e.lon], {
                    icon: displacementIcon(e.figure, maxFigure),
                })
                    .bindPopup(displacementPopupHtml(e), { maxWidth: 320 })
                    .addTo(map);
            });
        });
    })
    .catch((e) => {
        console.error("[map] failed to load data:", e);
    });
