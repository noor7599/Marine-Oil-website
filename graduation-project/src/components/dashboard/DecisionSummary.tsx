import { useEffect, useState } from "react";
import {
  FileText,
  Download,
  CheckCircle,
  AlertTriangle,
  Info,
  HelpCircle,
  Package
} from "lucide-react";
import { Button } from "@/components/ui/button";

type DecisionSummaryProps = {
  runId: string | null;
};

type DecisionApi = {
  final_prediction?: string | null;
  final_confidence?: number | null;
  decision_summary?: {
    oil_evidence?: number;
    nononoil_evidence?: number;
  } | null;
};

type HistoricalSummary = {
  oil_incidents_in_area?: number;
};

type ResultsApi = {
  decision?: DecisionApi;
  historicalContext?: {
    summary?: HistoricalSummary;
  };
  physicsValidation?: {
    drift_direction_deg?: number | null;
  };
  classifier?: {
    confidence?: number | null;
  };
};

const openDownload = (url: string) => {
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.click();
};

const DecisionSummary = ({ runId }: DecisionSummaryProps) => {
  const [generating, setGenerating] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [results, setResults] = useState<ResultsApi | null>(null);

  useEffect(() => {
    if (!runId) {
      setResults(null);
      setShowReport(false);
      setGenerating(false);
      return;
    }

    fetch(`http://localhost:5000/api/results/${runId}`)
      .then((res) => res.json())
      .then((json) => setResults(json))
      .catch((err) => {
        console.error("Failed to load decision summary data", err);
        setResults(null);
      });
  }, [runId]);

  const finalPrediction = results?.decision?.final_prediction ?? null;
  const finalConfidence = results?.decision?.final_confidence ?? null;

  const physicsPlausible = finalPrediction === "Oil-like";
  const status = physicsPlausible ? "confirmed" : "suspected";

  const handleGenerate = () => {
    if (!runId) return;

    setGenerating(true);

    setTimeout(() => {
      setGenerating(false);
      setShowReport(true);
    }, 1500);
  };

  return (
    <section
      className="glass-card p-6 animate-slide-up"
      style={{ animationDelay: "0.3s" }}
      aria-label="Decision summary and report generation"
    >
      <div className="flex items-center gap-2 mb-5">
        <FileText className="w-5 h-5 text-accent" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Decision Summary &amp; Report
        </h2>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
        <div className="xl:col-span-2 space-y-4">

          {/* STATUS */}

          {status === "confirmed" ? (
            <div className="flex items-center gap-3 bg-danger/10 border border-danger/30 rounded-lg p-5">
              <CheckCircle className="w-7 h-7 text-danger shrink-0" />
              <div>
                <p className="text-base font-bold text-danger">✓ Confirmed Oil Spill</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Physics-guided ensemble indicates oil spill with high confidence.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 bg-warning/10 border border-warning/30 rounded-lg p-5">
              <AlertTriangle className="w-7 h-7 text-warning shrink-0" />
              <div>
                <p className="text-base font-bold text-warning">⚠ Suspected Look-alike</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Physics check or ensemble decision below confirmation threshold.
                </p>
              </div>
            </div>
          )}

          {/* PIPELINE OUTPUT */}

          <div className="bg-background/50 rounded-lg border border-border/30 p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Pipeline Output
            </p>

            <p className="text-xs">
              Prediction: {finalPrediction || "Unknown"}
            </p>

            <p className="text-xs">
              Confidence: {finalConfidence != null
                ? `${(finalConfidence * 100).toFixed(1)}%`
                : "—"}
            </p>
          </div>

          {/* WHY THIS DECISION */}

          <div className="bg-background/50 rounded-lg border border-border/30 p-5 space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
              Why this decision
            </p>

            <div className="flex items-start gap-2.5">
              <span className="bg-accent/20 text-accent text-[9px] font-bold px-2 py-0.5 rounded">
                PRIMARY
              </span>
              <p className="text-xs">
                Physics-guided model — final prediction{" "}
                {finalPrediction || "Unknown"} with{" "}
                {finalConfidence != null
                  ? `${(finalConfidence * 100).toFixed(1)}%`
                  : "—"} confidence.
              </p>
            </div>

            <div className="flex items-start gap-2.5">
              <span className="bg-muted text-muted-foreground text-[9px] font-bold px-2 py-0.5 rounded">
                SUPPORT
              </span>
              <p className="text-xs text-muted-foreground">
                Statistical classifier and CV detection contribute additional evidence used in the ensemble.
              </p>
            </div>

            <div className="flex items-start gap-2.5">
              <span className="bg-muted text-muted-foreground text-[9px] font-bold px-2 py-0.5 rounded">
                CONTEXT
              </span>
              <p className="text-xs text-muted-foreground">
                Historical incident analysis and NLP risk assessment help prioritize operational response.
              </p>
            </div>
          </div>

          {/* KEY EVIDENCE */}

          <div className="bg-background/50 rounded-lg border border-border/30 p-5 space-y-2.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
              Key Evidence
            </p>

            {[
              {
                icon: <CheckCircle className="w-3.5 h-3.5 text-success" />,
                text: "Satellite detection and physics-guided analysis both indicate oil-like behavior."
              },
              {
                icon: <CheckCircle className="w-3.5 h-3.5 text-success" />,
                text: "Drift alignment and slick geometry derived from simulation outputs."
              },
              {
                icon: <CheckCircle className="w-3.5 h-3.5 text-success" />,
                text: "Ensemble decision combines CV, physics-guided, and NLP risk assessment."
              },
              {
                icon: <AlertTriangle className="w-3.5 h-3.5 text-warning" />,
                text: "Historical incident density and nearest matches increase operational risk."
              },
              {
                icon: <Info className="w-3.5 h-3.5 text-accent" />,
                text: "Forecast trajectory indicates potential coastal impact without mitigation."
              }
            ].map((e, i) => (
              <div key={i} className="flex items-start gap-2.5">
                {e.icon}
                <p className="text-xs text-muted-foreground">{e.text}</p>
              </div>
            ))}
          </div>

          {/* GENERATE REPORT BUTTON */}

          <Button
            className="w-full bg-accent text-accent-foreground hover:bg-accent/90 h-11"
            onClick={handleGenerate}
            disabled={generating || !runId}
          >
            {generating ? "Generating…" : "Generate Official Report"}
          </Button>
        </div>

        {/* REPORT PREVIEW */}

        <div className="xl:col-span-3 bg-background/50 rounded-lg border border-border/30 p-5 overflow-y-auto max-h-[600px]">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Report Preview
          </p>

          {showReport && runId ? (
            <>
              <iframe
                src={`http://localhost:5000/runs/${runId}/final_report.pdf`}
                className="w-full h-[500px] rounded border border-border"
              />

              <div className="border-t border-border/30 pt-4 mt-6">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                  <Download className="w-4 h-4 text-accent" />
                  Download Reports
                </h3>

                <div className="space-y-2">

                  <button
                    onClick={() =>
                      openDownload(`http://localhost:5000/runs/${runId}/final_report.pdf`)
                    }
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-danger/10 hover:bg-danger/20 border border-danger/30 text-danger rounded-lg text-sm font-medium"
                  >
                    <FileText className="w-4 h-4" />
                    Download Final Report (PDF)
                  </button>

                  <button
                    onClick={() =>
                      openDownload(`http://localhost:5000/runs/${runId}/all_outputs.zip`)
                    }
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-accent/10 hover:bg-accent/20 border border-accent/30 text-accent rounded-lg text-sm font-medium"
                  >
                    <Package className="w-4 h-4" />
                    Download All Resources (ZIP)
                  </button>

                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground/40">
              <HelpCircle className="w-8 h-8 mb-2" />
              <p className="text-xs">
                Click "Generate Official Report" to preview
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default DecisionSummary;
