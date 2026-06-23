import React, { useState, useCallback, useRef } from "react";
import { Upload, Loader2, AlertTriangle, CheckCircle, MapPin, RefreshCw, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const SARUpload = ({ setRunId }: { setRunId: (runId: string) => void }) => {
  const [status, setStatus] = useState<"idle" | "uploading" | "detected" | "clear">("idle");
  const [fileName, setFileName] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  
  // State for Backend Outputs
  const [maskUrl, setMaskUrl] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const runPipeline = async (file: File) => {
    // 1. Set Local Preview (The Original Uploaded Image)
    const localPreview = URL.createObjectURL(file);
    setPreviewUrl(localPreview);
    setFileName(file.name);
    setStatus("uploading");

    const formData = new FormData();
    formData.append("image", file);

    try {
      // Get auth token
      const token = localStorage.getItem('authToken');
      if (!token) {
        throw new Error('Authentication required. Please log in again.');
      }

      // 2. Run Pipeline
      const res = await fetch("http://localhost:5000/api/pipeline/run", {
        method: "POST",
        body: formData,
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!res.ok) throw new Error(`Server Error: ${res.status}`);

      const data = await res.json();
      if (!data.runId) throw new Error("No runId returned");

      setRunId(data.runId);
      const runId = data.runId;
      console.log("🚀 Pipeline Started. RunID:", runId);

      // --- FETCH CONFIDENCE & STATUS ---
      try {
        const cvRes = await fetch(`http://localhost:5000/runs/${runId}/cv_results.json`);
        if (cvRes.ok) {
          const cvData = await cvRes.json();
          setConfidence(typeof cvData?.confidence === 'number' ? cvData.confidence : 0.0);
          setStatus(cvData?.detected === true ? "detected" : "clear");
          console.log("✅ CV Results loaded. Detected:", cvData?.detected);
        } else {
          console.warn("⚠️ cv_results.json not found. Using defaults.");
          setStatus("clear");
          setConfidence(0.0);
        }
      } catch (e) { 
        console.error("❌ CV Fetch Error:", e); 
      }

      // --- FETCH LOCATION ---
      // Use API endpoint to find simulation_results_*.json
      try {
        const simRes = await fetch(`http://localhost:5000/api/runs/${runId}/simulation-results`);
        
        if (simRes.ok) {
          const simData = await simRes.json();
          const lat = simData?.setup?.release_location?.latitude;
          const lon = simData?.setup?.release_location?.longitude;
          
          if (typeof lat === 'number' && typeof lon === 'number') {
            setLocation({ lat, lon });
            console.log(`✅ Location loaded from simulation results:`, { lat, lon });
          } else {
            console.warn("⚠️ No valid location data found. Using fallback.");
            setLocation({ lat: 29.123, lon: -90.568 });
          }
        } else {
          console.warn("⚠️ Simulation results not found. Using fallback.");
          setLocation({ lat: 29.123, lon: -90.568 });
        }
      } catch (e) {
        console.warn("⚠️ Error fetching simulation results:", e);
        setLocation({ lat: 29.123, lon: -90.568 });
      }

      // --- FETCH MASK OVERLAY ---
      // Exact filename: cv_oil_binary.png (from visualizations folder)
      const maskName = "cv_oil_binary.png";
      const maskUrlStr = `http://localhost:5000/runs/${runId}/visualizations/${maskName}`;
      
      const maskCheck = await fetch(maskUrlStr, { method: 'HEAD' });
      if (maskCheck.ok) {
        setMaskUrl(maskUrlStr);
        console.log(`✅ Mask loaded: ${maskName}`);
      } else {
        console.warn(`❌ Mask not found: ${maskName}. Check backend terminal for file list.`);
        setMaskUrl(null);
      }

    } catch (err) {
      console.error(err);
      setStatus("idle");
      setPreviewUrl(null);
      setMaskUrl(null);
      setConfidence(null);
      setLocation(null);
      window.alert(err instanceof Error ? err.message : "Processing failed");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Basic validation
    if (file.size > 50 * 1024 * 1024) {
      alert('File size must be less than 50MB');
      return;
    }
    runPipeline(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    runPipeline(file);
  }, []);

  const handleReset = () => {
    setStatus("idle");
    setPreviewUrl(null);
    setMaskUrl(null);
    setConfidence(null);
    setLocation(null);
    setFileName("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary text-sm">1</span>
            SAR Detection
          </h2>
        </div>
        {status !== "idle" && (
          <Button variant="ghost" onClick={handleReset} className="text-muted-foreground hover:text-foreground">
            <RefreshCw className="w-4 h-4 mr-2" />
            Reset
          </Button>
        )}
      </div>

      {/* Upload State */}
      {status === "idle" && (
        <Card 
          className="border-2 border-dashed border-border bg-card/50 hover:bg-card transition-colors cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <CardContent className="flex flex-col items-center justify-center py-16 space-y-4">
            <div className="p-4 rounded-full bg-primary/10 text-primary">
              <Upload className="w-8 h-8" />
            </div>
            <div className="text-center space-y-1">
              <p className="font-medium text-lg">Upload Sentinel-1 GeoTIFF</p>
              <p className="text-sm text-muted-foreground">Drag & drop or click to browse</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".tif,.tiff,.png,.jpg"
              onChange={handleFileChange}
              className="hidden"
            />
          </CardContent>
        </Card>
      )}

      {/* Processing State */}
      {status === "uploading" && (
        <Card className="glass-card p-12 flex flex-col items-center justify-center">
          <Loader2 className="animate-spin w-10 h-10 mb-4 text-primary" />
          <p className="text-lg font-medium">Running Detection Pipeline...</p>
          <p className="text-sm text-muted-foreground mt-1">{fileName}</p>
        </Card>
      )}

      {/* RESULTS VIEW */}
      {(status === "detected" || status === "clear") && previewUrl && (
        <div className="space-y-6">
          
          {/* Alert Banner */}
          {status === "detected" && (
            <div className="bg-destructive/10 border border-destructive/50 text-destructive px-4 py-3 rounded-lg flex items-center gap-3 animate-pulse">
              <AlertTriangle className="w-5 h-5" />
              <span className="font-semibold">Candidate Detected</span>
            </div>
          )}

          {/* Split View: Original vs Mask */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* LEFT: Original Image (The Uploaded File) */}
            <Card className="overflow-hidden border-border bg-card">
              <CardHeader className="pb-2 border-b border-border/50">
                <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                  <ImageIcon className="w-4 h-4" />
                  Original SAR Image
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 relative aspect-square bg-black/20">
                <img src={previewUrl} alt="Original SAR" className="w-full h-full object-contain" />
                <div className="absolute bottom-3 left-3 bg-black/60 backdrop-blur px-2 py-1 rounded text-xs font-mono text-white/80">
                  Uploaded File
                </div>
              </CardContent>
            </Card>

            {/* RIGHT: Segmentation Mask Overlay (cv_oil_binary.png) */}
            <Card className="overflow-hidden border-border bg-card">
              <CardHeader className="pb-2 border-b border-border/50">
                <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                  <MapPin className="w-4 h-4" />
                  Segmentation Mask Overlay
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 relative aspect-square bg-black">
                
                {/* THE MASK IMAGE (cv_oil_binary.png) - ONLY THE MASK */}
                {maskUrl ? (
                  <img 
                    src={maskUrl} 
                    alt="Detection Mask" 
                    className="w-full h-full object-contain" 
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm font-bold bg-black/50 p-4 text-center">
                    MASK NOT FOUND<br/>
                    <span className="text-xs font-normal text-white/70 mt-1">Check Console (F12) for details</span>
                  </div>
                )}

                {status === "detected" && maskUrl && (
                  <Badge variant="destructive" className="absolute bottom-3 right-3 font-mono">
                    MASK DETECTED
                  </Badge>
                )}
              </CardContent>
            </Card>
          </div>

          {/* METRICS BAR */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            
            {/* 1. Status */}
            <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
              {status === "detected" ? (
                <AlertTriangle className="w-5 h-5 text-destructive" />
              ) : (
                <CheckCircle className="w-5 h-5 text-green-500" />
              )}
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Status</p>
                <p className={`font-bold ${status === "detected" ? "text-destructive" : "text-green-500"}`}>
                  {status === "detected" ? "Candidate" : "Clear"}
                </p>
              </div>
            </div>

            {/* 2. CONFIDENCE */}
            <div className="bg-card border border-border rounded-lg p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Confidence</p>
              <p className="text-2xl font-bold text-primary font-mono">
                {((confidence || 0) * 100).toFixed(1)}%
              </p>
            </div>

            {/* 3. LOCATION */}
            <div className="col-span-2 bg-card border border-border rounded-lg p-4 flex items-center gap-3">
              <MapPin className="w-5 h-5 text-muted-foreground shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Location</p>
                <p className="font-mono text-sm text-foreground">
                  {Math.abs(location?.lat || 0).toFixed(4)}°{location?.lat >= 0 ? 'N' : 'S'}, {Math.abs(location?.lon || 0).toFixed(4)}°{location?.lon >= 0 ? 'E' : 'W'}
                </p>
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default SARUpload;