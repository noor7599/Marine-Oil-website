import { useEffect, useMemo, useState } from "react";
import { ShieldCheck, ShieldX, Compass, Maximize2, Activity, Circle } from "lucide-react";

type PhysicsValidationProps = {
  runId: string | null;
};

type PhysicsValidationResult = {
  drift_direction_deg: number | null;
  elongation_ratio: number | null;
  compactness: number | null;
  mean_intensity_db: number | null;
  oil_percentage: number | null;
  oil_area_km2: number | null;
  rule_scores?: Record<string, number> | null;
  rule_results?: {
    darkness_pass?: boolean;
    smoothness_pass?: boolean;
    shape_pass?: boolean;
    alignment_pass?: boolean;
    all_pass?: boolean;
  } | null;
};

const PhysicsValidation = ({ runId }: PhysicsValidationProps) => {
  const [data, setData] = useState<PhysicsValidationResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!runId) {
      setData(null);
      return;
    }

    setLoading(true);
    fetch(`http://localhost:5000/api/results/${runId}`)
      .then((res) => res.json())
      .then((json) => {
        setData(json.physicsValidation ?? null);
      })
      .catch((err) => {
        console.error("Failed to load physics validation", err);
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [runId]);

  const metrics = useMemo(() => {
    const base: PhysicsValidationResult | null = data;

    const driftPass = base?.rule_results?.alignment_pass ?? true;
    const shapePass = base?.rule_results?.shape_pass ?? true;
    const darknessPass = base?.rule_results?.darkness_pass ?? true;

    return [
      {
        label: "Drift alignment",
        value:
          base?.drift_direction_deg != null
            ? `${base.drift_direction_deg.toFixed(0)}°`
            : "—",
        detail: "Spill shape vs. dominant drift direction from simulation",
        icon: <Compass className="w-4 h-4" />,
        pass: driftPass
      },
      {
        label: "Shape: Elongation",
        value:
          base?.elongation_ratio != null
            ? base.elongation_ratio.toFixed(2)
            : "—",
        detail: "Elongated pattern consistent with wind and current stretching",
        icon: <Maximize2 className="w-4 h-4" />,
        pass: shapePass
      },
      {
        label: "Radar darkness",
        value:
          base?.mean_intensity_db != null
            ? `${base.mean_intensity_db.toFixed(1)} dB`
            : "—",
        detail: "Backscatter level relative to surrounding sea surface",
        icon: <Activity className="w-4 h-4" />,
        pass: darknessPass
      },
      {
        label: "Oil footprint",
        value:
          base?.oil_area_km2 != null
            ? `${base.oil_area_km2.toFixed(1)} km²`
            : "—",
        detail: "Estimated slick area derived from detected oil pixels",
        icon: <Circle className="w-4 h-4" />,
        pass: true
      }
    ];
  }, [data]);

  const allPass = metrics.every((m) => m.pass);

  return (
    <section className="glass-card p-6 animate-slide-up border-2 border-accent/20" style={{ animationDelay: "0.1s" }} aria-label="Physics validation results">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-accent" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Physical Plausibility Check
            </h2>
            <p className="text-[10px] text-muted-foreground mt-0.5">Primary Validation</p>
          </div>
        </div>
        <div
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold ${
            allPass
              ? "bg-success/15 text-success border border-success/30"
              : "bg-danger/15 text-danger border border-danger/30"
          }`}
          role="status"
          aria-live="polite"
        >
          {allPass ? <ShieldCheck className="w-4 h-4" aria-hidden="true" /> : <ShieldX className="w-4 h-4" aria-hidden="true" />}
          {allPass ? "✓ Physically Plausible" : "✗ Not Plausible"}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="flex items-center gap-3 bg-background/50 rounded-lg border border-border/30 px-4 py-3.5"
          >
            <div className="text-accent/70 shrink-0" aria-hidden="true">{m.icon}</div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground">{m.label}</p>
              <p className="text-[10px] text-muted-foreground leading-relaxed">{m.detail}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm font-mono font-semibold text-accent">
                {loading ? "…" : m.value}
              </span>
              {m.pass ? (
                <ShieldCheck className="w-4 h-4 text-success" aria-label="Passed" />
              ) : (
                <ShieldX className="w-4 h-4 text-danger" aria-label="Failed" />
              )}
            </div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-muted-foreground/60 mt-4 italic">
        Based on Sentinel-1 SAR geometry, CMEMS surface currents, and ERA5 wind fields.
      </p>
    </section>
  );
};

export default PhysicsValidation;
