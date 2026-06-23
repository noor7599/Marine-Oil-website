import { useEffect, useRef, useState, useCallback } from "react";
import {
  Navigation, Play, Pause, Clock,
  Maximize2, Minimize2, Zap, RotateCcw,
  Target, Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// ─── Leaflet icon fix ─────────────────────────────────────────────────────────
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl:       "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl:     "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

// ─── Types ───────────────────────────────────────────────────────────────────
type Particle = { lat: number; lon: number; mass_oil: number };
type TimeStep = { time: string; particles: Particle[] };

type TrajectoryMapProps = {
  runId?:  string | null;
  csvUrl?: string | null;
  spillOrigin?: { lat: number; lon: number } | null;
  spillCountry?: string | null;
};

// ─── CSV parser with NATURAL PARTICLE DIFFUSION logic ─────────────────────
async function parseCsvToTimeSteps(url: string): Promise<TimeStep[]> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`CSV fetch failed: ${res.status} ${res.statusText}`);

  const lines = (await res.text())
    .split("\n")
    .filter((l) => l.trim() && !l.startsWith("#"));

  if (lines.length < 2) throw new Error("CSV has no data rows.");

  const header = lines[0].split(",").map((h) => h.trim());
  const need   = (n: string) => {
    const i = header.indexOf(n);
    if (i < 0) throw new Error(`CSV missing column: "${n}"`);
    return i;
  };
  const iTime    = need("time");
  const iLon     = need("lon");
  const iLat     = need("lat");
  const iMassOil = header.indexOf("mass_oil");

  type Row = { time: string; lon: number; lat: number; mass_oil: number };
  const rows: Row[] = [];

  for (let r = 1; r < lines.length; r++) {
    const c = lines[r].split(",");
    const time = c[iTime]?.trim() ?? "";
    const lon = parseFloat(c[iLon]);
    const lat = parseFloat(c[iLat]);
    const mass_oil = iMassOil >= 0 ? parseFloat(c[iMassOil]) || 1 : 1;
    if (!time || isNaN(lon) || isNaN(lat)) continue;
    rows.push({ time, lon, lat, mass_oil });
  }

  const byTime = new Map<string, Row[]>();
  for (const row of rows) {
    if (!byTime.has(row.time)) byTime.set(row.time, []);
    byTime.get(row.time)!.push(row);
  }

  const sortedTimes = Array.from(byTime.keys()).sort(
    (a, b) => new Date(a).getTime() - new Date(b).getTime()
  );

  let referenceParticles: Row[] = [];
  for (const t of sortedTimes) {
    const pts = byTime.get(t)!;
    if (pts.length > referenceParticles.length) {
      referenceParticles = pts;
    }
  }

  const referenceCenter = {
    lon: referenceParticles.reduce((s, p) => s + p.lon, 0) / referenceParticles.length,
    lat: referenceParticles.reduce((s, p) => s + p.lat, 0) / referenceParticles.length,
  };

  const particleProfiles = referenceParticles.map((p, idx) => {
    const dLon = p.lon - referenceCenter.lon;
    const dLat = p.lat - referenceCenter.lat;
    const angle = Math.atan2(dLat, dLon);
    const distance = Math.sqrt(dLon * dLon + dLat * dLat);

    return {
      id: idx,
      angle,
      distance,
      mass_oil: p.mass_oil,
      radialFactor: 0.7 + Math.random() * 0.7,
      turbulenceFactor: (Math.random() - 0.5) * 0.5,
      lagFactor: 0.8 + Math.random() * 0.4,
    };
  });

  const totalFrames = sortedTimes.length;

  return sortedTimes.map((time, stepIndex) => {
    const currentRows = byTime.get(time)!;

    const center = {
      lon: currentRows.reduce((s, p) => s + p.lon, 0) / currentRows.length,
      lat: currentRows.reduce((s, p) => s + p.lat, 0) / currentRows.length,
    };

    const rawProgress = totalFrames > 1 ? stepIndex / (totalFrames - 1) : 1;
    const spreadProgress = Math.pow(rawProgress, 0.65);

    const particles: Particle[] = particleProfiles.map((profile) => {
      const radial = profile.distance * spreadProgress * profile.radialFactor * profile.lagFactor;
      const turbulence = profile.distance * spreadProgress * profile.turbulenceFactor;

      const lon = center.lon + Math.cos(profile.angle) * radial - Math.sin(profile.angle) * turbulence;
      const lat = center.lat + Math.sin(profile.angle) * radial + Math.cos(profile.angle) * turbulence;

      return { lon, lat, mass_oil: profile.mass_oil };
    });

    return { time, particles };
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getMeanCenter(particles: Particle[]): { lat: number; lon: number } {
  return {
    lat: particles.reduce((s, p) => s + p.lat, 0) / particles.length,
    lon: particles.reduce((s, p) => s + p.lon, 0) / particles.length,
  };
}

// Haversine formula to calculate distance between two lat/lon points (in km)
function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

// Simple reverse geocoding for Arabian Gulf/Philippines region
function getCountryFromCoords(lat: number, lon: number): string {
  const regions: Array<{ name: string; bounds: [number, number, number, number] }> = [
    // Philippines
    { name: "Philippines", bounds: [4.0, 21.0, 116.0, 127.0] },
    // Arabian Gulf region
    { name: "Kuwait", bounds: [28.5, 30.1, 46.5, 48.5] },
    { name: "Saudi Arabia", bounds: [16.0, 32.0, 34.0, 56.0] },
    { name: "Iran", bounds: [25.0, 40.0, 44.0, 63.5] },
    { name: "Iraq", bounds: [29.0, 37.5, 38.5, 48.8] },
    { name: "UAE", bounds: [22.5, 26.5, 51.5, 56.5] },
    { name: "Qatar", bounds: [24.5, 26.2, 50.5, 51.8] },
    { name: "Bahrain", bounds: [25.8, 26.4, 50.3, 50.8] },
    { name: "Oman", bounds: [16.5, 26.5, 52.0, 60.0] },
  ];
  
  for (const { name, bounds } of regions) {
    const [minLat, maxLat, minLon, maxLon] = bounds;
    if (lat >= minLat && lat <= maxLat && lon >= minLon && lon <= maxLon) {
      return name;
    }
  }
  return "Int'l Waters";
}

// ─── Component ───────────────────────────────────────────────────────────────
const TrajectoryMap = ({
  runId  = null,
  csvUrl = null,
  spillOrigin = null,
  spillCountry = null,
}: TrajectoryMapProps) => {
  const mapRef           = useRef<L.Map | null>(null);
  const particleLayerRef = useRef<L.Layer | null>(null);

  const [timeStep,        setTimeStep]        = useState(0);
  const [playing,         setPlaying]         = useState(false);
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [hasData,         setHasData]         = useState(false);
  const [timeSteps,       setTimeSteps]       = useState<TimeStep[]>([]);
  const [isMaximized,     setIsMaximized]     = useState(false);
  const [animationSpeed,  setAnimationSpeed]  = useState<"0.5" | "1" | "2" | "4">("1");
  const [gifUrl,          setGifUrl]          = useState<string | null>(null);
  const [gifFramesReady,  setGifFramesReady]  = useState(false);
  
  // Location state
  const [spillCenter,     setSpillCenter]     = useState<{ lat: number; lon: number } | null>(null);
  const [mapCenter,       setMapCenter]       = useState<{ lat: number; lon: number } | null>(null);
  const [driftDistance,   setDriftDistance]   = useState<number | null>(null);

  const speedMs = { "0.5": 1200, "1": 600, "2": 300, "4": 150 }[animationSpeed];

  // ── 1. Init Leaflet map ──────────────────────────────────────────────────
  useEffect(() => {
    if (mapRef.current) return;
    setTimeout(() => {
      const el = document.getElementById("trajectory-map-container");
      if (!el) return;

      const map = L.map("trajectory-map-container", {
        attributionControl: false,
        zoomControl:        true,
        preferCanvas:       true,
      }).setView([28.6, 48.57], 10);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 19, minZoom: 0, crossOrigin: "anonymous",
        errorTileUrl: "image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
      }).addTo(map);

      map.zoomControl.setPosition("topright");
      setTimeout(() => {
        document.querySelectorAll<HTMLElement>(".leaflet-control-zoom a").forEach((b) => {
          Object.assign(b.style, {
            width: "40px", height: "40px", lineHeight: "40px",
            fontSize: "22px", color: "white", backgroundColor: "#0066cc",
            border: "none", borderRadius: "0", fontWeight: "bold",
          });
        });
        const zi = document.querySelector<HTMLElement>(".leaflet-control-zoom-in");
        const zo = document.querySelector<HTMLElement>(".leaflet-control-zoom-out");
        if (zi) { zi.style.borderTopLeftRadius    = "6px"; zi.style.borderTopRightRadius    = "6px"; }
        if (zo) { zo.style.borderBottomLeftRadius = "6px"; zo.style.borderBottomRightRadius = "6px"; }
      }, 200);

      // Track map center changes
      map.on("moveend", () => {
        const center = map.getCenter();
        setMapCenter({ lat: center.lat, lon: center.lng });
      });

      mapRef.current = map;
      setTimeout(() => map.invalidateSize(), 50);
    }, 100);
  }, []);

  // ── 2. Load GIF / check if individual frames are ready ─────────────────────
  useEffect(() => {
    if (!runId) return;
    setGifFramesReady(false);
    setGifUrl(null);

    const frame0Url = `http://localhost:5000/api/results/${runId}/gif-frames/frame_00.png`;
    fetch(frame0Url, { method: "HEAD" })
      .then((r) => {
        if (r.ok) {
          setGifUrl(frame0Url);
          setGifFramesReady(true);
        } else {
          const gifEndpoint = `http://localhost:5000/api/results/${runId}/trajectory-gif`;
          return fetch(gifEndpoint, { method: "HEAD" }).then((r2) => {
            if (r2.ok) setGifUrl(gifEndpoint);
          });
        }
      })
      .catch(() => {});
  }, [runId]);

  // ── 3. Load trajectory CSV ────────────────────────────────────────────────
  useEffect(() => {
    if (!runId && !csvUrl) {
      setError(null); setHasData(false); setTimeSteps([]); return;
    }
    setLoading(true); setError(null); setPlaying(false); setTimeStep(0);

    (async () => {
      try {
        let steps: TimeStep[];
        if (csvUrl) {
          steps = await parseCsvToTimeSteps(csvUrl);
          if (!steps.length) throw new Error("CSV contained no valid data rows.");
        } else {
          const res = await fetch(`http://localhost:5000/api/results/${runId}/trajectory-particles`);
          if (!res.ok) throw new Error("Failed to fetch particle data.");
          const json = await res.json();
          if (!json.timeSteps?.length) throw new Error("No simulation data available.");
          steps = json.timeSteps;
        }
        setTimeSteps(steps);
        setHasData(true);
        
        // Calculate spill center from first timestep
        if (steps.length > 0 && steps[0].particles.length > 0) {
          const center = getMeanCenter(steps[0].particles);
          setSpillCenter(center);
        }
      } catch (err: any) {
        setError(err.message ?? "Failed to load simulation data.");
        setHasData(false);
      } finally {
        setLoading(false);
      }
    })();
  }, [runId, csvUrl]);

  // ── 4. Calculate drift distance (NO MARKER) ───────────────────────────────
  useEffect(() => {
    if (!hasData) return;
    
    const origin = spillOrigin || spillCenter;
    const current = timeSteps[timeStep]?.particles.length > 0 
      ? getMeanCenter(timeSteps[timeStep].particles) 
      : null;

    // Calculate drift distance
    if (origin && current) {
      const distance = haversineDistance(origin.lat, origin.lon, current.lat, current.lon);
      setDriftDistance(distance);
    } else {
      setDriftDistance(null);
    }
  }, [timeStep, timeSteps, hasData, spillOrigin, spillCenter]);

  // ── 5. Render particles with L.geoJSON ────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !hasData || !timeSteps.length || timeStep >= timeSteps.length) return;
    
    const map = mapRef.current;
    const particles = timeSteps[timeStep].particles;
    
    if (particleLayerRef.current) {
      map.removeLayer(particleLayerRef.current);
    }
    
    const geo = {
      type: "FeatureCollection",
      features: particles.map((p) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [p.lon, p.lat],
        },
        properties: {
          mass_oil: p.mass_oil,
        },
      })),
    } as any;
    
    const layer = L.geoJSON(geo, {
      pointToLayer: (feature: any, latlng: L.LatLng) =>
        L.circleMarker(latlng, {
          radius: Math.max(2.5, Math.min(5, Math.sqrt(feature?.properties?.mass_oil || 1) * 1.4)),
          fillColor: "#2f2f2f",
          color: "#1f1f1f",
          weight: 0.2,
          fillOpacity: 0.12,
          opacity: 0.18,
        }),
    }).addTo(map);
    
    particleLayerRef.current = layer;
    
    const center = getMeanCenter(particles);
    map.panTo([center.lat, center.lon], {
      animate: true,
      duration: 0.5,
    });
    
  }, [timeStep, timeSteps, hasData]);

  // ── 6. Playback interval ─────────────────────────────────────────────────
  useEffect(() => {
    if (!playing || !timeSteps.length) return;
    const id = setInterval(() => {
      setTimeStep((p) => (p >= timeSteps.length - 1 ? 0 : p + 1));
    }, speedMs);
    return () => clearInterval(id);
  }, [playing, timeSteps, speedMs]);

  // ── 7. Resize on maximize ─────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current) return;
    for (let i = 0; i < 10; i++) {
      setTimeout(() => {
        mapRef.current?.invalidateSize();
        if (mapRef.current)
          mapRef.current.setView(mapRef.current.getCenter(), mapRef.current.getZoom());
      }, i * 100);
    }
  }, [isMaximized]);

  const togglePlay     = useCallback(() => setPlaying((p) => !p), []);
  const toggleMaximize = useCallback(() => setIsMaximized((m) => !m), []);

  const currentTimeLabel = hasData && timeSteps[timeStep] ? timeSteps[timeStep].time : "No data";
  const progress = timeSteps.length > 1 ? Math.round((timeStep / (timeSteps.length - 1)) * 100) : 0;
  
  // Determine country to display
  const originDisplay = spillOrigin || spillCenter;
  const displayCountry = spillCountry || (originDisplay ? getCountryFromCoords(originDisplay.lat, originDisplay.lon) : null);

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <section
      style={
        isMaximized
          ? {
              position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
              width: "100vw", height: "100vh", zIndex: 9999,
              overflow: "hidden", margin: 0, padding: 0,
              display: "flex", flexDirection: "column",
            }
          : undefined
      }
      className={!isMaximized ? "glass-card animate-slide-up overflow-hidden" : ""}
    >
      {/* ── Header ─────────────────────────────────────────────────────── */}
      {!isMaximized && (
        <div className="flex items-center justify-between p-5 border-b border-white/5 bg-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-accent/20 rounded-lg">
              <Navigation className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h2 className="text-sm font-bold uppercase tracking-widest text-white/90">
                2. Drift &amp; Spread Simulation
              </h2>
              <p className="text-[10px] text-muted-foreground">
                {timeSteps.length
                  ? `${timeSteps.length} time steps · particle diffusion`
                  : "Lagrangian dispersion model"}
              </p>
            </div>
          </div>

          {/* ✅ UPDATED: Timestamp + Country badge */}
          <div className="flex items-center gap-2 bg-black/40 border border-white/10 px-4 py-1.5 rounded-full">
            <Clock className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-mono text-white">{currentTimeLabel}</span>
            {displayCountry && (
              <>
                <span className="text-white/30">·</span>
                <span className="text-xs font-medium text-accent">{displayCountry}</span>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Map + GIF side-by-side ─────────────────────────────────────────── */}
      <div className={isMaximized ? "flex-1 flex flex-row w-full h-full" : "flex flex-row w-full"}>
        {/* ── Map Panel ───────────────────────────────────────────────────── */}
        <div
          style={isMaximized ? { flex: 1, position: "relative" } : undefined}
          className={!isMaximized ? "relative flex-1 min-w-0" : ""}
        >
          <div
            id="trajectory-map-container"
            style={isMaximized ? { width: "100%", height: "100%" } : { height: "500px" }}
          />

          {/* ── Controls (Top Left) ─────────────────────────────────────── */}
          <div className="absolute top-4 left-4 z-[1001] flex flex-col gap-2">
            {/* Maximize/Minimize Button */}
            <Button
              onClick={toggleMaximize}
              variant="ghost"
              size="icon"
              className="h-10 w-10 rounded-lg bg-white/90 hover:bg-white border border-gray-300 text-gray-700 shadow-lg"
              title={isMaximized ? "Minimize map" : "Maximize map"}
            >
              {isMaximized ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
            </Button>
          </div>

          {/* 🧭 Current Map Center (Bottom Left of map area) */}
          {mapCenter && (
            <div className="absolute bottom-24 left-6 z-[999]">
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-black/60 backdrop-blur-sm border border-white/10 rounded-md">
                <Globe className="w-3 h-3 text-white/50" />
                <span className="text-[9px] font-mono text-white/70">
                  {mapCenter.lat.toFixed(3)}°, {mapCenter.lon.toFixed(3)}°
                </span>
              </div>
            </div>
          )}

          {/* Loading / Error overlay */}
          {(loading || error) && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm z-[500]">
              <div className="text-center px-6">
                {loading && (
                  <>
                    <div className="animate-spin rounded-full h-12 w-12 border-2 border-accent/30 border-t-accent mx-auto mb-4" />
                    <p className="text-white font-medium">Loading trajectory data…</p>
                    <p className="text-white/40 text-xs mt-1">Parsing simulation CSV file</p>
                  </>
                )}
                {error && !loading && (
                  <>
                    <p className="text-yellow-400 font-medium mb-2">⚠️ Simulation Unavailable</p>
                    <p className="text-white/70 text-sm max-w-xs">{error}</p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* ── Playback controls ─────────────────────────────────────────── */}
          <div className="absolute bottom-6 left-6 right-6 z-[1000]">
            <div className="bg-black/80 backdrop-blur-md border border-white/10 p-4 rounded-2xl shadow-2xl">

              {hasData && isMaximized && (
                <div className="flex items-center gap-2 mb-3 pb-3 border-b border-white/10">
                  <Clock className="w-3.5 h-3.5 text-accent" />
                  <span className="text-xs font-mono text-white">{currentTimeLabel}</span>
                  {displayCountry && (
                    <>
                      <span className="text-white/30">·</span>
                      <span className="text-xs text-accent">{displayCountry}</span>
                    </>
                  )}
                </div>
              )}

              <div className="flex items-center gap-5">
                <Button
                  onClick={togglePlay}
                  variant="ghost"
                  size="icon"
                  className="h-12 w-12 rounded-full bg-accent/10 hover:bg-accent/20 border border-accent/30 text-accent disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!hasData}
                >
                  {playing ? <Pause className="fill-current" /> : <Play className="ml-1 fill-current" />}
                </Button>

                <Button
                  onClick={() => { setTimeStep(0); setPlaying(false); }}
                  variant="ghost"
                  size="icon"
                  className="h-12 w-12 rounded-full bg-accent/10 hover:bg-accent/20 border border-accent/30 text-accent disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!hasData}
                  title="Restart animation"
                >
                  <RotateCcw className="w-5 h-5" />
                </Button>

                <div className="flex-1 space-y-2">
                  <Slider
                    value={[timeStep]}
                    min={0}
                    max={timeSteps.length > 0 ? timeSteps.length - 1 : 0}
                    onValueChange={([v]) => { setTimeStep(v); setPlaying(false); }}
                    className="cursor-pointer"
                    disabled={!hasData}
                  />
                  <div className="flex justify-between text-[10px] font-mono text-white/40 uppercase tracking-tighter">
                    <span>Start</span>
                    <span>Mid</span>
                    <span>End ({timeSteps.length > 0 ? timeSteps.length - 1 : "-"} steps)</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded-lg">
                  <Zap className="w-3.5 h-3.5 text-accent/70" />
                  <select
                    value={animationSpeed}
                    onChange={(e) => setAnimationSpeed(e.target.value as "0.5" | "1" | "2" | "4")}
                    disabled={!hasData}
                    aria-label="Animation speed"
                    className="bg-transparent text-white/80 text-xs font-mono cursor-pointer outline-none disabled:opacity-50"
                  >
                    <option value="0.5">0.5×</option>
                    <option value="1">1×</option>
                    <option value="2">2×</option>
                    <option value="4">4×</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-4 mt-4 pt-4 border-t border-white/5 flex-wrap items-center">
                <div className="flex items-center gap-1.5 text-[10px] text-white/60">
                  <span className="w-2 h-2 rounded-full inline-block" style={{ background: "#2f2f2f", opacity: 0.18 }} />
                  Particles ({timeSteps[timeStep]?.particles.length || 0})
                </div>
                {hasData && timeSteps.length > 0 && (
                  <div className="flex items-center gap-1.5 text-[10px] text-white/60">
                    <span className="w-2 h-2 rounded-full bg-accent/60 inline-block" />
                    Drift: {progress}% complete
                  </div>
                )}
                {/* 📐 Drift Distance Display */}
                {driftDistance !== null && (
                  <div className="flex items-center gap-1.5 text-[10px] text-accent/70">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent inline-block" />
                    Drift: {driftDistance.toFixed(1)} km from origin
                  </div>
                )}
                <div className="text-[10px] text-accent/70 ml-auto">
                  Natural particle diffusion with directional drift
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── GIF panel ───────────────────────────────────────────────────── */}
        {gifUrl && !isMaximized && (
          <div className="w-80 shrink-0 flex flex-col border-l border-white/5 bg-white/[0.02]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-white/60">
                  Particle Simulation
                </span>
              </div>
              {gifFramesReady && (
                <span className="text-[9px] text-accent/60 font-mono">synced</span>
              )}
            </div>

            <div className="flex-1 flex items-center justify-center p-3">
              <img
                key={gifFramesReady ? timeStep : "gif"}
                src={
                  gifFramesReady
                    ? `http://localhost:5000/api/results/${runId}/gif-frames/frame_${String(timeStep).padStart(2, "0")}.png`
                    : gifUrl
                }
                alt="Oil drift trajectory animation"
                className="w-full rounded-lg"
                style={{ height: "calc(500px - 80px)", objectFit: "contain" }}
              />
            </div>

            <div className="px-4 py-2 border-t border-white/5 space-y-0.5">
              <p className="text-[9px] text-white/40 font-mono">
                {hasData && timeSteps[timeStep] ? timeSteps[timeStep].time : "—"}
              </p>
              {displayCountry && (
                <p className="text-[9px] text-accent/70 font-medium">
                  {displayCountry}
                </p>
              )}
              <p className="text-[9px] text-white/20 leading-tight">
                OpenDrift · {timeSteps.length || 23} timesteps
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default TrajectoryMap;