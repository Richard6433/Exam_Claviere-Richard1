// Burkina Faso — conflict pressure on school-age population.
// Three layers:
//   - 17 region polygons coloured by events per 100,000 children (choropleth)
//   - small blue dots for OSM schools
//   - amber triangles for recent IDMC displacement events
// Header strip shows total events / displaced / school-age children.

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
    if (n >= 10000) return (n / 1000).toFixed(0) + "k";
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

// YlOrRd 5-class sequential ramp keyed to events per 100,000 children.
// No grey fallback — every region gets a meaningful colour from the scale.
function colorForRate(rate) {
    if (rate >= 100) return "#b10026";
    if (rate >= 50) return "#fc4e2a";
    if (rate >= 30) return "#fd8d3c";
    if (rate >= 10) return "#feb24c";
    return "#fed976";
}

function displacementIcon(figure, maxFigure) {
    const minH = 14, maxH = 36;
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
    const dateRange =
        e.start_date && e.end_date && e.start_date !== e.end_date
            ? `${fmtFullDate(e.start_date)} – ${fmtFullDate(e.end_date)}`
            : fmtFullDate(e.date);
    return `
        <div class="popup popup-disp">
            <div class="disp-date">${dateRange}</div>
            <h3>${fmt(e.figure)} displaced</h3>
            <div class="disp-loc">${e.location}</div>
        </div>`;
}

function popupHtml(r) {
    const pop = r.school_age_pop;
    const schools = r.schools_osm;
    const displaced = r.displaced_recent || 0;
    const rate = pop ? (r.events / pop) * 100000 : null;
    const schoolsLine = schools
        ? ` · <strong>${fmt(schools)}</strong> schools mapped (OSM)`
        : "";
    const childrenRow = pop
        ? `<div class="children-row">
               <strong>${fmt(pop)}</strong> school-age children (5-14)
               · <strong>${rate.toFixed(1)}</strong> events per 100,000 children
               ${schoolsLine}
           </div>`
        : "";
    const displacedRow = displaced
        ? `<div class="displaced-row">
               <strong>${fmt(displaced)}</strong> people newly displaced
           </div>`
        : "";

    return `
        <div class="popup popup-region">
            <h3>${r.region}</h3>
            <div class="hero-stat">
                <span class="num">${fmt(r.events)}</span>
                <span class="label">conflict events</span>
            </div>
            ${childrenRow}
            ${displacedRow}
        </div>`;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function renderHeaderStats(events, displacement) {
    const totalEvents = events.regions.reduce((s, r) => s + r.events, 0);
    const totalChildren = events.regions.reduce(
        (s, r) => s + (r.school_age_pop || 0), 0,
    );
    setText("stat-events", fmt(totalEvents));
    setText("stat-displaced", fmt(displacement.total_displaced));
    setText("stat-children", fmtCompact(totalChildren));
    setText(
        "header-period",
        `${fmtDate(events.period_start)} → ${fmtDate(events.period_end)}`,
    );
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
                        color: "#ffffff",
                        weight: 1.5,
                        fillColor: colorForRate(rate),
                        fillOpacity: 0.7,
                        opacity: 1,
                    };
                },
                onEachFeature: (feature, layer) => {
                    const r = byPcode[feature.properties.pcode];
                    layer.bindTooltip(feature.properties.name, {
                        permanent: true,
                        direction: "center",
                        className: "region-label",
                    });
                    if (r) layer.bindPopup(popupHtml(r), { maxWidth: 320 });
                    layer.on({
                        mouseover: (e) =>
                            e.target.setStyle({
                                weight: 2.5,
                                color: "#0f172a",
                                fillOpacity: 0.85,
                            }),
                        mouseout: (e) =>
                            e.target.setStyle({
                                weight: 1.5,
                                color: "#ffffff",
                                fillOpacity: 0.7,
                            }),
                    });
                },
            }).addTo(map);
        });

        safe("schools", () => {
            schools.forEach(([lat, lon]) => {
                L.circleMarker([lat, lon], {
                    renderer: schoolsCanvas,
                    radius: 2.4,
                    stroke: false,
                    fillColor: "#0c4a6e",
                    fillOpacity: 0.8,
                }).addTo(map);
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
