import { useNavigate } from "react-router-dom";
import { ArrowLeft, Download, Database, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

const metadata = [
  { label: "File", value: "simulation_20260211T1430.nc" },
  { label: "Start Time", value: "2026-02-11 14:30 UTC" },
  { label: "End Time", value: "2026-02-12 14:30 UTC" },
  { label: "Spill Centroid", value: "29.1234°N, 90.5678°W" },
  { label: "Particle Count", value: "5,000" },
  { label: "Time Steps", value: "48 (hourly)" },
  { label: "Data Sources", value: "CMEMS currents, ERA5 wind" },
];

const NetCDFDetails = () => {
  const navigate = useNavigate();

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

      <main className="container mx-auto px-4 py-6 max-w-3xl">
        <div className="flex items-center gap-3 mb-6">
          <Database className="w-6 h-6 text-accent" />
          <div>
            <h1 className="text-xl font-bold text-foreground">Trajectory Simulation Output</h1>
            <p className="text-xs text-muted-foreground">🌊 NetCDF Metadata Details</p>
          </div>
        </div>

        <div className="glass-card p-6 space-y-4">
          {/* Status */}
          <div className="flex items-center gap-2 bg-success/10 border border-success/30 rounded-lg px-4 py-3">
            <CheckCircle className="w-5 h-5 text-success" />
            <div>
              <p className="text-sm font-semibold text-success">Completed — Ready for Analysis</p>
              <p className="text-xs text-muted-foreground">Simulation finished successfully</p>
            </div>
          </div>

          {/* Metadata Grid */}
          <div className="bg-background/50 rounded-lg border border-border/30 divide-y divide-border/20">
            {metadata.map((item) => (
              <div key={item.label} className="flex items-center justify-between px-4 py-3">
                <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{item.label}</span>
                <span className="text-sm font-mono text-foreground">{item.value}</span>
              </div>
            ))}
          </div>


        </div>
      </main>
    </div>
  );
};

export default NetCDFDetails;
