import express from "express";
import path from "path";
import fs from "fs";
import { glob } from "glob";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";


const router = express.Router();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ─── Helpers ──────────────────────────────────────────────────────────────────

const resolveRunDir = (backendRoot: string, runId: string): string | undefined => {
  const candidates = [
    path.resolve(backendRoot, "oilspill_analysis", "runs", runId),
    path.resolve(backendRoot, "oilspill_analysis", "data", "processed", "runs", runId),
  ];
  return candidates.find((dir) => fs.existsSync(dir));
};

const toUploadUrl = (backendRoot: string, inputImagePath: unknown): string | null => {
  if (typeof inputImagePath !== "string" || inputImagePath.length === 0) return null;
  const uploadsDir = path.resolve(backendRoot, "uploads");
  const abs = path.isAbsolute(inputImagePath)
    ? inputImagePath
    : path.resolve(backendRoot, inputImagePath);
  if (!abs.startsWith(uploadsDir + path.sep)) return null;
  return `/uploads/${encodeURIComponent(path.basename(abs))}`;
};

const findTrajectoryCsv = (runDir: string): string | null => {
  const searchDirs = [
    path.join(runDir, "visualizations"),
    runDir,
  ];

  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;
    const files = fs.readdirSync(dir);

    const fullCsv = files.find((f) => f.endsWith("_trajectories_full.csv"));
    if (fullCsv) return path.join(dir, fullCsv);

    const normalCsv = files.find((f) => f.endsWith("_trajectories.csv"));
    if (normalCsv) return path.join(dir, normalCsv);
  }

  return null;
};


const findTrajectoryGif = (runDir: string): string | null => {
  const visualizationDir = path.join(runDir, "visualizations");
  if (!fs.existsSync(visualizationDir)) return null;

  const gifPatterns = [
    path.join(visualizationDir, "*_trajectory.gif"),
    path.join(visualizationDir, "trajectory_animation_*.gif"),
    path.join(visualizationDir, "*.gif"),
  ];

  for (const pattern of gifPatterns) {
    const matches = glob.sync(pattern);
    if (matches.length > 0) {
      matches.sort(
        (a, b) => fs.statSync(b).mtime.getTime() - fs.statSync(a).mtime.getTime()
      );
      return matches[0];
    }
  }
  return null;
};

// ─── Helper: Format NLP reports as historical transactions ───────────────────
const formatNlpIncidents = (nlp: any, runId: string): any[] => {
  const byDistance: any[] = nlp.reports?.by_distance ?? [];
  const byTime:     any   = nlp.reports?.by_time;
  const byJoint:    any   = nlp.reports?.by_joint;

  const allReports: any[] = [...byDistance];

  if (byTime && !allReports.find((r) => r.name === byTime.name)) {
    allReports.push(byTime);
  }
  if (byJoint && !allReports.find((r) => r.name === byJoint.name)) {
    allReports.push(byJoint);
  }

  return allReports.map((r: any, idx: number) => ({
    id:          idx + 1,
    date:        r.date ? new Date(r.date).getFullYear().toString() : "Unknown",
    distance:    r.distance_km != null ? `${Number(r.distance_km).toFixed(1)} km` : "—",
    cause:       r.cause_category ?? "Unknown",
    vessel:      r.name ?? `Incident #${idx + 1}`,
    risk:        nlp.risk_level ?? "HIGH",
    location:    r.location ?? "Unknown",
    description: r.description ?? "No description available.",
    prevention:  r.prevention_focus ?? "No prevention data available.",
    pdfUrl:      `/runs/${runId}/nlp_report.pdf`,
    transaction_type: "historical_match",
    match_method:     r.match_type ?? "unknown",
    confidence_score: r.confidence ?? null,
    timestamp:        r.date ?? null,
  }));
};

// ─── GET /:runId ──────────────────────────────────────────────────────────────

router.get("/:runId", async (req, res) => {
  const { runId } = req.params;

  try {
    const backendRoot = path.resolve(__dirname, "..", "..");
    const runDir = resolveRunDir(backendRoot, runId);

    if (!runDir) {
      return res.status(404).json({ error: "Run not found" });
    }

    const pipelineResultsPath = path.join(runDir, "pipeline_results.json");
    if (!fs.existsSync(pipelineResultsPath)) {
      return res.status(404).json({ error: "Pipeline results not found for this run" });
    }

    const raw = JSON.parse(fs.readFileSync(pipelineResultsPath, "utf-8"));
    const steps = raw.steps || {};

    const physicsGuided    = steps.pg_classification || {};
    const oilAnalysis      = steps.oil_analysis || {};
    const simulation       = steps.simulation || {};
    const nlp              = steps.nlp_validation || {};
    const ensembleDecision = steps.ensemble_decision || {};

    const physicsValidation = {
      drift_direction_deg:  physicsGuided.drift_direction ?? null,
      elongation_ratio:     physicsGuided.geometric_features?.elongation_ratio ?? null,
      compactness:          physicsGuided.geometric_features?.compactness ?? null,
      mean_intensity_db:    physicsGuided.radiometric_features?.mean_intensity ?? null,
      oil_percentage:       oilAnalysis.oil_percentage ?? null,
      oil_area_km2:         oilAnalysis.oil_area_km2 ?? null,
      rule_scores:          physicsGuided.rule_scores ?? null,
      rule_results:         physicsGuided.rule_results ?? null,
    };

    const classifier = {
      classification:       physicsGuided.classification ?? null,
      confidence:           physicsGuided.confidence ?? null,
      oil_score:            physicsGuided.oil_score ?? null,
      non_oil_score:        physicsGuided.non_oil_score ?? null,
      geometric_features:   physicsGuided.geometric_features ?? null,
      radiometric_features: physicsGuided.radiometric_features ?? null,
      rule_scores:          physicsGuided.rule_scores ?? null,
      rule_results:         physicsGuided.rule_results ?? null,
    };

    const trajectoryCsvPath = simulation.viewable_export?.csv as string | undefined;
    const trajectoryGifPath = simulation.gif_path as string | undefined;
    const realCsvPath       = findTrajectoryCsv(runDir) || trajectoryCsvPath || null;
    const realGifPath       = findTrajectoryGif(runDir) || trajectoryGifPath || null;

    // ✨ FIX: Simplified gifUrl to avoid double "visualizations"
    const gifUrl = realGifPath
      ? `/visualizations/${path.relative(path.dirname(runDir), realGifPath)}`
      : null;

    if (gifUrl) {
      console.log(`✅ gif_url for ${runId}: ${gifUrl}`);
    } else {
      console.warn(`⚠️  No GIF found for run ${runId}`);
    }

    const trajectory = {
      setup:             simulation.setup ?? null,
      results_summary:   simulation.results_summary ?? null,
      viewable_export:   simulation.viewable_export ?? null,
      csv_relative_path: realCsvPath ? path.relative(runDir, realCsvPath) : null,
      gif_relative_path: realGifPath ? path.relative(runDir, realGifPath) : null,
    };

    const historicalContext = {
      risk_level:       nlp.risk_level ?? null,
      confidence:       nlp.confidence ?? null,
      distance_matches: nlp.distance_matches ?? null,
      time_matches:     nlp.time_matches ?? null,
      joint_matches:    nlp.joint_matches ?? null,
      reports:          nlp.reports ?? null,
      summary:          nlp.summary ?? null,
      transactions:     formatNlpIncidents(nlp, runId),
      transaction_count: formatNlpIncidents(nlp, runId).length,
    };

    const decision = {
      final_prediction:     ensembleDecision.final_prediction ?? null,
      final_confidence:     ensembleDecision.final_confidence ?? null,
      individual_decisions: ensembleDecision.individual_decisions ?? null,
      decision_summary:     ensembleDecision.decision_summary ?? null,
    };

    res.json({
      runId,
      inputImageUrl: toUploadUrl(backendRoot, raw.input_image),
      gif_url:       gifUrl,
      physicsValidation,
      classifier,
      trajectory,
      historicalContext,
      decision,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to read pipeline results" });
  }
});

// ─── GET /:runId/trajectory-csv ───────────────────────────────────────────────

router.get("/:runId/trajectory-csv", async (req, res) => {
  const { runId } = req.params;

  try {
    const backendRoot = path.resolve(__dirname, "..", "..");
    const runDir = resolveRunDir(backendRoot, runId);

    if (!runDir) return res.status(404).json({ error: "Run not found" });

    const csvPath = findTrajectoryCsv(runDir);
    if (!csvPath) return res.status(404).json({ error: "Trajectories CSV not found" });

    console.log(`✅ Serving trajectory CSV: ${csvPath}`);
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", `inline; filename="${path.basename(csvPath)}"`);
    fs.createReadStream(csvPath).pipe(res);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to serve trajectory CSV" });
  }
});

// ✨ NEW: GET /:runId/trajectory-gif - Serves animated GIF fallback
router.get("/:runId/trajectory-gif", async (req, res) => {
  const { runId } = req.params;

  try {
    const backendRoot = path.resolve(__dirname, "..", "..");
    const runDir = resolveRunDir(backendRoot, runId);

    if (!runDir) return res.status(404).json({ error: "Run not found" });

    const gifPath = findTrajectoryGif(runDir);
    if (!gifPath) {
      console.warn(`⚠️ No animated GIF found for run ${runId}`);
      return res.status(404).json({ error: "Animated GIF not found" });
    }

    console.log(`✅ Serving animated GIF: ${gifPath}`);
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Content-Type", "image/gif");
    res.setHeader("Cache-Control", "public, max-age=3600");
    fs.createReadStream(gifPath).pipe(res);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to serve animated GIF" });
  }
});

// ─── GET /:runId/gif-frames ───────────────────────────────────────────────────

router.get("/:runId/gif-frames", async (req, res) => {
  const { runId } = req.params;

  try {
    const backendRoot = path.resolve(__dirname, "..", "..");
    const runDir      = resolveRunDir(backendRoot, runId);

    if (!runDir) return res.status(404).json({ error: "Run not found" });

    const framesDir  = path.join(runDir, "gif_frames");
    const boundsFile = path.join(framesDir, "bounds.json");

    if (!fs.existsSync(boundsFile)) {
      console.log(`[${runId}] gif_frames not found — running process_gif_frames.py ...`);

      const scriptPath = path.resolve(backendRoot, "process_gif_frames.py");

      const pythonCandidates = [
        "/Users/mac/miniconda3/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
        "python3",
        "python",
      ];
      const pythonCmd = pythonCandidates.find((cmd) => {
        const r = spawnSync(cmd, ["--version"], { encoding: "utf-8" });
        return r.status === 0;
      }) ?? "python3";

      console.log(`[${runId}] Using Python: ${pythonCmd}`);

      const result = spawnSync(pythonCmd, [scriptPath, runId], {
        encoding: "utf-8",
        timeout:  120_000,
        cwd:      backendRoot,
        env:      { ...process.env, PYTHONPATH: backendRoot },
      });

      if (result.status !== 0) {
        console.error(result.stderr);
        return res.status(500).json({
          error:  "Frame processing failed",
          detail: result.stderr?.slice(0, 400) ?? "Unknown error",
        });
      }

      console.log(result.stdout);
    }

    if (!fs.existsSync(boundsFile)) {
      return res.status(500).json({ error: "bounds.json not created after processing" });
    }

    const meta = JSON.parse(fs.readFileSync(boundsFile, "utf-8")) as {
      frame_count: number;
      bounds:      object;
      timestamps?: string[];
    };

    const frameUrls = Array.from({ length: meta.frame_count }, (_, i) =>
      `/api/results/${runId}/gif-frames/${`frame_${String(i).padStart(2, "0")}.png`}`
    );

    res.setHeader("Access-Control-Allow-Origin", "*");
    res.json({ ...meta, frame_urls: frameUrls });

  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to load gif frames" });
  }
});

// ─── GET /:runId/gif-frames/:filename ────────────────────────────────────────

router.get("/:runId/gif-frames/:filename", (req, res) => {
  const { runId, filename } = req.params;

  if (!/^frame_\d{2}\.png$/.test(filename)) {
    return res.status(400).json({ error: "Invalid filename" });
  }

  const backendRoot = path.resolve(__dirname, "..", "..");
  const runDir      = resolveRunDir(backendRoot, runId);
  if (!runDir) return res.status(404).json({ error: "Run not found" });

  const filePath = path.join(runDir, "gif_frames", filename);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: "Frame not found" });
  }

  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Content-Type", "image/png");
  res.setHeader("Cache-Control", "public, max-age=86400");
  fs.createReadStream(filePath).pipe(res);
});

// ─── GET /:runId/nlp/incidents ────────────────────────────────────────────────

router.get("/:runId/nlp/incidents", (req, res) => {
  const { runId } = req.params;

  try {
    const backendRoot = path.resolve(__dirname, "..", "..");
    const runDir      = resolveRunDir(backendRoot, runId);
    if (!runDir) return res.status(404).json({ error: "Run not found" });

    const pipelinePath = path.join(runDir, "pipeline_results.json");
    if (!fs.existsSync(pipelinePath))
      return res.status(404).json({ error: "Pipeline results not found" });

    const raw  = JSON.parse(fs.readFileSync(pipelinePath, "utf-8"));
    const nlp  = raw.steps?.nlp_validation ?? {};

    const incidents = formatNlpIncidents(nlp, runId);
    const inputImageUrl = toUploadUrl(backendRoot, raw.input_image);

    res.setHeader("Access-Control-Allow-Origin", "*");
    res.json({
      runId,
      riskLevel:     nlp.risk_level ?? null,
      incidents,
      inputImageUrl,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to load NLP incidents" });
  }
});

export default router;