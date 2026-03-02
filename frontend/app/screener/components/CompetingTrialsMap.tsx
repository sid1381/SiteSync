'use client';
import React, { useEffect, useState, useMemo } from 'react';

// Country center coordinates for initial map view
const COUNTRY_CENTERS: Record<string, { lat: number; lng: number; zoom: number }> = {
  US: { lat: 39.8, lng: -98.5, zoom: 4 },
  CA: { lat: 56.1, lng: -106.3, zoom: 3 },
  GB: { lat: 55.3, lng: -3.4, zoom: 5 },
  DE: { lat: 51.2, lng: 10.4, zoom: 6 },
  FR: { lat: 46.2, lng: 2.2, zoom: 5 },
  IT: { lat: 41.9, lng: 12.6, zoom: 5 },
  ES: { lat: 40.5, lng: -3.7, zoom: 5 },
  PL: { lat: 51.9, lng: 19.1, zoom: 6 },
  AU: { lat: -25.3, lng: 133.8, zoom: 4 },
  JP: { lat: 36.2, lng: 138.3, zoom: 5 },
  KR: { lat: 35.9, lng: 127.8, zoom: 7 },
  CN: { lat: 35.9, lng: 104.2, zoom: 4 },
  IN: { lat: 20.6, lng: 78.9, zoom: 4 },
  BR: { lat: -14.2, lng: -51.9, zoom: 4 },
  MX: { lat: 23.6, lng: -102.6, zoom: 5 },
  NL: { lat: 52.1, lng: 5.3, zoom: 7 },
  BE: { lat: 50.5, lng: 4.5, zoom: 7 },
  SE: { lat: 60.1, lng: 18.6, zoom: 4 },
  DK: { lat: 56.3, lng: 9.5, zoom: 6 },
  AT: { lat: 47.5, lng: 14.6, zoom: 6 },
  CZ: { lat: 49.8, lng: 15.5, zoom: 7 },
  HU: { lat: 47.2, lng: 19.5, zoom: 7 },
  RO: { lat: 45.9, lng: 25.0, zoom: 6 },
  ZA: { lat: -30.6, lng: 22.9, zoom: 5 },
  TR: { lat: 39.0, lng: 35.2, zoom: 5 },
  IL: { lat: 31.0, lng: 34.9, zoom: 7 },
  TH: { lat: 15.9, lng: 100.9, zoom: 5 },
  RU: { lat: 61.5, lng: 105.3, zoom: 3 },
  AR: { lat: -38.4, lng: -63.6, zoom: 4 },
  NZ: { lat: -40.9, lng: 174.9, zoom: 5 },
};

const DEFAULT_CENTER = { lat: 20, lng: 0, zoom: 2 };

// Marker type for the map
interface MapMarker {
  lat: number;
  lng: number;
  label: string;
  nct_id: string;
  enrollment: number;
}

// Lazy-loaded Leaflet map component that imports react-leaflet at runtime
function LeafletMap({
  center,
  zoom,
  markers
}: {
  center: [number, number];
  zoom: number;
  markers: MapMarker[];
}) {
  const [components, setComponents] = useState<{
    MapContainer: React.ComponentType<any>;
    TileLayer: React.ComponentType<any>;
    CircleMarker: React.ComponentType<any>;
    Popup: React.ComponentType<any>;
    Tooltip: React.ComponentType<any>;
  } | null>(null);

  useEffect(() => {
    // Import everything client-side only
    Promise.all([
      import('react-leaflet'),
    ]).then(([rl]) => {
      // Load CSS via link tag (more reliable than CSS import in Turbopack)
      const existingLink = document.querySelector('link[href*="leaflet.css"]');
      if (!existingLink) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        link.crossOrigin = '';
        document.head.appendChild(link);
      }

      setComponents({
        MapContainer: rl.MapContainer,
        TileLayer: rl.TileLayer,
        CircleMarker: rl.CircleMarker,
        Popup: rl.Popup,
        Tooltip: rl.Tooltip,
      });
    }).catch((err) => {
      console.error('Failed to load Leaflet:', err);
      // Retry with alternate approach
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
      import('react-leaflet').then((rl) => {
        setComponents({
          MapContainer: rl.MapContainer,
          TileLayer: rl.TileLayer,
          CircleMarker: rl.CircleMarker,
          Popup: rl.Popup,
          Tooltip: rl.Tooltip,
        });
      });
    });
  }, []);

  if (!components) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-50">
        <span className="text-xs text-slate-400">Loading map...</span>
      </div>
    );
  }

  const { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } = components;

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ height: '100%', width: '100%' }}
      scrollWheelZoom={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org">OSM</a> &copy; <a href="https://carto.com">CARTO</a>'
      />
      {markers.map((site, idx) => (
        <CircleMarker
          key={`site-${idx}`}
          center={[site.lat, site.lng]}
          radius={6}
          pathOptions={{
            fillColor: '#ef4444',
            fillOpacity: 0.7,
            color: '#ffffff',
            weight: 1.5,
          }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <div style={{ fontSize: '11px' }}>
              <div style={{ fontWeight: 600 }}>{site.nct_id}</div>
              {site.enrollment > 0 && <div>Target: {site.enrollment}</div>}
            </div>
          </Tooltip>
          <Popup>
            <div style={{ fontSize: '12px' }}>
              <div style={{ fontWeight: 600 }}>{site.nct_id}</div>
              {site.label && <div style={{ color: '#64748b', marginTop: 2 }}>{site.label}</div>}
              {site.enrollment > 0 && <div style={{ marginTop: 2 }}>Enrollment: <strong>{site.enrollment}</strong></div>}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

interface TrialSite {
  nct_id: string;
  facility_name?: string;
  city?: string;
  state?: string;
  lat?: number;
  lng?: number;
  enrollment?: number;
  status?: string;
}

interface CompetingTrialsMapProps {
  countryCode: string;
  countryName: string;
  competingTrialDetails?: Array<{
    nct_id: string;
    enrollment?: number;
    sites_in_country?: number;
    sites_total?: number;
  }>;
  trialSites?: TrialSite[];
  activelyRecruiting?: number;
  competitionDemand?: number;
  competitionPressure?: string;
  compact?: boolean;
}

export default function CompetingTrialsMap({
  countryCode,
  countryName,
  competingTrialDetails = [],
  trialSites = [],
  activelyRecruiting = 0,
  competitionDemand = 0,
  competitionPressure = 'unknown',
  compact = false,
}: CompetingTrialsMapProps) {
  const center = COUNTRY_CENTERS[countryCode] || DEFAULT_CENTER;

  // Generate map markers from trial data
  const siteMarkers = useMemo((): MapMarker[] => {
    if (trialSites.length > 0) {
      return trialSites
        .filter((s): s is TrialSite & { lat: number; lng: number } => s.lat !== undefined && s.lng !== undefined)
        .map(s => ({
          lat: s.lat,
          lng: s.lng,
          label: s.facility_name || s.city || '',
          nct_id: s.nct_id,
          enrollment: s.enrollment || 0,
        }));
    }

    // Generate distributed points from competing trial details
    // This is a placeholder until we add real geocoding
    const markers: MapMarker[] = [];

    const countryCenter = COUNTRY_CENTERS[countryCode] || DEFAULT_CENTER;
    const spread = countryCode === 'US' ? 12 : countryCode === 'AU' ? 10 : 5;

    competingTrialDetails.forEach((trial, i) => {
      const sitesInCountry = trial.sites_in_country || 1;
      for (let j = 0; j < Math.min(sitesInCountry, 8); j++) {
        // Distribute sites with some randomness based on index
        const angle = ((i * 137.508 + j * 45) % 360) * (Math.PI / 180);
        const dist = (0.3 + ((i * 7 + j * 13) % 10) / 10) * spread;
        markers.push({
          lat: countryCenter.lat + Math.sin(angle) * dist * 0.5,
          lng: countryCenter.lng + Math.cos(angle) * dist,
          label: `${trial.nct_id} (Site ${j + 1})`,
          nct_id: trial.nct_id,
          enrollment: trial.enrollment || 0,
        });
      }
    });

    return markers;
  }, [competingTrialDetails, trialSites, countryCode]);

  // Pressure badge color
  const pressureColor =
    competitionPressure === 'low' ? 'bg-green-100 text-green-700' :
    competitionPressure === 'moderate' ? 'bg-yellow-100 text-yellow-700' :
    competitionPressure === 'high' ? 'bg-orange-100 text-orange-700' :
    competitionPressure === 'extreme' ? 'bg-red-100 text-red-700' :
    'bg-slate-100 text-slate-700';

  // Compact mode: just the map, no header or trial list
  if (compact) {
    return (
      <div style={{ height: '100%', width: '100%' }}>
        <LeafletMap
          center={[center.lat, center.lng]}
          zoom={center.zoom}
          markers={siteMarkers}
        />
      </div>
    );
  }

  // Full mode: with header and trial list
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      {/* Map header */}
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            Competing Trial Landscape
          </h3>
          <p className="text-sm text-slate-500 mt-0.5">
            {activelyRecruiting} recruiting trials · ~{competitionDemand?.toLocaleString()} patient demand
          </p>
        </div>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${pressureColor}`}>
          {competitionPressure} pressure
        </span>
      </div>

      {/* Map */}
      <div style={{ height: '420px', width: '100%' }}>
        <LeafletMap
          center={[center.lat, center.lng]}
          zoom={center.zoom}
          markers={siteMarkers}
        />
      </div>

      {/* Trial list below map */}
      {competingTrialDetails.length > 0 && (
        <div className="px-5 py-4 border-t border-slate-100">
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Competing Trials ({competingTrialDetails.length})
          </h4>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {competingTrialDetails.map((trial, i) => (
              <div key={i} className="flex items-center justify-between text-sm py-1.5 border-b border-slate-50 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-400"></span>
                  <a
                    href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline font-mono text-xs"
                  >
                    {trial.nct_id}
                  </a>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span>{trial.sites_in_country || '?'} sites in {countryName}</span>
                  <span>{trial.sites_total || '?'} sites total</span>
                  <span className="font-medium text-slate-700">
                    {trial.enrollment ? `${trial.enrollment} target` : 'No enrollment data'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data source note */}
      <div className="px-5 py-3 bg-slate-50 border-t border-slate-100 text-xs text-slate-400">
        Data: ClinicalTrials.gov · Site locations are approximate (city-level geocoding planned)
      </div>
    </div>
  );
}
