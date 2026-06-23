import express from "express";
import cors from "cors";
import dotenv from "dotenv";

import pipelineRoutes from "./routes/pipelineRoutes";
import resultsRoutes from "./routes/resultsRoutes";


dotenv.config();

const app = express();

const PORT = process.env.PORT || 5000;

app.use(cors({
  origin: "http://localhost:8080",
  credentials: true
}));

app.use(express.json());
app.use(cors({ origin: "*" }));

app.use("/api/pipeline", pipelineRoutes);

app.use("/api/results", resultsRoutes);

app.use(
  "/runs",
  express.static("oilspill_analysis/runs")
);

app.get("/health", (req, res) => {

  res.json({
    status: "OK",
    timestamp: new Date().toISOString()
  });

});

app.listen(PORT, () => {

  console.log(`Server running on port ${PORT}`);

});