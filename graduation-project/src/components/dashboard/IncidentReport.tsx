import { forwardRef } from "react";

const IncidentReport = forwardRef<HTMLDivElement>((_, ref) => {
  const now = new Date();
  const utcTimestamp = now.toISOString().replace("T", " ").slice(0, 19) + " UTC";

  return (
    <div
      ref={ref}
      className="bg-white text-[#1a1a1a] rounded-lg overflow-hidden shadow-xl"
      style={{
        fontFamily: "'Inter', 'Calibri', 'Arial', sans-serif",
        maxWidth: "210mm",
        margin: "0 auto",
      }}
    >
      {/* Header Bar */}
      <div className="bg-[#0d1b2a] text-white px-8 py-5 flex items-center justify-between">
        <div>
          <p className="text-[10px] tracking-[0.3em] uppercase text-red-400 font-semibold mb-1">
            Confidential – Oil Spill Incident Report
          </p>
          <p className="text-lg font-bold tracking-tight">🛟 OceanGuard AI</p>
        </div>
        <div className="text-right text-[11px] text-gray-300 leading-relaxed">
          <p>Report ID: OG-{now.getFullYear()}-{String(now.getMonth() + 1).padStart(2, "0")}{String(now.getDate()).padStart(2, "0")}-001</p>
          <p>Generated: {utcTimestamp}</p>
        </div>
      </div>

      <div className="px-8 py-6 space-y-5 text-[13px] leading-relaxed">
        {/* Section 1 — Incident Summary */}
        <section>
          <SectionTitle icon="📡" title="Incident Summary" />
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 mt-2">
            <Field label="Status">
              <span className="inline-flex items-center gap-1.5 bg-green-100 text-green-800 font-semibold px-2 py-0.5 rounded text-xs">
                ✅ Confirmed Oil Spill
              </span>
            </Field>
            <Field label="Detection Time">{utcTimestamp}</Field>
            <Field label="Location">38.7000°N, 20.3000°E (Ionian Sea)</Field>
            <Field label="Estimated Spill Area">~4.2 km²</Field>
          </div>
        </section>

        <Divider />

        {/* Section 2 — Evidence & Validation */}
        <section>
          <SectionTitle icon="📊" title="Evidence & Validation" />
          <div className="mt-2 space-y-1.5">
            <EvidenceRow
              label="Computer Vision"
              value="Detected by MarineXt model (F1 = 87%, IoU = 0.58)"
              pass
            />
            <EvidenceRow
              label="Physics Check"
              value="Drift alignment: 89° (within 90° tolerance) — physically plausible"
              pass
            />
            <EvidenceRow
              label="ML Classifier"
              value="Oil-like classification with 99.94% confidence"
              pass
            />
            <EvidenceRow
              label="Historical Context"
              value="HIGH-RISK ZONE: 3 past spills within 35 km (last: 2022, cause: grounding)"
              warn
            />
          </div>
        </section>

        <Divider />

        {/* Section 3 — Drift Forecast */}
        <section>
          <SectionTitle icon="🌊" title="Drift Forecast (Next 24 Hours)" />
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2">
            <Field label="Primary Direction">Northeast at ~2.3 km/h</Field>
            <Field label="Coastal Proximity">Approaching western coastline within 18–24 h</Field>
          </div>
          <p className="text-[11px] text-gray-500 mt-2 italic">
            Based on real-time CMEMS surface currents and ERA5 10 m wind fields.
          </p>
        </section>

        <Divider />

        {/* Section 4 — Recommended Actions */}
        <section>
          <SectionTitle icon="🛟" title="Recommended Actions" />
          <div className="mt-2 space-y-2">
            <ActionRow
              priority="Immediate"
              color="bg-red-600"
              text="Deploy containment booms and response team to centroid coordinates (38.7°N, 20.3°E). Escalate to REMPEC and national coast guard."
            />
            <ActionRow
              priority="Monitoring"
              color="bg-amber-500"
              text="Track drift trajectory using attached NetCDF file. Schedule follow-up SAR acquisition in 12 h."
            />
            <ActionRow
              priority="Prevention"
              color="bg-blue-600"
              text="Likely cause: Grounding — verify vessel traffic in the area. Initiate Tier-2 response protocol."
            />
          </div>
        </section>

        <Divider />

        {/* Signature Block */}
        <section className="grid grid-cols-2 gap-8">
          <div>
            <p className="text-[11px] text-gray-500 mb-6">Authorized Signature</p>
            <div className="border-b border-gray-300 w-48" />
            <p className="text-[10px] text-gray-400 mt-1">Name / Agency / Date</p>
          </div>
          <div>
            <p className="text-[11px] text-gray-500 mb-6">Agency Stamp</p>
            <div className="w-20 h-20 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center text-[10px] text-gray-400">
              Stamp
            </div>
          </div>
        </section>
      </div>

      {/* Footer */}
      <div className="bg-[#0d1b2a] text-gray-400 px-8 py-3 text-[10px] flex justify-between items-center">
        <div className="space-y-0.5">
          <p><span className="text-gray-500">Data:</span> Sentinel-1 · CMEMS · ERA5</p>
          <p><span className="text-gray-500">Models:</span> MarineXt · OpenOil · Gradient Boosting · Mistral-7B</p>
        </div>
        <div className="text-right space-y-0.5">
          <p>CPU-only · Open-source · Offline-capable</p>
          <p className="text-gray-500">OceanGuard AI v1.0</p>
        </div>
      </div>
    </div>
  );
});

IncidentReport.displayName = "IncidentReport";

/* ---------- Sub-components ---------- */

const SectionTitle = ({ icon, title }: { icon: string; title: string }) => (
  <h3 className="text-sm font-bold text-[#0d1b2a] uppercase tracking-wider flex items-center gap-2 border-b border-gray-200 pb-1">
    <span>{icon}</span> {title}
  </h3>
);

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div>
    <p className="text-[11px] text-gray-500 font-medium">{label}</p>
    <p className="text-[13px] text-[#1a1a1a]">{children}</p>
  </div>
);

const EvidenceRow = ({ label, value, pass, warn }: { label: string; value: string; pass?: boolean; warn?: boolean }) => (
  <div className="flex items-start gap-2 bg-gray-50 rounded px-3 py-2">
    <span className="mt-0.5 text-xs shrink-0">
      {warn ? "⚠️" : pass ? "✅" : "❓"}
    </span>
    <p className="text-[12px]">
      <span className="font-semibold text-[#0d1b2a]">{label}:</span>{" "}
      <span className={warn ? "text-amber-700 font-medium" : "text-gray-700"}>{value}</span>
    </p>
  </div>
);

const ActionRow = ({ priority, color, text }: { priority: string; color: string; text: string }) => (
  <div className="flex items-start gap-2">
    <span className={`${color} text-white text-[10px] font-bold uppercase px-2 py-0.5 rounded shrink-0 mt-0.5`}>
      {priority}
    </span>
    <p className="text-[12px] text-gray-700">{text}</p>
  </div>
);

const Divider = () => <hr className="border-gray-200" />;

export default IncidentReport;
