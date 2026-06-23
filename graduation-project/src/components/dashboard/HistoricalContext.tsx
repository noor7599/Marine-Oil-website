import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { History, Shield, ShieldAlert, ExternalLink } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Button } from "@/components/ui/button";

type HistoricalContextProps = {
  runId: string | null;
};

type HistoricalSummary = {
  total_incidents_analyzed?: number;
  distance_matches_found?: number;
  time_matches?: number;
  joint_matches?: number;
  oil_incidents_in_area?: number;
  closest_distance_km?: number;
  closest_time_years?: number;
  recommendation?: string;
};

type HistoricalReport = {
  date?: string;
  distance_km?: number;
  cause_category?: string;
  name?: string;
};

type HistoricalApi = {
  risk_level?: string;
  confidence?: number;
  reports?: {
    by_distance?: HistoricalReport[];
  };
  summary?: HistoricalSummary;
};

const baseColors = [
  "hsl(4, 78%, 62%)",
  "hsl(38, 92%, 50%)",
  "hsl(186, 80%, 42%)",
  "hsl(260, 48%, 65%)",
  "hsl(210, 10%, 45%)"
];

const HistoricalContext = ({ runId }: HistoricalContextProps) => {
  const navigate = useNavigate();
  const [data, setData] = useState<HistoricalApi | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(null);
      return;
    }

    fetch(`http://localhost:5000/api/results/${runId}`)
      .then((res) => res.json())
      .then((json) => {
        setData(json.historicalContext ?? null);
      })
      .catch((err) => {
        console.error("Failed to load historical context", err);
        setData(null);
      });
  }, [runId]);

  const { causeData, historicalSpills } = useMemo(() => {
    const reports = data?.reports?.by_distance ?? [];

    const spills = reports.slice(0, 3).map((r, idx) => ({
      year: r.date ? new Date(r.date).getFullYear() : 0,
      distance: r.distance_km != null ? `${r.distance_km.toFixed(1)} km` : "—",
      cause: r.cause_category || "Unknown",
      vessel: r.name || `Incident #${idx + 1}`
    }));

    const counts: Record<string, number> = {};
    reports.forEach((r) => {
      const key = r.cause_category || "Unknown";
      counts[key] = (counts[key] || 0) + 1;
    });

    const total = Object.values(counts).reduce((acc, v) => acc + v, 0) || 1;
    const causes = Object.entries(counts).map(([name, count], idx) => ({
      name,
      value: (count / total) * 100,
      color: baseColors[idx % baseColors.length]
    }));

    return {
      causeData: causes,
      historicalSpills: spills
    };
  }, [data]);

  const riskLabel = data?.risk_level || "UNKNOWN RISK";
  const incidentsInArea = data?.summary?.oil_incidents_in_area;

  return (
    <section className="glass-card p-6 animate-slide-up" style={{ animationDelay: "0.25s" }} aria-label="Historical incident context">
      <div className="flex items-center gap-2 mb-5">
        <History className="w-5 h-5 text-accent" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Historical Context
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 space-y-4">
          {/* Risk badge — large, clear */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2.5 bg-danger/10 border border-danger/30 rounded-lg px-5 py-3" role="status">
              <ShieldAlert className="w-6 h-6 text-danger" aria-hidden="true" />
              <div>
                <p className="text-base font-bold text-danger">⚠ {riskLabel} AREA</p>
                <p className="text-xs text-muted-foreground">
                  {incidentsInArea != null ? `${incidentsInArea} past incidents within search area` : "Historical incidents in vicinity"}
                </p>
              </div>
            </div>
          </div>

          {/* Historical spills table */}
          <div className="bg-background/50 rounded-lg border border-border/30 overflow-hidden">
            <table className="w-full text-xs" role="table" aria-label="Past incidents near this location">
              <thead>
                <tr className="border-b border-border/30">
                  <th className="text-left px-4 py-2.5 text-muted-foreground font-medium">Year</th>
                  <th className="text-left px-4 py-2.5 text-muted-foreground font-medium">Distance</th>
                  <th className="text-left px-4 py-2.5 text-muted-foreground font-medium">Cause</th>
                  <th className="text-left px-4 py-2.5 text-muted-foreground font-medium hidden sm:table-cell">Vessel</th>
                </tr>
              </thead>
              <tbody>
                {historicalSpills.map((s, idx) => (
                  <tr key={`${s.year}-${idx}`} className="border-b border-border/20 last:border-0">
                    <td className="px-4 py-2.5 font-mono text-foreground">{s.year || "—"}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{s.distance}</td>
                    <td className="px-4 py-2.5">
                      <span className="bg-warning/10 text-warning px-2 py-0.5 rounded text-[10px] font-medium">{s.cause}</span>
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground hidden sm:table-cell">{s.vessel}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Prevention tip */}
          <div className="flex items-start gap-2.5 bg-accent/5 border border-accent/20 rounded-lg px-4 py-3">
            <Shield className="w-4 h-4 text-accent mt-0.5 shrink-0" aria-hidden="true" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              <span className="text-accent font-medium">Prevention tip:</span> Use enhanced navigation systems in shallow coastal zones. Historical groundings in this region correlate with inadequate depth data.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            className="text-xs gap-1.5"
            onClick={() => {
              if (!runId) return;
              navigate(`/historical-reports?runId=${encodeURIComponent(runId)}`);
            }}
          >
            <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" /> View All Reports
          </Button>
        </div>

        {/* Pie chart */}
        <div className="bg-background/50 rounded-lg border border-border/30 p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Cause Distribution</p>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={causeData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value">
                {causeData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "hsl(216, 40%, 16%)",
                  border: "1px solid hsl(216, 25%, 25%)",
                  borderRadius: "6px",
                  color: "hsl(60, 6%, 88%)",
                  fontSize: 12,
                }}
                formatter={(value: number) => [`${value}%`, "Share"]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {causeData.map((c) => (
              <div key={c.name} className="flex items-center gap-2 text-[10px]">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: c.color }} aria-hidden="true" />
                <span className="text-muted-foreground">{c.name}</span>
                <span className="ml-auto font-mono text-foreground">{c.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default HistoricalContext;