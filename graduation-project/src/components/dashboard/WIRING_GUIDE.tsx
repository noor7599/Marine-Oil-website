// ─────────────────────────────────────────────────────────────────────────────
// HOW TO WIRE THE NEW PROPS IN YOUR RESULTS PAGE
// ─────────────────────────────────────────────────────────────────────────────
//
// Your results page already calls:
//   GET http://localhost:5000/api/results/:runId
// which returns a JSON object that already contains:
//   result.inputImageUrl   →  e.g. "/uploads/2023-04-11-sentinel.jpg"
//   result.physicsValidation.oil_area_km2  →  e.g. 18.4
//
// You just need to forward those two values to <TrajectoryMap>.
// ─────────────────────────────────────────────────────────────────────────────

// BEFORE (what you had):
<TrajectoryMap runId={runId} />


// AFTER (add the two new props):
<TrajectoryMap
  runId={runId}

  // builds the CSV URL from runId automatically
  csvUrl={runId ? `http://localhost:5000/api/results/${runId}/trajectory-csv` : null}

  // prepend the backend host so the browser can fetch it
  // result.inputImageUrl is already the path e.g. "/uploads/filename.jpg"
  inputImageUrl={
    result?.inputImageUrl
      ? `http://localhost:5000${result.inputImageUrl}`
      : null
  }

  // optional but improves initial sizing; falls back to 20 km² if missing
  oilAreaKm2={result?.physicsValidation?.oil_area_km2 ?? null}
/>

// ─────────────────────────────────────────────────────────────────────────────
// BACKEND: make sure /uploads is served with CORS headers so the browser
// canvas can read the image (canvas.getContext("2d").getImageData() requires
// the image to be CORS-accessible).
//
// In your Express app (app.ts or server.ts), wherever you serve uploads,
// add the crossOrigin header:
// ─────────────────────────────────────────────────────────────────────────────

// In your Express server setup file, add this BEFORE your routes:
import cors from "cors";
app.use(cors());                               // already likely present

// Also add this so the /uploads folder is served with CORS headers:
app.use("/uploads", (req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  next();
}, express.static(path.join(__dirname, "uploads")));

// ─────────────────────────────────────────────────────────────────────────────
// HOW IT WORKS END TO END
// ─────────────────────────────────────────────────────────────────────────────
//
//  1. User uploads SAR image → pipeline runs → CSV saved to:
//       runs/{runId}/visualizations/simulation_*_trajectories.csv
//
//  2. Results page loads → fetches /api/results/:runId → gets inputImageUrl
//
//  3. TrajectoryMap receives inputImageUrl + csvUrl
//
//  4. processImageToOilMask() loads the SAR image into an off-screen canvas,
//     scans every pixel:
//       dark pixel  (luma < 65)  → orange-red,  fully opaque
//       edge pixel  (65–115)     → orange-red,  semi-transparent (soft edge)
//       light pixel (> 115)      → transparent  (sea disappears)
//     outputs a PNG data-URL that is just the oil blob, orange-red on transparent
//
//  5. That PNG is placed as an L.imageOverlay on the map, centred on the
//     first CSV timestep's mean lat/lon, sized to oilAreaKm2
//
//  6. Each animation frame (play button):
//       - center  shifts  → follows the mean lat/lon from that CSV timestep
//       - bounds  expand  → oil spreads up to 2.5× the initial area
//       - opacity drops   → oil dilutes as it spreads (0.85 → 0.45)
//       - CSS blur stays  → soft fluid edges throughout
//
//  Result: the actual oil blob shape from the SAR image appears on the map
//  and drifts + spreads exactly like the video, with no dots at all.
// ─────────────────────────────────────────────────────────────────────────────
