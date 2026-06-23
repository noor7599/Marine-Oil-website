import React, { useState, useRef } from 'react';
import { Upload, AlertTriangle, MapPin, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import SARUpload from '@/components/sar/SARUpload';
import SegmentationOverlay from '@/components/sar/SegmentationOverlay';
import DetectionMetrics from '@/components/sar/DetectionMetrics';

interface DetectionResult {
  maskUrl: string;
  f1Score: number;
  iou: number;
  latitude: number;
  longitude: number;
  confidence: number;
  isCandidate: boolean;
}

export default function SARDetection() {
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [detectionResult, setDetectionResult] = useState<DetectionResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageUpload = async (file: File) => {
    setIsProcessing(true);
    setError(null);
    
    try {
      // Create preview URL
      const previewUrl = URL.createObjectURL(file);
      setUploadedImage(previewUrl);

      // Send to backend for processing
      const formData = new FormData();
      formData.append('image', file);

      const response = await fetch('http://localhost:5000/api/sar/detect', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Detection failed');
      }

      const result = await response.json();
      setDetectionResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process image');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setUploadedImage(null);
    setDetectionResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-foreground">SAR Detection</h1>
          <p className="text-muted-foreground mt-1">
            Upload SAR imagery for oil spill detection and segmentation
          </p>
        </div>
        <Button variant="outline" onClick={handleReset}>
          Reset
        </Button>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Success Alert */}
      {detectionResult?.isCandidate && (
        <Alert className="bg-success/10 border-success text-success-foreground">
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>
            Oil spill candidate detected with {detectionResult.confidence}% confidence
          </AlertDescription>
        </Alert>
      )}

      {/* Upload Section */}
      {!uploadedImage && (
        <SARUpload 
          onUpload={handleImageUpload} 
          isProcessing={isProcessing}
          fileInputRef={fileInputRef}
        />
      )}

      {/* Detection Results */}
      {uploadedImage && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Original Image */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Original SAR Image
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative aspect-square bg-muted rounded-lg overflow-hidden">
                <img 
                  src={uploadedImage} 
                  alt="Original SAR" 
                  className="w-full h-full object-contain"
                />
                <div className="absolute bottom-2 left-2 bg-background/80 px-2 py-1 rounded text-xs">
                  Sentinel-1 IW GRD • 256×256 px
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Segmentation Overlay */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5" />
                Segmentation Mask Overlay
              </CardTitle>
            </CardHeader>
            <CardContent>
              <SegmentationOverlay 
                originalImage={uploadedImage}
                maskUrl={detectionResult?.maskUrl || null}
              />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Metrics */}
      {detectionResult && (
        <DetectionMetrics result={detectionResult} />
      )}
    </div>
  );
}