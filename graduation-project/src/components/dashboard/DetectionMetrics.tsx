import React from 'react';
import { AlertTriangle, MapPin } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface DetectionMetricsProps {
  result: {
    f1Score: number;
    iou: number;
    latitude: number;
    longitude: number;
    confidence: number;
    isCandidate: boolean;
  };
}

export default function DetectionMetrics({ result }: DetectionMetricsProps) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Candidate Alert */}
          <div className="flex items-center gap-2">
            {result.isCandidate && (
              <Badge variant="destructive" className="animate-pulse">
                <AlertTriangle className="h-3 w-3 mr-1" />
                Candidate Detected
              </Badge>
            )}
          </div>

          {/* F1 Score */}
          <div className="bg-muted rounded-lg p-3">
            <div className="text-xs text-muted-foreground mb-1">F1-score</div>
            <div className="text-2xl font-bold text-success">
              {(result.f1Score * 100).toFixed(0)}%
            </div>
          </div>

          {/* IoU */}
          <div className="bg-muted rounded-lg p-3">
            <div className="text-xs text-muted-foreground mb-1">IoU</div>
            <div className="text-2xl font-bold text-primary">
              {result.iou.toFixed(2)}
            </div>
          </div>

          {/* Coordinates */}
          <div className="flex items-center gap-2 bg-muted rounded-lg p-3">
            <MapPin className="h-4 w-4 text-muted-foreground" />
            <div>
              <div className="text-xs text-muted-foreground">Location</div>
              <div className="text-sm font-mono">
                {result.latitude.toFixed(3)}°N, {result.longitude.toFixed(3)}°W
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}