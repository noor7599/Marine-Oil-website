import { spawn } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import pool from "../database/pool.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const saveCaseToDatabase = async (userId: string, runId: string): Promise<void> => {
  try {
    const backendRoot = path.resolve(__dirname, "..", "..");
    const runDir = path.resolve(backendRoot, "oilspill_analysis", "runs", runId);
    const pipelineResultsPath = path.join(runDir, "pipeline_results.json");

    if (!fs.existsSync(pipelineResultsPath)) {
      console.warn(`Pipeline results not found for run ${runId}, skipping DB save`);
      return;
    }

    const raw = JSON.parse(fs.readFileSync(pipelineResultsPath, "utf-8"));
    const steps = raw.steps || {};
    const physicsGuided = steps.pg_classification || {};
    const oilAnalysis = steps.oil_analysis || {};
    const ensembleDecision = steps.ensemble_decision || {};

    // Get input image URL
    let inputImageUrl: string | null = null;
    if (raw.input_image) {
      const uploadsDir = path.resolve(backendRoot, "uploads");
      const abs = path.isAbsolute(raw.input_image)
        ? raw.input_image
        : path.resolve(backendRoot, raw.input_image);
      if (abs.startsWith(uploadsDir + path.sep)) {
        inputImageUrl = `/uploads/${encodeURIComponent(path.basename(abs))}`;
      }
    }

    await pool.query(
      `INSERT INTO cases (user_id, run_id, input_image_url, confidence, classification, oil_area_km2, is_oil, risk_level)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT (user_id, run_id) DO UPDATE SET
         input_image_url = $3,
         confidence = $4,
         classification = $5,
         oil_area_km2 = $6,
         is_oil = $7,
         risk_level = $8,
         updated_at = CURRENT_TIMESTAMP`,
      [
        userId,
        runId,
        inputImageUrl,
        ensembleDecision.final_confidence ?? physicsGuided.confidence ?? null,
        physicsGuided.classification ?? "Unknown",
        oilAnalysis.oil_area_km2 ?? null,
        ensembleDecision.final_prediction ?? physicsGuided.classification === "Oil" ?? false,
        steps.nlp_validation?.risk_level ?? "UNKNOWN"
      ]
    );
    console.log(`✅ Case ${runId} saved to database for user ${userId}`);
  } catch (error) {
    console.error(`❌ Failed to save case to database:`, error);
    // Don't reject - pipeline succeeded, only DB save failed
  }
};

export const runPipeline = (imagePath: string, userId: string): Promise<any> => {
  return new Promise((resolve, reject) => {
    // Correctly resolve the backend root
    const backendRoot = path.resolve(__dirname, "..", "..");
    
    const scriptPath = path.resolve(
      backendRoot, 
      "oilspill_analysis", 
      "src", 
      "main", 
      "main_pipeline.py"
    );

    // FIXED: Corrected quotes and closing parenthesis below
    const csvPath = path.resolve(
      backendRoot, 
      "oilspill_analysis", 
      "data", 
      "raw", 
      "incidents_balanced_cleaned.csv"
    );

    const resolvedImagePath = path.isAbsolute(imagePath)
      ? imagePath
      : path.resolve(backendRoot, imagePath);

    if (!fs.existsSync(resolvedImagePath)) {
      reject(new Error(`Uploaded image not found on disk: ${resolvedImagePath}`));
      return;
    }

    let runId: string | null = null;
    let stderr = "";

    const oilspillCwd = path.resolve(backendRoot, "oilspill_analysis");

    // Allow overriding the python command (e.g. conda env) without editing code.
    // Examples:
    //   PIPELINE_PYTHON=python3
    //   PIPELINE_PYTHON="/Users/mac/miniconda3/envs/oilspill3/bin/python"
    //   PIPELINE_PYTHON="conda run -n oilspill3 python"
    const pythonCmd = process.env.PIPELINE_PYTHON || "python3";

    const shellEscape = (s: string) => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;

    const command = `${pythonCmd} ${shellEscape(scriptPath)} --image ${shellEscape(
      resolvedImagePath
    )} --csv ${shellEscape(csvPath)}`;

    const pyProcess = spawn(command, {
      shell: true,
      cwd: oilspillCwd
    });

    pyProcess.stdout.on("data", (data) => {
      const text = data.toString();
      console.log(text);
      
      // Look for the run ID in the output (e.g., runs/20260314T2222Z)
      const match = text.match(/runs\/([0-9TZ]+)/);
      if (match) {
        runId = match[1];
      }
    });

    pyProcess.stderr.on("data", (data) => {
      const text = data.toString();
      stderr += text;
      console.error("Python Error:", text);
    });

    pyProcess.on("close", async (code) => {
      if (code === 0 && runId) {
        // Save case to database
        await saveCaseToDatabase(userId, runId);
        resolve({
          message: "Pipeline completed",
          runId
        });
      } else if (code === 0 && !runId) {
        reject(new Error("Pipeline completed but no runId was found in output"));
      } else {
        const hint =
          stderr.includes("ModuleNotFoundError") || stderr.includes("ImportError")
            ? "Python environment is missing dependencies. Start backend with PIPELINE_PYTHON pointing to your working conda env (e.g. `PIPELINE_PYTHON=\"conda run -n oilspill3 python\"`)."
            : "";
        const message = [
          `Pipeline failed with exit code ${code}`,
          stderr ? `--- Python stderr ---\n${stderr.trim()}` : "",
          hint
        ]
          .filter(Boolean)
          .join("\n\n");
        reject(new Error(message));
      }
    });
  });
};