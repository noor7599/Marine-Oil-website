import { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader } from "lucide-react";

type OilSimulationMapProps = {
  runId: string | null;
};

interface CSVCoordinate {
  latitude: number;
  longitude: number;
}

const OilSimulationMap = ({ runId }: OilSimulationMapProps) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const gifOverlayRef = useRef<any>(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gifUrl, setGifUrl] = useState<string | null>(null);
  const [bounds, setBounds] = useState<[[number, number], [number, number]] | null>(null);

  // Parse CSV and calculate bounding box
  const parseTrajectoryCSV = async (csvText: string): Promise<CSVCoordinate[]> => {
    const lines = csvText
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#"));

    if (lines.length <= 1) throw new Error("CSV has no data rows");

    const header = lines[0].split(",");
    const latIdx = header.indexOf("latitude");
    const lonIdx = header.indexOf("longitude");

    if (latIdx === -1 || lonIdx === -1) {
      throw new Error("CSV missing latitude or longitude columns");
    }

    const coords: CSVCoordinate[] = lines.slice(1).map((line) => {
      const cols = line.split(",");
      return {
        latitude: parseFloat(cols[latIdx]),
        longitude: parseFloat(cols[lonIdx]),
      };
    });

    return coords.filter(
      (c) => !isNaN(c.latitude) && !isNaN(c.longitude)
    );
  };

  // Calculate bounding box from coordinates
  const calculateBounds = (coords: CSVCoordinate[]): [[number, number], [number, number]] => {
    if (coords.length === 0) throw new Error("No valid coordinates");

    const lats = coords.map((c) => c.latitude);
    const lons = coords.map((c) => c.longitude);

    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);

    // Add padding (0.05 degrees ≈ 5.5km at equator)
    const padding = 0.05;

    return [
      [minLat - padding, minLon - padding],
      [maxLat + padding, maxLon + padding],
    ];
  };

  // Fetch and set up map
  useEffect(() => {
    if (!runId || !mapContainerRef.current) return;

    setLoading(true);
    setError(null);
    setGifUrl(null);
    setBounds(null);

    const setupMap = async () => {
      try {
        // Dynamically import Leaflet
        const L = await import("leaflet");

        // Initialize map
        const map = L.map(mapContainerRef.current!, {
          center: [0, 0],
          zoom: 2,
          zoomControl: true,
          attributionControl: true,
        });

        // Add tile layer
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "© OpenStreetMap contributors",
          opacity: 0.6,
          maxZoom: 19,
        }).addTo(map);

        mapInstanceRef.current = { map, L };

        // Try to fetch CSV to calculate bounds
        let calculatedBounds: [[number, number], [number, number]] | null = null;
        try {
          const csvPath = `${runId}_trajectories.csv`;
          const csvUrl = `http://localhost:5000/runs/${runId}/visualizations/${csvPath}`;
          
          console.log(`📊 Fetching CSV from: ${csvUrl}`);
          const csvRes = await fetch(csvUrl);
          
          if (!csvRes.ok) {
            throw new Error(`CSV fetch failed: ${csvRes.status}`);
          }

          const csvText = await csvRes.text();
          const coords = await parseTrajectoryCSV(csvText);
          
          if (coords.length > 0) {
            calculatedBounds = calculateBounds(coords);
            console.log(`✅ CSV parsed: ${coords.length} points, bounds:`, calculatedBounds);
          }
        } catch (csvErr) {
          console.warn("⚠️ CSV loading failed, will use fallback bounds:", csvErr);
          // Fallback: try to get start location from simulation results
          try {
            const simPath = `simulation_results_${runId}.json`;
            const simUrl = `http://localhost:5000/runs/${runId}/${simPath}`;
            const simRes = await fetch(simUrl);
            
            if (simRes.ok) {
              const simData = await simRes.json();
              const lat = simData?.setup?.release_location?.latitude;
              const lon = simData?.setup?.release_location?.longitude;
              
              if (typeof lat === "number" && typeof lon === "number") {
                // Small fallback bounds around start location
                const offset = 0.05;
                calculatedBounds = [
                  [lat - offset, lon - offset],
                  [lat + offset, lon + offset],
                ];
                console.log(`✅ Using fallback bounds from release_location:`, calculatedBounds);
              }
            }
          } catch (simErr) {
            console.warn("⚠️ Simulation file also unavailable:", simErr);
          }
        }

        if (!calculatedBounds) {
          throw new Error("Could not determine bounds from CSV or simulation data");
        }

        setBounds(calculatedBounds);

        // Fetch GIF URL and validate it exists
        const gifFileName = `trajectory_animation_${runId}.gif`;
        const gifUrl = `http://localhost:5000/runs/${runId}/visualizations/${gifFileName}`;
        
        console.log(`🎬 Fetching GIF from: ${gifUrl}`);
        
        // Validate GIF exists with HEAD request
        const gifCheck = await fetch(gifUrl, { method: "HEAD" });
        if (!gifCheck.ok) {
          throw new Error(`GIF not found: ${gifCheck.status}`);
        }

        setGifUrl(gifUrl);
        console.log(`✅ GIF validated: ${gifUrl}`);

        // Add GIF overlay to map
        gifOverlayRef.current = L.imageOverlay(gifUrl, calculatedBounds, {
          opacity: 0.85,
          interactive: false,
        }).addTo(map);

        console.log(`✅ GIF overlay added to map`);

        // Fit bounds to show entire animation
        map.fitBounds(calculatedBounds, { padding: [50, 50] });

        setLoading(false);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Unknown error";
        console.error("❌ Map setup failed:", errorMsg);
        setError(errorMsg);
        setLoading(false);
      }
    };

    setupMap();

    // Cleanup on unmount
    return () => {
      if (mapInstanceRef.current?.map) {
        mapInstanceRef.current.map.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [runId]);

  return (
    <div className="w-full h-full flex flex-col bg-background">
      {/* Leaflet CSS */}
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
      />

      {/* Loading State */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-50">
          <div className="flex flex-col items-center gap-3">
            <Loader className="w-8 h-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Loading simulation...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-50">
          <div className="flex flex-col items-center gap-3 p-4 bg-card border border-destructive/50 rounded-lg max-w-md">
            <AlertCircle className="w-8 h-8 text-destructive" />
            <p className="text-sm text-foreground text-center">
              <span className="font-semibold">Failed to load simulation:</span>
            </p>
            <p className="text-xs text-muted-foreground text-center">{error}</p>
          </div>
        </div>
      )}

      {/* Map Container */}
      <div
        ref={mapContainerRef}
        className="w-full h-full rounded-lg overflow-hidden"
      />

      {/* Status Footer */}
      {gifUrl && bounds && (
        <div className="text-xs text-muted-foreground p-2 text-center border-t border-border/30">
          ✅ GIF overlay loaded • Map bounds: [{bounds[0][0].toFixed(3)}, {bounds[0][1].toFixed(3)}]
          → [{bounds[1][0].toFixed(3)}, {bounds[1][1].toFixed(3)}]
        </div>
      )}
    </div>
  );
};

export default OilSimulationMap;
