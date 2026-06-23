import Header from "@/components/dashboard/Header";
import SARUpload from "@/components/dashboard/SARUpload";
import PhysicsValidation from "@/components/dashboard/PhysicsValidation";
import StatisticalClassifier from "@/components/dashboard/StatisticalClassifier";
import TrajectoryMap from "@/components/dashboard/TrajectoryMap";
import HistoricalContext from "@/components/dashboard/HistoricalContext";
import DecisionSummary from "@/components/dashboard/DecisionSummary";
import HelpSection from "@/components/dashboard/HelpSection";

import { useState, useEffect } from "react";

type ResultData = {
  inputImageUrl?: string | null;
  physicsValidation?: {
    oil_area_km2?: number | null;
  };
};

const Index = () => {

  const [runId, setRunId] = useState<string | null>(null);
  const [result, setResult] = useState<ResultData | null>(null);

  // Fetch result data when runId changes
  useEffect(() => {
    if (!runId) {
      setResult(null);
      return;
    }

    fetch(`http://localhost:5000/api/results/${runId}`)
      .then((res) => res.json())
      .then((data) => setResult(data))
      .catch((err) => {
        console.error("Failed to fetch result data:", err);
        setResult(null);
      });
  }, [runId]);

  return (
    <div className="min-h-screen ocean-gradient">

      <Header />

      <main
        className="container mx-auto px-4 py-8 space-y-8 max-w-7xl"
        role="main"
      >

        <SARUpload setRunId={setRunId} />

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <PhysicsValidation runId={runId} />
          <StatisticalClassifier runId={runId} />
        </div>

        <TrajectoryMap
          runId={runId}
          csvUrl={runId ? `http://localhost:5000/api/results/${runId}/trajectory-csv` : null}
          inputImageUrl={result?.inputImageUrl ? `http://localhost:5000${result.inputImageUrl}` : null}
          oilAreaKm2={result?.physicsValidation?.oil_area_km2 ?? null}
        />

        <HistoricalContext runId={runId} />

        <DecisionSummary runId={runId} />

        <HelpSection />

      </main>

    </div>
  );
};

export default Index;