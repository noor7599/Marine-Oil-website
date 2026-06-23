import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, FileText, Eye, X, MapPin, AlertTriangle, Shield, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

const riskColor: Record<string, string> = {
  HIGH: "bg-danger/10 text-danger border-danger/30",
  MEDIUM: "bg-warning/10 text-warning border-warning/30",
  LOW: "bg-accent/10 text-accent border-accent/30",
};

type Incident = {
  id: number;
  date: string;
  distance: string;
  cause: string;
  vessel: string;
  risk: string;
  location: string;
  description: string;
  prevention: string;
  pdfUrl: string;
};

type NlpIncidentsResponse = {
  runId: string;
  riskLevel: string | null;
  incidents: Incident[];
  inputImageUrl: string | null;
};

const HistoricalReports = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const runId = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("runId");
  }, [location.search]);

  const [data, setData] = useState<NlpIncidentsResponse | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(null);
      return;
    }

    fetch(`http://localhost:5000/api/results/${runId}/nlp/incidents`)
      .then((res) => res.json())
      .then((json) => setData(json))
      .catch((err) => {
        console.error("Failed to load NLP incidents", err);
        setData(null);
      });
  }, [runId]);

  const incidents = data?.incidents ?? [];
  const inputImageUrl = data?.inputImageUrl ?? null;

  return (
    <div className="min-h-screen ocean-gradient">
      {/* Navbar */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-md sticky top-0 z-50">
        <div className="container mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/dashboard")} className="gap-2 text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 max-w-5xl">
        <div className="flex items-center gap-3 mb-6">
          <FileText className="w-6 h-6 text-accent" />
          <div>
            <h1 className="text-xl font-bold text-foreground">Historical Incident Reports</h1>
            <p className="text-xs text-muted-foreground">📁 Retrieved incidents within 50 km of current detection point</p>
          </div>
        </div>

        {/* Table */}
        <div className="glass-card overflow-hidden mb-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider">Date</th>
                <th className="text-left px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider">Distance</th>
                <th className="text-left px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider">Cause</th>
                <th className="text-left px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider hidden sm:table-cell">Risk</th>
                <th className="text-right px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id} className="border-b border-border/20 last:border-0 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3 font-mono text-foreground">{inc.date}</td>
                  <td className="px-4 py-3 text-muted-foreground">{inc.distance}</td>
                  <td className="px-4 py-3">
                    <span className="bg-warning/10 text-warning px-2 py-0.5 rounded text-xs">{inc.cause}</span>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${riskColor[inc.risk] || riskColor.HIGH}`}>{inc.risk}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={() => setSelectedIncident(inc)}>
                      <Eye className="w-3.5 h-3.5" /> View Full Report
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Download Button - Centered Below Table */}
        <div className="flex justify-center mt-8">
          <button
            onClick={() => {
              if (!runId) return;
              const a = document.createElement("a");
              a.href = `http://localhost:5000/output/reports/nlp_incident_report_${encodeURIComponent(runId)}.pdf`;
              a.target = "_blank";
              a.rel = "noopener noreferrer";
              a.click();
            }}
            className="inline-flex items-center gap-2 px-6 py-3 bg-accent/10 hover:bg-accent/20 border border-accent/30 text-accent rounded-lg transition-all duration-200 font-medium text-sm shadow-lg hover:shadow-xl hover:scale-105"
          >
            <Download className="w-4 h-4" />
            Download NLP Results
          </button>
        </div>
      </main>

      {/* Report Modal */}
      {selectedIncident && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4" onClick={() => setSelectedIncident(null)}>
          <div className="bg-card border border-border/50 rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-accent" />
                <h3 className="font-semibold text-foreground">Incident Report — {selectedIncident.date}</h3>
              </div>
              <button
                onClick={() => setSelectedIncident(null)}
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Close report"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-6 py-5 space-y-5 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1">📍 Location</p>
                  <p className="text-foreground flex items-center gap-1"><MapPin className="w-3.5 h-3.5 text-accent" /> {selectedIncident.location}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1">Vessel</p>
                  <p className="text-foreground">{selectedIncident.vessel}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1">Cause</p>
                  <p className="text-warning font-medium">{selectedIncident.cause}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-1">Distance from Detection</p>
                  <p className="text-foreground">{selectedIncident.distance}</p>
                </div>
              </div>

              <div>
                <p className="text-xs text-muted-foreground font-medium mb-1">📋 Description</p>
                <p className="text-muted-foreground leading-relaxed">{selectedIncident.description}</p>
              </div>

              <div className="bg-accent/5 border border-accent/20 rounded-lg p-4 flex items-start gap-2">
                <Shield className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-accent font-semibold mb-1">Prevention Recommendation</p>
                  <p className="text-xs text-muted-foreground">{selectedIncident.prevention}</p>
                </div>
              </div>

              {inputImageUrl && (
                <div>
                  <p className="text-xs text-muted-foreground font-medium mb-2">🛰 Uploaded SAR Image</p>
                  <img
                    src={`http://localhost:5000${inputImageUrl}`}
                    alt="Uploaded SAR"
                    className="w-full rounded-lg border border-border/50"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HistoricalReports;