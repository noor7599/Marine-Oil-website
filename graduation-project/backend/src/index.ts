import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import path from "path";
import fs from "fs";
import archiver from "archiver";
import { fileURLToPath } from "url";

import authRoutes from "./routes/auth.js";
import pipelineRoutes from "./routes/pipelineRoutes";
import { initDatabase } from "./database/init.js";
import { seedDatabase } from "./database/seed.js";
import resultsRoutes from "./routes/resultsRoutes";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const allowedOrigins = new Set(
  (process.env.CORS_ORIGIN
    ? process.env.CORS_ORIGIN.split(",").map((s) => s.trim())
    : ["http://localhost:8080", "http://localhost:8081", "http://localhost:5173"]
  ).filter(Boolean)
);

const isLocalhostOrigin = (origin: string) =>
  /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);

app.use(
  cors({
    origin(origin, callback) {
      if (!origin) return callback(null, true);
      if (isLocalhostOrigin(origin) || allowedOrigins.has(origin)) return callback(null, true);
      return callback(new Error(`CORS blocked for origin: ${origin}`));
    },
    credentials: true
  })
);

app.use(express.json());

app.use("/api/auth", authRoutes);
app.use("/api/pipeline", pipelineRoutes);
app.use("/api/results", resultsRoutes);

// Expose uploaded images
app.use("/uploads", (req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  next();
}, express.static(path.join(__dirname, "..", "uploads")));

const backendRoot = path.resolve(__dirname, "..");

// Helper to find the actual run directory on disk
const resolveRunDir = (runId: string): string | undefined => {
  const candidates = [
    path.resolve(backendRoot, "oilspill_analysis", "runs", runId),
    path.resolve(backendRoot, "oilspill_analysis", "data", "processed", "runs", runId)
  ];
  const found = candidates.find((p) => fs.existsSync(p));
  if (found) console.log(`📂 Resolved Run Dir for ${runId}: ${found}`);
  else console.warn(`❌ Run Dir NOT FOUND for ${runId}. Checked:`, candidates);
  return found;
};

// ✅ ZIP GENERATION
app.get("/runs/:runId/all_outputs.zip", (req, res) => {
  const runId = req.params.runId;
  const runDir = resolveRunDir(runId);
  
  if (!runDir) return res.status(404).json({ error: "Run ID not found" });

  let files = [];
  try {
    files = fs.readdirSync(runDir);
  } catch (e) {
    return res.status(500).json({ error: "Could not read run directory" });
  }

  if (files.length === 0) {
    fs.writeFileSync(path.join(runDir, 'README.txt'), 'No outputs generated yet.');
  }

  res.setHeader("Content-Type", "application/zip");
  res.setHeader("Content-Disposition", `attachment; filename="all_outputs_${runId}.zip"`);

  const archive = archiver("zip", { zlib: { level: 9 } });
  archive.on("error", (err) => {
    console.error("Archiver Error:", err);
    if (!res.headersSent) res.status(500).end();
  });
  archive.pipe(res);
  archive.directory(runDir, runId);
  archive.finalize();
});

// ✅ WILDCARD ROUTE FOR FILES (Mask, JSONs, etc.)
app.get("/runs/:runId/*", (req, res) => {
  const { runId } = req.params;
  const prefix = `/runs/${runId}/`;
  const relativeFilePath = req.path.startsWith(prefix) ? req.path.slice(prefix.length) : "";

  if (!relativeFilePath) return res.status(400).json({ error: "Invalid file path" });

  const runDir = resolveRunDir(runId);
  if (!runDir) return res.status(404).json({ error: "Run ID not found" });

  const fullPath = path.join(runDir, relativeFilePath);

  // Security Check
  if (!fullPath.startsWith(path.resolve(runDir))) {
    return res.status(403).json({ error: "Access denied" });
  }

  if (fs.existsSync(fullPath)) {
    console.log(`✅ Serving file: ${relativeFilePath}`);
    return res.sendFile(fullPath);
  }

  console.warn(`❌ File not found: ${fullPath}`);
  res.status(404).json({ 
    error: "File not found", 
    searchedIn: runDir,
    requested: relativeFilePath 
  });
});

// ✅ NLP REPORT ROUTE (With Detailed Logging)
app.get("/runs/:runId/nlp_report.pdf", (req, res) => {
  const runId = req.params.runId;
  const runDir = resolveRunDir(runId);
  if (!runDir) return res.status(404).json({ error: "Run not found" });

  const reportsDir = path.join(runDir, "reports");
  
  console.log(`🔍 Looking for NLP report in: ${reportsDir}`);

  if (!fs.existsSync(reportsDir)) {
    console.warn(`⚠️ Reports folder does not exist: ${reportsDir}`);
    return res.status(404).json({ error: "Reports folder not found" });
  }

  try {
    const files = fs.readdirSync(reportsDir);
    console.log(`📄 Files in reports folder:`, files);

    const candidates = files.filter((f) => f.toLowerCase().endsWith(".pdf") && f.startsWith("nlp_incident_report_"));
    
    const exact = candidates.find((f) => f.includes(runId));
    const picked = exact || candidates[0];
    
    if (!picked) {
        console.warn(`⚠️ No matching PDF found in reports folder.`);
        return res.status(404).json({ error: "NLP report not found" });
    }

    console.log(`✅ Serving NLP Report: ${picked}`);
    res.sendFile(path.join(reportsDir, picked));
  } catch (err) {
    console.error("Error reading reports directory:", err);
    res.status(500).json({ error: "Failed to read reports directory" });
  }
});

// ✅ NEW NLP REPORT ROUTE (Using /output/reports/ path)
app.get("/output/reports/nlp_incident_report_:runId.pdf", (req, res) => {
  const runId = req.params.runId;
  const runDir = resolveRunDir(runId);
  if (!runDir) return res.status(404).json({ error: "Run not found" });

  const reportsDir = path.join(runDir, "reports");
  
  console.log(`🔍 Looking for NLP report in: ${reportsDir}`);

  if (!fs.existsSync(reportsDir)) {
    console.warn(`⚠️ Reports folder does not exist: ${reportsDir}`);
    return res.status(404).json({ error: "Reports folder not found" });
  }

  try {
    const files = fs.readdirSync(reportsDir);
    console.log(`📄 Files in reports folder:`, files);

    const candidates = files.filter((f) => f.toLowerCase().endsWith(".pdf") && f.startsWith("nlp_incident_report_"));
    
    const exact = candidates.find((f) => f.includes(runId));
    const picked = exact || candidates[0];
    
    if (!picked) {
        console.warn(`⚠️ No matching PDF found in reports folder.`);
        return res.status(404).json({ error: "NLP report not found" });
    }

    console.log(`✅ Serving NLP Report: ${picked}`);
    res.sendFile(path.join(reportsDir, picked));
  } catch (err) {
    console.error("Error reading reports directory:", err);
    res.status(500).json({ error: "Failed to read reports directory" });
  }
});

// ✅ API: Get simulation results for a run
app.get("/api/runs/:runId/simulation-results", (req, res) => {
  const runId = req.params.runId;
  const runDir = resolveRunDir(runId);
  
  if (!runDir) return res.status(404).json({ error: "Run not found" });

  try {
    const files = fs.readdirSync(runDir);
    const simFile = files.find((f) => f.startsWith("simulation_results_") && f.endsWith(".json"));
    
    if (!simFile) {
      return res.status(404).json({ error: "Simulation results file not found" });
    }

    const simPath = path.join(runDir, simFile);
    const data = fs.readFileSync(simPath, "utf-8");
    res.json(JSON.parse(data));
  } catch (err) {
    console.error("Error reading simulation results:", err);
    res.status(500).json({ error: "Failed to read simulation results" });
  }
});

app.get("/health", (req, res) => {
  res.json({ status: "OK", timestamp: new Date().toISOString() });
});

app.use((req, res) => {
  res.status(404).json({ error: "Not found" });
});

app.use((err: any, req: express.Request, res: express.Response) => {
  console.error(err);
  res.status(500).json({ error: "Internal server error" });
});

const start = async () => {
  try {
    await initDatabase();
    await seedDatabase();
  } catch (err) {
    console.warn("Database init/seed skipped:", err);
  }

  app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
  });
};

start().catch((err) => {
  console.error("Startup failed:", err);
  process.exit(1);
});