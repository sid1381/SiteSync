'use client';

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import {
  ArrowLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Search,
  Upload,
  Building2,
  Star,
  StarOff,
  MapPin,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  SlidersHorizontal,
  X,
  CheckCircle,
  Shield,
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface SiteScore {
  site_id: string;
  site_name: string;
  city: string;
  state?: string;
  country: string;
  country_code: string;
  final_score: number;
  site_composite_score: number;
  country_composite_score: number;
  experience_score: number;
  pi_strength_score: number;
  capacity_score: number;
  compliance_score: number;
  protocol_match_score: number;
  trial_count: number;
  indication_trial_count: number;
  completion_rate: number;
  competing_trial_count: number;
  investigators: Array<{
    name: string;
    role?: string;
    specialty?: string;
    trial_count?: number;
    publications?: number;
    primary_role?: string;
  }>;
  red_flags: string[];
  yellow_flags: string[];
  strengths: string[];
  gap_analysis?: string;
  is_shortlisted: boolean;
  // Citeline enrichment
  citeline_enriched?: boolean;
  citeline_match_type?: string;
  citeline_tier?: string;
  citeline_pi_discovery?: Record<string, unknown>;
  citeline_enrichment?: Record<string, unknown>;
  // PubMed enrichment
  pubmed_data?: Record<string, unknown>;
  pubmed_enriched?: boolean;
  // FDA enrichment
  fda_data?: Record<string, unknown>;
  fda_enriched?: boolean;
  // Data sources
  data_sources?: string[];
  // Data confidence tier
  data_confidence?: string;  // "high", "medium", "low"
  data_sources_checked?: string[];  // e.g. ["ctgov", "citeline", "pubmed", "compliance"]
  data_source_count?: number;  // Number of sources with data
  // Percentile rankings
  percentile?: number;  // 0-100, percentile rank within country
  calibration_band?: string;  // "Strong", "Viable", "Watchlist", "DNR"
  dimension_percentiles?: Record<string, number>;  // percentile for each dimension
}

interface CountryScore {
  country_name: string;
  country_code: string;
  composite_score: number;
  // ... other fields not needed for this view
}

interface Project {
  id: number;
  name: string;
  indication?: string;
  phase?: string;
  // ... other fields not needed
}

interface SiteWeights {
  experience: number;
  pi_strength: number;
  capacity: number;
  compliance: number;
  protocol_match: number;
}

interface CountryBenchmarks {
  enrollment_benchmarks?: {
    median_pts_site_month?: number;
    median_enrollment_duration_months?: number;
    median_target_accrual?: number;
    pts_site_month_by_phase?: Record<string, number>;
    enrollment_duration_by_phase?: Record<string, number>;
  };
  competition_summary?: {
    active_trials?: number;
    total_trials?: number;
    by_phase?: Record<string, number>;
    by_status?: Record<string, number>;
  };
}

interface SiteRankingViewProps {
  project: Project;
  country: CountryScore;
  sites: SiteScore[];
  shortlist: SiteScore[];
  weights: SiteWeights;
  scoringPreset: string;
  loading: boolean;
  error: string | null;
  countryBenchmarks?: CountryBenchmarks;
  onWeightsChange: (weights: SiteWeights) => void;
  onPresetChange: (preset: string) => void;
  onRefresh: () => void;
  onSelectSite: (site: SiteScore) => void;
  onToggleShortlist: (site: SiteScore) => void;
  onBack: () => void;
  onRetry: () => void;
  onViewProtocol: () => void;
  onBackToProjects: () => void;
}

// Preset weight configurations
const PRESET_WEIGHTS: Record<string, SiteWeights> = {
  phase_1: { experience: 0.25, pi_strength: 0.25, capacity: 0.20, compliance: 0.20, protocol_match: 0.10 },
  phase_2: { experience: 0.30, pi_strength: 0.25, capacity: 0.20, compliance: 0.15, protocol_match: 0.10 },
  phase_3: { experience: 0.35, pi_strength: 0.20, capacity: 0.20, compliance: 0.15, protocol_match: 0.10 },
};

const PRESET_OPTIONS = [
  { value: 'phase_1', label: 'Phase I' },
  { value: 'phase_2', label: 'Phase II' },
  { value: 'phase_3', label: 'Phase III' },
  { value: 'custom', label: 'Custom' },
];

// =============================================================================
// HELPERS
// =============================================================================

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-amber-600';
  return 'text-red-600';
}

function getScoreBadgeStyle(score: number): string {
  if (score >= 80) return 'bg-green-50 text-green-700 border-green-200';
  if (score >= 60) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-red-50 text-red-700 border-red-200';
}

// =============================================================================
// SORTABLE HEADER
// =============================================================================

function SortableHeader({
  label,
  sortKey,
  currentSort,
  onSort,
  className = '',
}: {
  label: string;
  sortKey: string;
  currentSort: { key: string; direction: 'asc' | 'desc' };
  onSort: (key: string) => void;
  className?: string;
}) {
  const isActive = currentSort.key === sortKey;
  return (
    <th
      className={`text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-3 cursor-pointer hover:text-slate-600 transition-colors ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="flex items-center gap-1">
        {label}
        {isActive ? (
          currentSort.direction === 'desc' ? (
            <ChevronDown className="w-3.5 h-3.5" strokeWidth={2} />
          ) : (
            <ChevronUp className="w-3.5 h-3.5" strokeWidth={2} />
          )
        ) : null}
      </span>
    </th>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function SiteRankingView({
  project,
  country,
  sites,
  shortlist,
  weights,
  scoringPreset,
  loading,
  error,
  countryBenchmarks,
  onWeightsChange,
  onPresetChange,
  onRefresh,
  onSelectSite,
  onToggleShortlist,
  onBack,
  onRetry,
  onViewProtocol,
  onBackToProjects,
}: SiteRankingViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' }>({
    key: 'final_score',
    direction: 'desc',
  });
  const [showShortlist, setShowShortlist] = useState(false);
  const [showWeights, setShowWeights] = useState(false);
  const [localWeights, setLocalWeights] = useState(weights);
  const [localPreset, setLocalPreset] = useState(scoringPreset);

  // Sync local state with parent props when they change
  useEffect(() => {
    setLocalWeights(weights);
  }, [weights]);

  useEffect(() => {
    setLocalPreset(scoringPreset);
  }, [scoringPreset]);

  // Citeline SiteTrove upload state
  const [citelineResult, setCitelineResult] = useState<any>(null);
  const [citelineLoading, setCitelineLoading] = useState(false);
  const [citelineError, setCitelineError] = useState<string | null>(null);
  const [showMatchDetails, setShowMatchDetails] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Compliance check state
  const [complianceResult, setComplianceResult] = useState<any>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // SiteTrove upload handler
  const handleCitelineUpload = async (file: File) => {
    setCitelineLoading(true);
    setCitelineError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(
        `${API_URL}/screener/projects/${project.id}/upload-citeline?country_code=${country.country_code}`,
        { method: 'POST', body: formData }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const result = await res.json();
      setCitelineResult(result);
    } catch (e: any) {
      setCitelineError(e.message);
    } finally {
      setCitelineLoading(false);
    }
  };

  // Apply Citeline enrichment (SiteTrove)
  const handleApplyCiteline = async () => {
    if (!citelineResult?.match_details) return;

    try {
      const res = await fetch(
        `${API_URL}/screener/projects/${project.id}/apply-citeline?country_code=${country.country_code}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(citelineResult.match_details),
        }
      );
      if (!res.ok) throw new Error('Failed to apply enrichment');
      // Refresh sites data after enrichment
      onRefresh();
      setCitelineResult(null);
    } catch (e: any) {
      setCitelineError(e.message);
    }
  };

  // Run compliance checks (NPI resolution, OIG LEIE, FDA inspections)
  const handleRunComplianceChecks = async () => {
    setComplianceLoading(true);
    setComplianceError(null);
    setComplianceResult(null);

    try {
      const res = await fetch(
        `${API_URL}/screener/projects/${project.id}/compliance/run-all?country_code=${country.country_code}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' } }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Compliance check failed');
      }

      const result = await res.json();
      setComplianceResult(result);
      // Refresh sites data after compliance check
      onRefresh();
    } catch (e: any) {
      setComplianceError(e.message);
    } finally {
      setComplianceLoading(false);
    }
  };

  // Filtering and sorting
  const filteredSites = useMemo(() => {
    return sites.filter((s) => {
      if (s.final_score < minScore) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const nameMatch = s.site_name.toLowerCase().includes(q);
        const piMatch = s.investigators[0]?.name?.toLowerCase().includes(q);
        if (!nameMatch && !piMatch) return false;
      }
      return true;
    });
  }, [sites, minScore, searchQuery]);

  const sortedSites = useMemo(() => {
    return [...filteredSites].sort((a, b) => {
      const aVal = (a as any)[sortConfig.key];
      const bVal = (b as any)[sortConfig.key];
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortConfig.direction === 'desc' ? bVal - aVal : aVal - bVal;
      }
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortConfig.direction === 'desc'
          ? bVal.localeCompare(aVal)
          : aVal.localeCompare(bVal);
      }
      return 0;
    });
  }, [filteredSites, sortConfig]);

  const handleSort = useCallback((key: string) => {
    setSortConfig((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  }, []);

  const shortlistSet = useMemo(() => new Set(shortlist.map((s) => s.site_id)), [shortlist]);

  // Track excluded sites from compliance check results
  const excludedSiteIds = useMemo(() => {
    if (!complianceResult?.oig_check?.excluded_sites) return new Set<string>();
    return new Set(complianceResult.oig_check.excluded_sites.map((ex: any) => ex.site_id));
  }, [complianceResult]);

  // Summary stats
  const avgScore =
    filteredSites.length > 0
      ? Math.round(filteredSites.reduce((sum, s) => sum + s.final_score, 0) / filteredSites.length)
      : 0;
  const totalTrials = filteredSites.reduce((sum, s) => sum + s.trial_count, 0);
  const totalIndicationTrials = filteredSites.reduce((sum, s) => sum + s.indication_trial_count, 0);

  const handleWeightChange = (key: keyof SiteWeights, value: number) => {
    setLocalWeights((prev) => ({ ...prev, [key]: value }));
    // Auto-switch to "Custom" when manually adjusting sliders
    setLocalPreset('custom');
  };

  const handlePresetSelect = (preset: string) => {
    setLocalPreset(preset);
    if (preset !== 'custom' && PRESET_WEIGHTS[preset]) {
      setLocalWeights(PRESET_WEIGHTS[preset]);
    }
  };

  const handleApplyWeights = () => {
    onPresetChange(localPreset);
    if (localPreset !== 'custom') {
      // Use preset weights
      onWeightsChange(PRESET_WEIGHTS[localPreset] || localWeights);
    } else {
      onWeightsChange(localWeights);
    }
    setShowWeights(false);
  };

  // Loading state
  if (loading && sites.length === 0) {
    return (
      <div className="max-w-6xl mx-auto px-4">
        <nav className="flex items-center gap-1.5 text-xs text-slate-400 mb-8">
          <button onClick={onBackToProjects} className="hover:text-slate-600 transition-colors">
            Projects
          </button>
          <ChevronRight className="w-3 h-3" />
          <button onClick={onViewProtocol} className="hover:text-slate-600 transition-colors">
            {project.name}
          </button>
          <ChevronRight className="w-3 h-3" />
          <button onClick={onBack} className="hover:text-slate-600 transition-colors">
            Countries
          </button>
          <ChevronRight className="w-3 h-3" />
          <span className="text-slate-700 font-medium">Sites in {country.country_name}</span>
        </nav>
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-500">Loading sites...</p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4">
        <nav className="flex items-center gap-1.5 text-xs text-slate-400 mb-8">
          <button onClick={onBackToProjects} className="hover:text-slate-600 transition-colors">
            Projects
          </button>
          <ChevronRight className="w-3 h-3" />
          <button onClick={onViewProtocol} className="hover:text-slate-600 transition-colors">
            {project.name}
          </button>
          <ChevronRight className="w-3 h-3" />
          <button onClick={onBack} className="hover:text-slate-600 transition-colors">
            Countries
          </button>
          <ChevronRight className="w-3 h-3" />
          <span className="text-slate-700 font-medium">Sites in {country.country_name}</span>
        </nav>
        <div className="border border-red-200 rounded-lg p-8 bg-red-50/50 text-center">
          <XCircle className="w-8 h-8 text-red-500 mx-auto mb-3" strokeWidth={1.5} />
          <p className="text-sm text-red-700 mb-4">{error}</p>
          <button
            onClick={onRetry}
            className="text-sm text-red-600 font-medium hover:text-red-700 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-slate-400 mb-8">
        <button onClick={onBackToProjects} className="hover:text-slate-600 transition-colors">
          Projects
        </button>
        <ChevronRight className="w-3 h-3" />
        <button onClick={onViewProtocol} className="hover:text-slate-600 transition-colors">
          {project.name}
        </button>
        <ChevronRight className="w-3 h-3" />
        <button onClick={onBack} className="hover:text-slate-600 transition-colors">
          Countries
        </button>
        <ChevronRight className="w-3 h-3" />
        <span className="text-slate-700 font-medium">Sites in {country.country_name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Sites in {country.country_name}</h1>
          <p className="text-sm text-slate-500">
            {sites.length} sites · Country score:{' '}
            <span className={getScoreColor(country.composite_score)}>
              {Math.round(country.composite_score)}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowShortlist(!showShortlist)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              showShortlist
                ? 'bg-amber-100 text-amber-700 border border-amber-200'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Star className="w-4 h-4" strokeWidth={1.5} />
            Shortlist ({shortlist.length})
          </button>
          <button
            onClick={() => setShowWeights(!showWeights)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <SlidersHorizontal className="w-4 h-4" strokeWidth={1.5} />
            Weights
          </button>
        </div>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Total Sites', value: filteredSites.length, suffix: '' },
          { label: 'Avg Score', value: avgScore, suffix: '' },
          { label: 'Total Trials', value: totalTrials, suffix: '' },
          { label: 'Indication Trials', value: totalIndicationTrials, suffix: '' },
        ].map((m, i) => (
          <div key={i} className="border border-slate-200 rounded-lg p-4 bg-white">
            <div className="text-2xl font-bold text-slate-900 tabular-nums">{m.value.toLocaleString()}{m.suffix}</div>
            <div className="text-xs text-slate-400 mt-1">{m.label}</div>
          </div>
        ))}
      </div>

      {/* Citeline SiteTrove Enrichment Section */}
      <div className="mb-6">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleCitelineUpload(f);
          }}
        />

        <div className="border border-slate-200 rounded-lg bg-white overflow-hidden">
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                <Upload className="w-4 h-4 text-amber-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-700">Enrich with Citeline SiteTrove</p>
                <p className="text-xs text-slate-400">Upload PI profiles, regulatory history, and enrollment metrics</p>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="p-5">
            {!citelineResult ? (
              <div>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={citelineLoading}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 border border-slate-300 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
                >
                  {citelineLoading ? (
                    <span className="flex items-center gap-2">
                      <div className="w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                      Processing...
                    </span>
                  ) : 'Upload .xlsx'}
                </button>
                {citelineError && (
                  <p className="mt-2 text-xs text-red-600">{citelineError}</p>
                )}
              </div>
            ) : (
              /* SiteTrove Results */
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
                      <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700">
                        SiteTrove — {citelineResult.file_name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {citelineResult.matched} of {citelineResult.total_records} records matched
                        {citelineResult.new_pis > 0 && ` · ${citelineResult.new_pis} new PIs discovered`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowMatchDetails(!showMatchDetails)}
                      className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 border border-slate-200 rounded-md hover:bg-slate-50"
                    >
                      {showMatchDetails ? 'Hide' : 'Show'} Details
                    </button>
                    <button
                      onClick={handleApplyCiteline}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-slate-800 rounded-md hover:bg-slate-700"
                    >
                      Apply Enrichment
                    </button>
                    <button
                      onClick={() => { setCitelineResult(null); setCitelineError(null); }}
                      className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>

                {/* Enrichment stats */}
                {citelineResult.enrichment_summary && (
                  <div className="flex gap-4 mb-3">
                    {Object.entries(citelineResult.enrichment_summary).map(([key, value]) => (
                      <div key={key} className="text-xs">
                        <span className="text-slate-400">{key.replace(/_/g, ' ')}: </span>
                        <span className="text-slate-700 font-medium">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Match details table */}
                {showMatchDetails && citelineResult.match_details && (
                  <div className="max-h-48 overflow-y-auto border border-slate-100 rounded-lg">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-slate-500 font-medium">Citeline PI</th>
                          <th className="px-3 py-2 text-left text-slate-500 font-medium">Matched Site</th>
                          <th className="px-3 py-2 text-left text-slate-500 font-medium">Confidence</th>
                          <th className="px-3 py-2 text-left text-slate-500 font-medium">Method</th>
                          <th className="px-3 py-2 text-left text-slate-500 font-medium">Tier</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {citelineResult.match_details.map((m: any, i: number) => (
                          <tr key={i} className={m.matched ? '' : 'opacity-50'}>
                            <td className="px-3 py-2">
                              <div className="text-slate-700">{m.citeline_pi}</div>
                              <div className="text-slate-400">{m.citeline_org}</div>
                            </td>
                            <td className="px-3 py-2 text-slate-600">
                              {m.matched_site_name || '—'}
                            </td>
                            <td className="px-3 py-2">
                              <span className={`inline-flex px-1.5 py-0.5 rounded text-xs font-medium ${
                                m.confidence >= 85 ? 'bg-green-50 text-green-700' :
                                m.confidence >= 70 ? 'bg-amber-50 text-amber-700' :
                                'bg-red-50 text-red-700'
                              }`}>
                                {m.confidence}%
                              </span>
                            </td>
                            <td className="px-3 py-2 text-slate-500">{m.match_method?.replace(/_/g, ' ')}</td>
                            <td className="px-3 py-2">
                              {m.enrichment?.tier && (
                                <span className={`inline-flex px-1.5 py-0.5 rounded text-xs font-medium ${
                                  m.enrichment.tier === 'Gold' ? 'bg-amber-50 text-amber-700' :
                                  m.enrichment.tier === 'Silver' ? 'bg-slate-100 text-slate-600' :
                                  'bg-orange-50 text-orange-700'
                                }`}>
                                  {m.enrichment.tier}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Compliance Check Section */}
      <div className="mb-6">
        <div className="border border-slate-200 rounded-lg bg-white overflow-hidden">
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                <Shield className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-700">Compliance Checks</p>
                <p className="text-xs text-slate-400">NPI resolution, OIG LEIE exclusions, FDA inspections</p>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="p-5">
            {!complianceResult ? (
              <div>
                <button
                  onClick={handleRunComplianceChecks}
                  disabled={complianceLoading}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 border border-slate-300 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
                >
                  {complianceLoading ? (
                    <span className="flex items-center gap-2">
                      <div className="w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                      Running checks...
                    </span>
                  ) : 'Run Compliance Checks'}
                </button>
                {complianceError && (
                  <p className="mt-2 text-xs text-red-600">{complianceError}</p>
                )}
              </div>
            ) : (
              /* Compliance Results */
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
                      <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700">
                        Compliance checks complete
                      </p>
                      <p className="text-xs text-slate-500">
                        {complianceResult.total_sites} sites checked
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => { setComplianceResult(null); setComplianceError(null); }}
                    className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700"
                  >
                    Dismiss
                  </button>
                </div>

                {/* Results grid */}
                <div className="grid grid-cols-3 gap-4 mt-4">
                  {/* NPI Resolution */}
                  {complianceResult.npi_resolution && (
                    <div className="p-3 bg-slate-50 rounded-lg">
                      <p className="text-xs text-slate-400 mb-1">NPI Resolution</p>
                      <p className="text-lg font-semibold text-slate-900">
                        {complianceResult.npi_resolution.npi_from_citeline + complianceResult.npi_resolution.npi_from_nppes}
                      </p>
                      <p className="text-xs text-slate-500">
                        {complianceResult.npi_resolution.npi_from_citeline} Citeline · {complianceResult.npi_resolution.npi_from_nppes} NPPES
                      </p>
                    </div>
                  )}

                  {/* OIG Check */}
                  {complianceResult.oig_check && (
                    <div className={`p-3 rounded-lg ${complianceResult.oig_check.exclusions_found > 0 ? 'bg-red-50' : 'bg-slate-50'}`}>
                      <p className="text-xs text-slate-400 mb-1">OIG LEIE</p>
                      {complianceResult.oig_check.exclusions_found > 0 ? (
                        <>
                          <p className="text-lg font-semibold text-red-600">
                            {complianceResult.oig_check.exclusions_found} Excluded
                          </p>
                          <p className="text-xs text-red-500">
                            {complianceResult.oig_check.clean} clean · {complianceResult.oig_check.reinstated} reinstated
                          </p>
                          {/* Show excluded site names */}
                          {complianceResult.oig_check.excluded_sites && complianceResult.oig_check.excluded_sites.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-red-200">
                              <p className="text-xs text-red-600 font-medium mb-1">Excluded PIs:</p>
                              <div className="space-y-1">
                                {complianceResult.oig_check.excluded_sites.map((ex: any, idx: number) => (
                                  <button
                                    key={idx}
                                    onClick={() => {
                                      const site = sites.find(s => s.site_id === ex.site_id);
                                      if (site) onSelectSite(site);
                                    }}
                                    className="block w-full text-left text-xs text-red-700 hover:text-red-900 hover:underline"
                                  >
                                    • {ex.pi_name} ({ex.site_name})
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <>
                          <p className="text-lg font-semibold text-green-600">
                            {complianceResult.oig_check.clean} Clear
                          </p>
                          <p className="text-xs text-slate-500">
                            {complianceResult.oig_check.total_checked} PIs checked
                          </p>
                        </>
                      )}
                    </div>
                  )}

                  {/* FDA Inspections */}
                  {complianceResult.fda_inspections && (
                    <div className={`p-3 rounded-lg ${complianceResult.fda_inspections.oai_found > 0 ? 'bg-amber-50' : 'bg-slate-50'}`}>
                      <p className="text-xs text-slate-400 mb-1">FDA Inspections</p>
                      <p className="text-lg font-semibold text-slate-900">
                        {complianceResult.fda_inspections.sites_with_inspections}
                      </p>
                      <p className="text-xs text-slate-500">
                        sites with records
                        {complianceResult.fda_inspections.oai_found > 0 && (
                          <span className="text-amber-600"> · {complianceResult.fda_inspections.oai_found} OAI</span>
                        )}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Search + filter row */}
      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
            strokeWidth={1.5}
          />
          <input
            type="text"
            placeholder="Search sites or investigators..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Min score:</span>
          <input
            type="range"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-24"
          />
          <span className="tabular-nums w-6">{minScore}</span>
        </div>
      </div>

      {/* Weights panel */}
      {showWeights && (
        <div className="border border-slate-200 rounded-lg p-5 mb-6 bg-white">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-900">Scoring Weights</h3>
            <button onClick={() => setShowWeights(false)} className="text-slate-400 hover:text-slate-600">
              <X className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>

          {/* Preset dropdown */}
          <div className="mb-4">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
              Scoring Profile
            </label>
            <select
              value={localPreset}
              onChange={(e) => handlePresetSelect(e.target.value)}
              className="w-full max-w-xs px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {PRESET_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-400 mt-1">
              {localPreset === 'custom'
                ? 'Manually adjust sliders below'
                : `Optimized for ${PRESET_OPTIONS.find((o) => o.value === localPreset)?.label} trials`}
            </p>
          </div>

          <div className="grid grid-cols-5 gap-4 mb-4">
            {Object.entries(localWeights).map(([key, value]) => (
              <div key={key}>
                <label className="text-xs text-slate-500 capitalize">{key.replace('_', ' ')}</label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={value * 100}
                  onChange={(e) => handleWeightChange(key as keyof SiteWeights, Number(e.target.value) / 100)}
                  className="w-full mt-1"
                />
                <div className="text-xs text-slate-600 tabular-nums">{Math.round(value * 100)}%</div>
              </div>
            ))}
          </div>
          <button
            onClick={handleApplyWeights}
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Apply & Refresh
          </button>
        </div>
      )}

      {/* Country Benchmarks Bar */}
      {countryBenchmarks && (countryBenchmarks.competition_summary || countryBenchmarks.enrollment_benchmarks) && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 mb-4">
          <div className="flex items-center gap-1 mb-2">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Country Benchmarks
            </span>
            <span className="text-[10px] text-slate-400">({country.country_name})</span>
          </div>
          <div className="grid grid-cols-3 gap-6">
            {countryBenchmarks.competition_summary?.active_trials !== undefined && (
              <div>
                <div className="text-lg font-semibold text-slate-800 tabular-nums">
                  {countryBenchmarks.competition_summary.active_trials}
                </div>
                <div className="text-xs text-slate-500">Active Competing Trials</div>
              </div>
            )}
            {countryBenchmarks.enrollment_benchmarks?.median_pts_site_month !== undefined && (
              <div>
                <div className="text-lg font-semibold text-slate-800 tabular-nums">
                  {countryBenchmarks.enrollment_benchmarks.median_pts_site_month.toFixed(2)} pts/site/mo
                </div>
                <div className="text-xs text-slate-500">Median Enrollment Rate</div>
              </div>
            )}
            {countryBenchmarks.enrollment_benchmarks?.median_enrollment_duration_months !== undefined && (
              <div>
                <div className="text-lg font-semibold text-slate-800 tabular-nums">
                  {countryBenchmarks.enrollment_benchmarks.median_enrollment_duration_months.toFixed(1)} months
                </div>
                <div className="text-xs text-slate-500">Median Enrollment Duration</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      {sortedSites.length === 0 ? (
        <div className="border border-slate-200 rounded-lg p-12 text-center bg-white">
          <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-3" strokeWidth={1.5} />
          <p className="text-sm text-slate-500">
            {searchQuery ? 'No sites match your search criteria' : 'No sites found for this country'}
          </p>
        </div>
      ) : (
        <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-3 w-12">
                  #
                </th>
                <SortableHeader label="Site" sortKey="site_name" currentSort={sortConfig} onSort={handleSort} />
                <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">
                  PI
                </th>
                <SortableHeader label="Score" sortKey="final_score" currentSort={sortConfig} onSort={handleSort} className="w-20" />
                <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-3 w-16">
                  Data
                </th>
                <SortableHeader label="Trials" sortKey="trial_count" currentSort={sortConfig} onSort={handleSort} className="w-16" />
                <SortableHeader label="Indication" sortKey="indication_trial_count" currentSort={sortConfig} onSort={handleSort} className="w-20" />
                <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-3 w-28">
                  Competing
                </th>
                <th className="w-12" />
              </tr>
            </thead>
            <tbody>
              {sortedSites.map((site, index) => {
                const isShortlisted = shortlistSet.has(site.site_id);
                return (
                  <tr
                    key={`${site.site_id}-${index}`}
                    className="border-t border-slate-100 hover:bg-slate-50/50 cursor-pointer transition-colors"
                    onClick={() => onSelectSite(site)}
                  >
                    <td className="px-4 py-3 text-sm text-slate-400 tabular-nums">{index + 1}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-900">{site.site_name}</span>
                        {/* EXCLUDED badge next to site name */}
                        {excludedSiteIds.has(site.site_id) && (
                          <span className="text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded px-1.5 py-0.5">
                            EXCLUDED
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3" strokeWidth={1.5} />
                        {site.city}
                        {site.state ? `, ${site.state}` : ''}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {site.investigators[0]?.name || (
                        <span className="text-slate-300 italic">Not reported</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`inline-flex items-center justify-center w-10 h-7 text-xs font-bold rounded-md border tabular-nums ${getScoreBadgeStyle(
                            site.final_score
                          )}`}
                        >
                          {Math.round(site.final_score)}
                        </span>
                        <span className="text-xs text-slate-400">P{Math.round(site.percentile || 0)}</span>
                        {/* Calibration Band Badge */}
                        <span
                          className={`text-xs font-medium rounded px-1.5 py-0.5 ${
                            site.calibration_band === 'Strong'
                              ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
                              : site.calibration_band === 'Viable'
                              ? 'text-blue-700 bg-blue-50 border border-blue-200'
                              : site.calibration_band === 'Watchlist'
                              ? 'text-amber-700 bg-amber-50 border border-amber-200'
                              : 'text-red-700 bg-red-50 border border-red-200'
                          }`}
                        >
                          {site.calibration_band || 'Watchlist'}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {/* Data Confidence Badge */}
                      <span
                        title={site.data_sources_checked ? `Sources: ${site.data_sources_checked.map((s: string) => s === 'ctgov' ? 'CT.gov' : s.charAt(0).toUpperCase() + s.slice(1)).join(', ')}` : 'Sources: CT.gov'}
                        className={`text-xs font-medium rounded px-1.5 py-0.5 ${
                          site.data_confidence === 'high'
                            ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
                            : site.data_confidence === 'medium'
                            ? 'text-amber-700 bg-amber-50 border border-amber-200'
                            : 'text-slate-500 bg-slate-50 border border-slate-200'
                        }`}
                      >
                        {site.data_confidence === 'high' ? 'High' : site.data_confidence === 'medium' ? 'Med' : 'Low'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{site.trial_count}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{site.indication_trial_count}</td>
                    <td
                      className="px-4 py-3"
                      title={[
                        site.red_flags.length > 0 ? `Risks: ${site.red_flags.join('; ')}` : '',
                        site.strengths.length > 0 ? `Strengths: ${site.strengths.join('; ')}` : '',
                      ].filter(Boolean).join('\n\n')}
                    >
                      {/* Competing trial count */}
                      {site.competing_trial_count == null ? (
                        <span className="text-xs text-slate-400">—</span>
                      ) : site.competing_trial_count > 0 ? (
                        <span className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
                          {site.competing_trial_count} trial{site.competing_trial_count !== 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5">
                          None
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleShortlist(site);
                        }}
                        className={`p-1 rounded transition-colors ${
                          isShortlisted ? 'text-amber-500' : 'text-slate-300 hover:text-amber-400'
                        }`}
                      >
                        {isShortlisted ? (
                          <Star className="w-5 h-5 fill-current" strokeWidth={1.5} />
                        ) : (
                          <StarOff className="w-5 h-5" strokeWidth={1.5} />
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between py-8 border-t border-slate-200 mt-0">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to country ranking
        </button>
        <div className="text-xs text-slate-400">
          Data: ClinicalTrials.gov · Last updated with project creation
        </div>
      </div>

      {/* Shortlist Sidebar */}
      {showShortlist && (
        <div className="fixed right-0 top-0 bottom-0 w-80 bg-white shadow-xl border-l border-slate-200 overflow-y-auto z-40">
          <div className="sticky top-0 bg-white border-b border-slate-200 p-4 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 flex items-center gap-2">
              <Star className="w-4 h-4 text-amber-500" strokeWidth={1.5} />
              Shortlist ({shortlist.length})
            </h3>
            <button onClick={() => setShowShortlist(false)} className="text-slate-400 hover:text-slate-600">
              <X className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
          <div className="p-4">
            {shortlist.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-8">
                No sites shortlisted yet.
                <br />
                Click the star icon on a site to add it.
              </p>
            ) : (
              <div className="space-y-3">
                {shortlist.map((site) => (
                  <div key={site.site_id} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-slate-900 text-sm truncate">{site.site_name}</p>
                        <p className="text-xs text-slate-500 truncate">
                          {site.city}, {site.country}
                        </p>
                      </div>
                      <span
                        className={`inline-flex items-center justify-center w-8 h-6 text-xs font-bold rounded-md border ml-2 ${getScoreBadgeStyle(
                          site.final_score
                        )}`}
                      >
                        {Math.round(site.final_score)}
                      </span>
                    </div>
                    <button
                      onClick={() => onToggleShortlist(site)}
                      className="mt-2 text-xs text-red-600 hover:text-red-700 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
