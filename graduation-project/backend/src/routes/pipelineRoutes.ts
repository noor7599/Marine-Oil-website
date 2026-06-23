import express from "express";
import multer from "multer";
import { runPipeline } from "../services/pipelineService";
import { authMiddleware } from "../middleware/auth.js";

const router = express.Router();

// Keep original filename so Python can read the date from it (e.g. "2023-04-11-...")
const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, "uploads/"),
  filename:    (_req,  file, cb) => cb(null, file.originalname),
});

const upload = multer({ storage });

router.post("/run", authMiddleware, upload.single("image"), async (req, res) => {
  try {
    const imagePath = req.file?.path;
    if (!imagePath)
      return res.status(400).json({ error: "No image uploaded" });

    const userId = req.user?.userId;
    if (!userId)
      return res.status(401).json({ error: "User not authenticated" });

    const result = await runPipeline(imagePath, userId);
    res.json(result);
  } catch (error) {
    console.error("Pipeline Error:", error);
    res.status(500).json({
      error:   "Pipeline failed",
      details: error instanceof Error ? error.message : String(error),
    });
  }
});

export default router;