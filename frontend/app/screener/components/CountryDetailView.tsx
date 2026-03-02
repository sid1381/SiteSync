'use client';

import React, { useState, useRef } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  ChevronDown,
  FlaskConical,
  Building2,
  Swords,
  Shield,
  Users,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  CheckCircle,
  ExternalLink,
  Upload,
} from 'lucide-react';
import CompetingTrialsMap from './CompetingTrialsMap';

// ============================================================
// TYPES
// ============================================================
interface DimensionBreakdown {
  trial_experience?: {
    score: number;
    weight: number;
    weighted_contribution: number;
    data: {
      indication_trials: number;
      total_trials: number;
      weighted_experience?: number;
      avg_weight_per_trial?: number | null;
      weights_applied?: boolean;
      percentile_rank: number;
      rank_position: string;
    };
    explanation: string;
  };
  site_density?: {
    score: number;
    weight: number;
    weighted_contribution: number;
    data: {
      site_count: number;
      sites_per_10m_pop: number | null;
      percentile_rank: number;
      rank_position: string;
    };
    explanation: string;
  };
  competition?: {
    score: number;
    weight: number;
    weighted_contribution: number;
    data: {
      competing_trials: number;
      competition_demand: number | null;
      addressable_pool: number | null;
      competition_ratio: number | null;
      pressure_level: string;
      demand_source?: string;
      avg_competing_enrollment?: number | null;
    };
    explanation: string;
  };
  regulatory?: {
    score: number;
    weight: number;
    weighted_contribution: number;
    data: {
      regulatory_quality?: { raw: number; normalized: number; weight: number };
      logistics_index?: { raw: number | null; normalized: number | null; weight: number };
      health_expenditure?: { raw: number | null; normalized: number; weight: number };
      gbt_bonus?: { bonus: number; tier: string; authority: string };
      source?: string;
    };
    explanation: string;
    missing?: boolean;
  };
  prevalence?: {
    score: number;
    weight: number;
    weighted_contribution: number;
    data: {
      prevalence_per_100k: number | null;
      source: string | null;
      data_year: number | null;
      confidence: string | null;
      estimated_patients: number | null;
      addressable_pool: number | null;
      percentile_rank: number;
      rank_position: string;
    };
    explanation: string;
    missing?: boolean;
  };
  overall?: {
    score: number;
    formula: string;
    result: number;
  };
}

interface CountryScore {
  country_code: string;
  country_name: string;
  composite_score: number;
  trial_experience_score: number;
  site_density_score: number;
  competition_score: number;
  regulatory_score: number;
  prevalence_score: number;
  total_trials: number;
  indication_trials: number;
  site_count: number;
  actively_recruiting: number;
  regulatory_summary?: string;
  prevalence_estimate?: string;
  regulatory_quality_raw?: number;
  physician_density?: number;
  logistics_index?: number;
  health_expenditure_pct?: number;
  population?: number;
  prevalence_per_100k?: number;
  estimated_patients?: number;
  addressable_pool?: number;
  competition_demand?: number;
  competition_ratio?: number;
  competition_pressure?: string;
  competing_trial_details?: Array<{
    nct_id: string;
    enrollment?: number;
    sites_in_country?: number;
    sites_total?: number;
  }>;
  dimension_breakdown?: DimensionBreakdown;
}

interface CountryDetailViewProps {
  country: CountryScore;
  projectId: number;
  projectName?: string;
  extraData?: Record<string, any>;
  onBack: () => void;
  onViewSites: (countryCode: string) => void;
  onRefresh?: () => void;
}

// ============================================================
// HELPERS
// ============================================================
function getRecommendation(score: number) {
  if (score >= 85) return { label: 'Strong Include', bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' };
  if (score >= 70) return { label: 'Include', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' };
  if (score >= 50) return { label: 'Conditional', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' };
  return { label: 'Not Recommended', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' };
}

function getScoreColor(score: number) {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-amber-600';
  return 'text-red-600';
}

function getBarColor(score: number) {
  if (score >= 80) return 'bg-green-500';
  if (score >= 60) return 'bg-amber-500';
  return 'bg-red-500';
}

function getConfidence(bd: DimensionBreakdown | undefined) {
  if (!bd) return 'Low';
  const scores = [
    bd.trial_experience?.score,
    bd.site_density?.score,
    bd.competition?.score,
    bd.regulatory?.score,
    bd.prevalence?.score,
  ];
  const available = scores.filter(s => s != null).length;
  if (available >= 5) return 'High';
  if (available >= 3) return 'Medium';
  return 'Low';
}

function generateSummary(country: CountryScore, rec: { label: string }): string {
  const bd = country.dimension_breakdown;
  const score = country.composite_score || 0;

  if (score >= 85) {
    const strengths = [];
    if ((bd?.site_density?.score || 0) >= 80) strengths.push('strong site infrastructure');
    if ((bd?.competition?.score || 0) >= 80) strengths.push('low competition pressure');
    if ((bd?.trial_experience?.score || 0) >= 80) strengths.push('deep trial experience');
    if ((bd?.regulatory?.score || 0) >= 80) strengths.push('established regulatory pathway');
    const top2 = strengths.slice(0, 2).join(' and ');
    return `High-priority country for this protocol with ${top2 || 'strong overall feasibility'}.`;
  } else if (score >= 70) {
    return `Viable candidate with moderate-to-strong feasibility. Review dimension details before finalizing.`;
  } else if (score >= 50) {
    return `Below-average feasibility profile. Consider only if specific strategic factors justify inclusion.`;
  }
  return `Weak feasibility profile across multiple dimensions. Not recommended for this protocol.`;
}

function generateStrengths(country: CountryScore): string[] {
  const bd = country.dimension_breakdown;
  const strengths: string[] = [];

  if ((bd?.trial_experience?.score || 0) >= 80)
    strengths.push(`${country.indication_trials} indication-matched trials support efficient site activation`);
  if ((bd?.site_density?.score || 0) >= 80)
    strengths.push(`Dense site network (${country.site_count} sites) enables flexible startup planning`);
  if ((bd?.competition?.score || 0) >= 80)
    strengths.push(`Low competitive pressure — enrollment unlikely to be constrained`);
  if ((bd?.regulatory?.score || 0) >= 80) {
    const gbt = bd?.regulatory?.data?.gbt_bonus?.tier;
    strengths.push(`Established regulatory framework${gbt && gbt !== 'Unclassified' ? ` (${gbt})` : ''}`);
  }
  if ((bd?.prevalence?.score || 0) >= 80)
    strengths.push(`Large addressable patient pool supports enrollment targets`);

  // If everything is strong, add a general one
  if (strengths.length === 0)
    strengths.push('Balanced profile across all dimensions');

  return strengths.slice(0, 3);
}

function generateRisks(country: CountryScore): string[] {
  const bd = country.dimension_breakdown;
  const risks: string[] = [];

  // Always flag prevalence data quality
  const prevSource = bd?.prevalence?.data?.source;
  if (prevSource) {
    risks.push(`Prevalence based on ${prevSource} — not validated against local registry data`);
  } else {
    risks.push(`Prevalence estimate is model-derived — local validation recommended`);
  }

  // Score-based risks
  if ((bd?.competition?.score || 100) < 60)
    risks.push(`${country.actively_recruiting} competing trials creating enrollment pressure`);
  if ((bd?.regulatory?.score || 100) < 70)
    risks.push(`Regulatory environment may extend startup timelines`);
  if ((bd?.trial_experience?.score || 100) < 60)
    risks.push(`Limited prior trial experience in this indication`);
  if ((bd?.site_density?.score || 100) < 60)
    risks.push(`Sparse site infrastructure — limited backup options`);

  // General modeling caveat if all scores are high
  if (risks.length <= 1)
    risks.push(`Scores assume current competitive landscape — monitor for new trial registrations`);

  return risks.slice(0, 3);
}

function trimExplanation(text: string, maxLength: number = 100): string {
  if (!text || text.length <= maxLength) return text;
  // Cut at last complete word within limit
  const trimmed = text.substring(0, maxLength);
  const lastSpace = trimmed.lastIndexOf(' ');
  return trimmed.substring(0, lastSpace > 0 ? lastSpace : maxLength) + '…';
}

// Map prevalence confidence to DimensionCard confidence level
function getPrevalenceConfidenceLevel(confidence: string | null | undefined): string {
  switch (confidence) {
    case 'published': return 'High';
    case 'regional_estimate': return 'Medium';
    case 'modeled': return 'Low';
    default: return 'Low';
  }
}

// Get prevalence confidence badge styling
function getPrevalenceConfidenceBadge(confidence: string | null | undefined): { text: string; className: string } {
  switch (confidence) {
    case 'published':
      return {
        text: 'Published',
        className: 'text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1.5 py-0.5'
      };
    case 'regional_estimate':
      return {
        text: 'Regional Est.',
        className: 'text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5'
      };
    case 'modeled':
    default:
      return {
        text: 'Modeled',
        className: 'text-xs font-medium text-slate-500 bg-slate-50 border border-slate-200 rounded px-1.5 py-0.5'
      };
  }
}

function getImplication(key: string, score: number): string {
  const implications: Record<string, Record<string, string>> = {
    trial_experience: {
      high: 'Experienced sites should enable efficient startup',
      mid: 'May need additional site training and monitoring',
      low: 'Budget for extended site qualification process',
    },
    site_density: {
      high: 'Dense network supports flexible site selection',
      mid: 'Limited backup options if sites underperform',
      low: 'Sparse infrastructure may constrain enrollment',
    },
    competition: {
      high: 'Competition unlikely to slow enrollment',
      mid: 'Moderate competition — monitor enrollment pace',
      low: 'Significant pressure — plan enrollment contingencies',
    },
    regulatory: {
      high: 'Standard regulatory timelines expected',
      mid: 'Allow additional lead time for approvals',
      low: 'Extended approval timelines likely',
    },
    prevalence: {
      high: 'Large patient pool supports enrollment targets',
      mid: 'Realistic targets recommended',
      low: 'Extended recruitment period may be needed',
    },
  };
  const level = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';
  return implications[key]?.[level] || '';
}

// ============================================================
// DIMENSION CARD
// ============================================================
function DimensionCard({
  icon: Icon,
  title,
  weight,
  score,
  contribution,
  explanation,
  implication,
  confidence,
  source,
  children,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  title: string;
  weight: number;
  score: number | null | undefined;
  contribution: number | null | undefined;
  explanation: string;
  implication: string;
  confidence: string;
  source: string;
  children?: React.ReactNode;
}) {
  const s = score ?? 0;
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" strokeWidth={1.5} />
          <span className="text-sm font-semibold text-slate-900">{title}</span>
          <span className="text-xs text-slate-400">{(weight * 100).toFixed(0)}%</span>
        </div>
        <span className="text-xs text-slate-400 tabular-nums">+{contribution?.toFixed(1) ?? '—'}</span>
      </div>

      {/* Score + bar */}
      <div className="flex items-center gap-3 mb-3">
        <div className="flex-1 bg-slate-100 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all ${getBarColor(s)}`}
            style={{ width: `${Math.min(s, 100)}%` }}
          />
        </div>
        <span className={`text-2xl font-bold tabular-nums ${getScoreColor(s)}`}>
          {score != null ? Math.round(s) : '—'}
        </span>
      </div>

      {/* Explanation */}
      <p className="text-xs text-slate-600 leading-relaxed mb-2">{explanation}</p>

      {/* Implication */}
      {implication && (
        <p className="text-xs text-slate-500 italic mb-3">{implication}</p>
      )}

      {/* Dimension-specific data */}
      {children && <div className="mt-auto">{children}</div>}

      {/* Source footer */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100 text-[11px] text-slate-400">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
          confidence === 'High' ? 'bg-green-400' :
          confidence === 'Medium' ? 'bg-amber-400' : 'bg-red-400'
        }`} />
        <span>{confidence}</span>
        <span className="text-slate-200">·</span>
        <span className="truncate">{source}</span>
      </div>
    </div>
  );
}

// ============================================================
// MAIN COMPONENT
// ============================================================
export default function CountryDetailView({
  country,
  projectId,
  projectName,
  extraData,
  onBack,
  onViewSites,
  onRefresh,
}: CountryDetailViewProps) {
  const [showMethodology, setShowMethodology] = useState(false);

  // Check if trialtrove analytics exist for this country
  const trialtroveAnalytics = extraData?.trialtrove_analytics?.[country.country_code]?.analytics;

  // TrialTrove upload state
  const [trialtroveResult, setTrialtroveResult] = useState<any>(null);
  const [trialtroveLoading, setTrialtroveLoading] = useState(false);
  const [trialtroveError, setTrialtroveError] = useState<string | null>(null);
  const [trialtroveApplying, setTrialtroveApplying] = useState(false);
  const [trialtroveApplied, setTrialtroveApplied] = useState(false);
  const [showTrialtroveUpdate, setShowTrialtroveUpdate] = useState(false);
  const trialtroveFileInputRef = useRef<HTMLInputElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // TrialTrove upload handler
  const handleTrialtroveUpload = async (file: File) => {
    setTrialtroveLoading(true);
    setTrialtroveError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(
        `${API_URL}/screener/projects/${projectId}/upload-trialtrove?country_code=${country.country_code}`,
        { method: 'POST', body: formData }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const result = await res.json();
      setTrialtroveResult(result);
    } catch (e: any) {
      setTrialtroveError(e.message);
    } finally {
      setTrialtroveLoading(false);
    }
  };

  // Apply TrialTrove enrichment (moves from pending to permanent storage)
  const handleApplyTrialtrove = async () => {
    if (!trialtroveResult) return;

    setTrialtroveApplying(true);
    try {
      // No file needed - backend uses data stored during upload
      const res = await fetch(
        `${API_URL}/screener/projects/${projectId}/apply-trialtrove?country_code=${country.country_code}`,
        { method: 'POST' }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to apply enrichment');
      }

      setTrialtroveApplied(true);
      setShowTrialtroveUpdate(false);
      onRefresh?.();
    } catch (e: any) {
      setTrialtroveError(e.message);
    } finally {
      setTrialtroveApplying(false);
    }
  };

  if (!country) return null;

  const bd = country.dimension_breakdown;
  const score = country.composite_score || 0;
  const rec = getRecommendation(score);
  const confidence = getConfidence(bd);
  const strengths = generateStrengths(country);
  const risks = generateRisks(country);

  return (
    <div className="max-w-6xl mx-auto px-4">

      {/* ── BREADCRUMB ── */}
      <nav className="flex items-center gap-1.5 text-xs text-slate-400 mb-8">
        <button onClick={onBack} className="hover:text-slate-600 transition-colors">Projects</button>
        <ChevronRight className="w-3 h-3" />
        <button onClick={onBack} className="hover:text-slate-600 transition-colors">{projectName || 'Project'}</button>
        <ChevronRight className="w-3 h-3" />
        <button onClick={onBack} className="hover:text-slate-600 transition-colors">Countries</button>
        <ChevronRight className="w-3 h-3" />
        <span className="text-slate-700 font-medium">{country.country_name}</span>
      </nav>

      {/* ── HERO ── */}
      <div className="mb-10">
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-slate-900">{country.country_name}</h1>
              <span className="text-sm text-slate-400">{country.country_code}</span>
              <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${rec.bg} ${rec.text} ${rec.border}`}>
                {rec.label}
              </span>
            </div>
            <p className="text-sm text-slate-500">
              {country.indication_trials} indication trials · {country.site_count} sites · {country.actively_recruiting} competing · Confidence: {confidence}
            </p>
          </div>
          <div className="text-right pl-8">
            <div className={`text-5xl font-bold tabular-nums leading-none ${getScoreColor(score)}`}>
              {Math.round(score)}
            </div>
            <div className="text-xs text-slate-400 mt-1">Composite Score</div>
          </div>
        </div>

        {/* Executive summary */}
        <p className="text-sm text-slate-700 leading-relaxed mb-6">
          {generateSummary(country, rec)}
        </p>

        {/* Strengths / Risks two-column */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-green-50/50 border border-green-100 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-green-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={2} />
              Strengths
            </h3>
            <ul className="space-y-2">
              {strengths.map((s, i) => (
                <li key={i} className="text-xs text-green-800 leading-relaxed flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-green-500 mt-1.5 flex-shrink-0" />
                  {s}
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-amber-50/50 border border-amber-100 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-amber-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" strokeWidth={2} />
              Risks &amp; Data Caveats
            </h3>
            <ul className="space-y-2">
              {risks.map((r, i) => (
                <li key={i} className="text-xs text-amber-800 leading-relaxed flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* ── METHODOLOGY (collapsed) ── */}
      <button
        onClick={() => setShowMethodology(!showMethodology)}
        className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors mb-6"
      >
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showMethodology ? 'rotate-0' : '-rotate-90'}`} strokeWidth={2} />
        Score methodology
      </button>
      {showMethodology && (
        <div className="bg-slate-900 text-slate-300 rounded-lg px-4 py-3 text-xs font-mono mb-6">
          {Math.round(bd?.trial_experience?.score || 0)}×{((bd?.trial_experience?.weight || 0.3) * 100).toFixed(0)}% + {' '}
          {Math.round(bd?.site_density?.score || 0)}×{((bd?.site_density?.weight || 0.25) * 100).toFixed(0)}% + {' '}
          {Math.round(bd?.competition?.score || 0)}×{((bd?.competition?.weight || 0.2) * 100).toFixed(0)}% + {' '}
          {Math.round(bd?.regulatory?.score || 0)}×{((bd?.regulatory?.weight || 0.15) * 100).toFixed(0)}% + {' '}
          {Math.round(bd?.prevalence?.score || 0)}×{((bd?.prevalence?.weight || 0.1) * 100).toFixed(0)}%
          {' = '}<span className="text-white font-bold">{Math.round(score)}</span>
        </div>
      )}

      {/* ── TRIALTROVE ENRICHMENT (hidden when analytics exist, unless updating) ── */}
      {(!trialtroveAnalytics || showTrialtroveUpdate) && (
      <div className="mb-8">
        {/* Hidden file input */}
        <input
          ref={trialtroveFileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleTrialtroveUpload(f);
          }}
        />

        <div className="border border-slate-200 rounded-lg bg-white overflow-hidden">
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                <Upload className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-700">Enrich with Citeline TrialTrove</p>
                <p className="text-xs text-slate-400">Upload competitive trial landscape, enrollment benchmarks, and sponsor intelligence</p>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="p-5">
            {!trialtroveResult ? (
              <div>
                <button
                  onClick={() => trialtroveFileInputRef.current?.click()}
                  disabled={trialtroveLoading}
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 border border-slate-300 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
                >
                  {trialtroveLoading ? (
                    <span className="flex items-center gap-2">
                      <div className="w-3 h-3 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
                      Processing...
                    </span>
                  ) : 'Upload .xlsx'}
                </button>
                {trialtroveError && (
                  <p className="mt-2 text-xs text-red-600">{trialtroveError}</p>
                )}
              </div>
            ) : (
              /* TrialTrove Results - Analytics Preview */
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
                      <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700">
                        TrialTrove — {trialtroveResult.file_name || 'Parsed'}
                      </p>
                      <p className="text-xs text-slate-500">
                        {trialtroveResult.total_records} trials • {trialtroveResult.nct_overlap || 0} overlap with existing data
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => { setTrialtroveResult(null); setTrialtroveError(null); setTrialtroveApplied(false); }}
                    className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700"
                  >
                    Dismiss
                  </button>
                </div>

                {/* Analytics Preview Grid */}
                {trialtroveResult.analytics_preview && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">Active Trials</p>
                      <p className="text-lg font-semibold text-slate-800">
                        {trialtroveResult.analytics_preview.active_trials || 0}
                      </p>
                      <p className="text-xs text-slate-400">
                        {trialtroveResult.analytics_preview.recruiting_trials || 0} recruiting
                      </p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">Median Enrollment</p>
                      <p className="text-lg font-semibold text-slate-800">
                        {trialtroveResult.analytics_preview.median_pts_per_site_month != null
                          ? `${trialtroveResult.analytics_preview.median_pts_per_site_month.toFixed(2)}/site/mo`
                          : trialtroveResult.analytics_preview.median_enrollment || '—'}
                      </p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">Top Sponsor</p>
                      <p className="text-sm font-medium text-slate-800 truncate" title={trialtroveResult.analytics_preview.top_sponsor}>
                        {trialtroveResult.analytics_preview.top_sponsor || '—'}
                      </p>
                      <p className="text-xs text-slate-400">
                        of {trialtroveResult.analytics_preview.sponsor_count || 0} sponsors
                      </p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">Top Endpoint</p>
                      <p className="text-sm font-medium text-slate-800 truncate" title={trialtroveResult.analytics_preview.top_endpoint}>
                        {trialtroveResult.analytics_preview.top_endpoint || '—'}
                      </p>
                    </div>
                  </div>
                )}

                {/* Phase Distribution */}
                {trialtroveResult.analytics_preview?.phase_distribution && Object.keys(trialtroveResult.analytics_preview.phase_distribution).length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(trialtroveResult.analytics_preview.phase_distribution).map(([phase, count]) => (
                      <span key={phase} className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded">
                        {phase}: {count as number}
                      </span>
                    ))}
                  </div>
                )}

                {/* Apply Button */}
                {!trialtroveApplied ? (
                  <button
                    onClick={handleApplyTrialtrove}
                    disabled={trialtroveApplying}
                    className="w-full px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {trialtroveApplying ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Applying...
                      </span>
                    ) : (
                      'Apply Enrichment'
                    )}
                  </button>
                ) : (
                  <div className="flex items-center justify-center gap-2 py-2 text-sm text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    Enrichment applied successfully
                  </div>
                )}

                {trialtroveError && (
                  <p className="text-xs text-red-600">{trialtroveError}</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* ── DIMENSION CARDS (3 columns top row) ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        <DimensionCard
          icon={FlaskConical}
          title="Trial Experience"
          weight={bd?.trial_experience?.weight ?? 0.3}
          score={bd?.trial_experience?.score}
          contribution={bd?.trial_experience?.weighted_contribution}
          explanation={trimExplanation(bd?.trial_experience?.explanation || `${country.indication_trials} indication-specific trials`)}
          implication={getImplication('trial_experience', bd?.trial_experience?.score || 0)}
          confidence="High"
          source="ClinicalTrials.gov"
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>Indication trials: <strong className="text-slate-700">{bd?.trial_experience?.data?.indication_trials ?? country.indication_trials}</strong></span>
            <span>Total trials: <strong className="text-slate-700">{bd?.trial_experience?.data?.total_trials ?? country.total_trials}</strong></span>
            {bd?.trial_experience?.data?.weighted_experience != null && (
              <span>Weighted: <strong className="text-slate-700">{bd.trial_experience.data.weighted_experience.toFixed(1)}</strong></span>
            )}
            {bd?.trial_experience?.data?.rank_position && (
              <span>Rank: <strong className="text-slate-700">{bd.trial_experience.data.rank_position}</strong></span>
            )}
          </div>
        </DimensionCard>

        <DimensionCard
          icon={Building2}
          title="Site Density"
          weight={bd?.site_density?.weight ?? 0.25}
          score={bd?.site_density?.score}
          contribution={bd?.site_density?.weighted_contribution}
          explanation={trimExplanation(bd?.site_density?.explanation || `${country.site_count} research sites`)}
          implication={getImplication('site_density', bd?.site_density?.score || 0)}
          confidence="High"
          source="ClinicalTrials.gov + World Bank"
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>Sites: <strong className="text-slate-700">{bd?.site_density?.data?.site_count ?? country.site_count}</strong></span>
            {bd?.site_density?.data?.sites_per_10m_pop != null && (
              <span>Per 10M: <strong className="text-slate-700">{bd.site_density.data.sites_per_10m_pop.toFixed(1)}</strong></span>
            )}
            {bd?.site_density?.data?.rank_position && (
              <span className="col-span-2">Rank: <strong className="text-slate-700">{bd.site_density.data.rank_position}</strong></span>
            )}
          </div>
        </DimensionCard>

        <DimensionCard
          icon={Swords}
          title="Competition"
          weight={bd?.competition?.weight ?? 0.2}
          score={bd?.competition?.score}
          contribution={bd?.competition?.weighted_contribution}
          explanation={trimExplanation(bd?.competition?.explanation || `${country.actively_recruiting} competing trials`)}
          implication={getImplication('competition', bd?.competition?.score || 0)}
          confidence={country.competing_trial_details && country.competing_trial_details.length > 0 ? 'High' : 'Medium'}
          source={`CT.gov enrollment (${country.competing_trial_details?.length || 0} trials)`}
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>Competing: <strong className="text-slate-700">{country.actively_recruiting} trials</strong></span>
            <span>Pressure: <strong className={
              country.competition_pressure === 'low' ? 'text-green-600' :
              country.competition_pressure === 'moderate' ? 'text-amber-600' :
              'text-red-600'
            }>{country.competition_pressure || 'unknown'}</strong></span>
            {country.competition_demand != null && (
              <span>Demand: <strong className="text-slate-700">~{country.competition_demand.toLocaleString()}</strong></span>
            )}
            {country.addressable_pool != null && (
              <span>Pool: <strong className="text-slate-700">~{country.addressable_pool.toLocaleString()}</strong></span>
            )}
          </div>
        </DimensionCard>
      </div>

      {/* ── DIMENSION CARDS (2 columns bottom row) ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        <DimensionCard
          icon={Shield}
          title="Regulatory"
          weight={bd?.regulatory?.weight ?? 0.15}
          score={bd?.regulatory?.score}
          contribution={bd?.regulatory?.weighted_contribution}
          explanation={trimExplanation(bd?.regulatory?.explanation || country.regulatory_summary || 'Regulatory assessment')}
          implication={getImplication('regulatory', bd?.regulatory?.score || 0)}
          confidence={bd?.regulatory?.data?.gbt_bonus?.tier && bd.regulatory.data.gbt_bonus.tier !== 'Unclassified' ? 'High' : 'Medium'}
          source="World Bank + WHO/ICH"
        >
          <div className="space-y-2">
            <div className="grid grid-cols-3 gap-x-3 gap-y-1 text-xs text-slate-500">
              {bd?.regulatory?.data?.regulatory_quality?.normalized != null && (
                <span>RQ: <strong className="text-slate-700">{Math.round(bd.regulatory.data.regulatory_quality.normalized)}</strong></span>
              )}
              {bd?.regulatory?.data?.logistics_index?.normalized != null && (
                <span>LPI: <strong className="text-slate-700">{Math.round(bd.regulatory.data.logistics_index.normalized)}</strong></span>
              )}
              {bd?.regulatory?.data?.health_expenditure?.normalized != null && (
                <span>HE: <strong className="text-slate-700">{Math.round(bd.regulatory.data.health_expenditure.normalized)}</strong></span>
              )}
            </div>
            {bd?.regulatory?.data?.gbt_bonus && bd.regulatory.data.gbt_bonus.tier !== 'Unclassified' && (
              <div className="text-xs text-blue-600">
                {bd.regulatory.data.gbt_bonus.tier}: +{bd.regulatory.data.gbt_bonus.bonus} ({bd.regulatory.data.gbt_bonus.authority})
              </div>
            )}
          </div>
        </DimensionCard>

        <DimensionCard
          icon={Users}
          title="Prevalence"
          weight={bd?.prevalence?.weight ?? 0.1}
          score={bd?.prevalence?.score}
          contribution={bd?.prevalence?.weighted_contribution}
          explanation={trimExplanation(bd?.prevalence?.explanation || country.prevalence_estimate || 'Prevalence assessment')}
          implication={getImplication('prevalence', bd?.prevalence?.score || 0)}
          confidence={getPrevalenceConfidenceLevel(bd?.prevalence?.data?.confidence)}
          source={`${bd?.prevalence?.data?.source || 'Literature synthesis'}${bd?.prevalence?.data?.data_year ? ` · ${bd.prevalence.data.data_year}` : ''}`}
        >
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
              {country.prevalence_per_100k != null && (
                <span>Rate: <strong className="text-slate-700">{country.prevalence_per_100k.toFixed(0)}/100k</strong></span>
              )}
              {country.estimated_patients != null && (
                <span>Patients: <strong className="text-slate-700">~{country.estimated_patients.toLocaleString()}</strong></span>
              )}
              {bd?.prevalence?.data?.rank_position && (
                <span className="col-span-2">Rank: <strong className="text-slate-700">{bd.prevalence.data.rank_position}</strong></span>
              )}
            </div>
            {/* Confidence badge */}
            {bd?.prevalence?.data?.confidence && (
              <div className="flex items-center gap-2">
                <span className={getPrevalenceConfidenceBadge(bd.prevalence.data.confidence).className}>
                  {getPrevalenceConfidenceBadge(bd.prevalence.data.confidence).text}
                </span>
              </div>
            )}
          </div>
        </DimensionCard>
      </div>

      {/* ── AI ANALYSIS ── */}
      {(country.regulatory_summary || country.prevalence_estimate) && (
        <div className="mb-10">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Analysis</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {country.regulatory_summary && (
              <div className="border border-slate-200 rounded-lg p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Shield className="w-4 h-4 text-slate-400" strokeWidth={1.5} />
                  <h3 className="text-sm font-semibold text-slate-900">Regulatory Environment</h3>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">{country.regulatory_summary}</p>
              </div>
            )}
            {country.prevalence_estimate && (
              <div className="border border-slate-200 rounded-lg p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Users className="w-4 h-4 text-slate-400" strokeWidth={1.5} />
                  <h3 className="text-sm font-semibold text-slate-900">Recruitment Feasibility</h3>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">{country.prevalence_estimate}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── COMPETITIVE INTELLIGENCE (Citeline TrialTrove) ── */}
      {trialtroveAnalytics && (
        <div className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Competitive Intelligence
            </h2>
            <button
              onClick={() => setShowTrialtroveUpdate(true)}
              className="text-xs text-blue-600 hover:text-blue-700 hover:underline"
            >
              Update TrialTrove data
            </button>
          </div>

          <div className="border border-slate-200 rounded-lg bg-white overflow-hidden">
            {/* Source badge */}
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-blue-50 to-indigo-50">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600" />
                </div>
                <span className="text-xs font-medium text-slate-700">Citeline TrialTrove</span>
              </div>
              <span className="text-[10px] text-slate-500">
                {extraData?.trialtrove_analytics?.[country.country_code]?.uploaded_at
                  ? `Updated ${new Date(extraData.trialtrove_analytics[country.country_code].uploaded_at).toLocaleDateString()}`
                  : 'Data applied'}
              </span>
            </div>

            {/* Key Metrics Grid */}
            <div className="p-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {/* Active Trials */}
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500 mb-1">Active Trials</p>
                  <p className="text-2xl font-bold text-slate-900">
                    {trialtroveAnalytics.competition_summary?.active_trials ?? 0}
                  </p>
                  <p className="text-xs text-slate-400">all phases · all indication trials in {country.country_name}</p>
                  <p className="text-xs text-slate-400">
                    {trialtroveAnalytics.competition_summary?.by_status?.Open ?? 0} recruiting
                  </p>
                </div>

                {/* Enrollment Rate */}
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500 mb-1">Enrollment Rate</p>
                  <p className="text-2xl font-bold text-slate-900">
                    {trialtroveAnalytics.enrollment_benchmarks?.median_pts_site_month != null
                      ? trialtroveAnalytics.enrollment_benchmarks.median_pts_site_month.toFixed(2)
                      : '—'}
                  </p>
                  <p className="text-xs text-slate-400">pts/site/month</p>
                </div>

                {/* Median Duration */}
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500 mb-1">Median Duration</p>
                  <p className="text-2xl font-bold text-slate-900">
                    {trialtroveAnalytics.enrollment_benchmarks?.median_enrollment_duration_months != null
                      ? `${trialtroveAnalytics.enrollment_benchmarks.median_enrollment_duration_months.toFixed(0)}mo`
                      : '—'}
                  </p>
                  <p className="text-xs text-slate-400">enrollment period</p>
                </div>

                {/* Trial Universe */}
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500 mb-1">Trial Universe</p>
                  <p className="text-2xl font-bold text-slate-900">
                    {trialtroveAnalytics.competition_summary?.total_trials ?? 0}
                  </p>
                  <p className="text-xs text-slate-400">total trials</p>
                </div>
              </div>

              {/* Phase Distribution */}
              {trialtroveAnalytics.competition_summary?.by_phase && Object.keys(trialtroveAnalytics.competition_summary.by_phase).length > 0 && (
                <div className="mb-6">
                  <p className="text-xs font-medium text-slate-600 mb-2">Phase Distribution</p>
                  <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
                    {(() => {
                      const phases = trialtroveAnalytics.competition_summary.by_phase;
                      const total = Object.values(phases).reduce((a: number, b: any) => a + (Number(b) || 0), 0);
                      const colors: Record<string, string> = {
                        'I': 'bg-blue-300',
                        'II': 'bg-blue-500',
                        'III': 'bg-blue-700',
                        'IV': 'bg-indigo-600',
                      };
                      // Order phases consistently
                      const phaseOrder = ['I', 'II', 'III', 'IV', 'other'];
                      const sortedEntries = Object.entries(phases).sort(
                        ([a], [b]) => phaseOrder.indexOf(a) - phaseOrder.indexOf(b)
                      );
                      return sortedEntries.map(([phase, count]) => (
                        <div
                          key={phase}
                          className={`${colors[phase] || 'bg-slate-400'} transition-all`}
                          style={{ width: `${((Number(count) || 0) / total) * 100}%` }}
                          title={`Phase ${phase}: ${count}`}
                        />
                      ));
                    })()}
                  </div>
                  <div className="flex flex-wrap gap-3 mt-2">
                    {Object.entries(trialtroveAnalytics.competition_summary.by_phase)
                      .sort(([a], [b]) => ['I', 'II', 'III', 'IV', 'other'].indexOf(a) - ['I', 'II', 'III', 'IV', 'other'].indexOf(b))
                      .map(([phase, count]) => (
                      <span key={phase} className="text-xs text-slate-500">
                        <span className="font-medium text-slate-700">Phase {phase}:</span> {count as number}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Two-column: Top Sponsors & Top Endpoints */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Top Sponsors */}
                {trialtroveAnalytics.sponsor_landscape?.top_sponsors && trialtroveAnalytics.sponsor_landscape.top_sponsors.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-600 mb-2">Top Sponsors</p>
                    <div className="space-y-2">
                      {trialtroveAnalytics.sponsor_landscape.top_sponsors.slice(0, 5).map((s: { name: string; trial_count: number }, i: number) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="text-slate-700 truncate pr-2" title={s.name}>{s.name}</span>
                          <span className="text-slate-500 tabular-nums flex-shrink-0">{s.trial_count} trials</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Top Endpoints */}
                {trialtroveAnalytics.endpoint_landscape?.top_endpoints && trialtroveAnalytics.endpoint_landscape.top_endpoints.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-600 mb-2">Top Endpoints</p>
                    <div className="space-y-2">
                      {trialtroveAnalytics.endpoint_landscape.top_endpoints.slice(0, 5).map((e: { name: string; trial_count: number }, i: number) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="text-slate-700 truncate pr-2" title={e.name}>{e.name}</span>
                          <span className="text-slate-500 tabular-nums flex-shrink-0">{e.trial_count} trials</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── COMPETING TRIALS MAP (2-column: map + trial list) ── */}
      <div className="mb-10">
        <div className="mb-4">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Competing Trial Landscape</h2>
          <p className="text-xs text-slate-400 mt-1">Directly competing for patients · matched phase & indication</p>
        </div>
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-5">
            {/* Map - 3 columns */}
            <div className="lg:col-span-3 h-[420px]">
              <CompetingTrialsMap
                countryCode={country.country_code}
                countryName={country.country_name}
                competingTrialDetails={country.competing_trial_details || []}
                activelyRecruiting={country.actively_recruiting || 0}
                competitionDemand={country.competition_demand || 0}
                competitionPressure={country.competition_pressure || 'unknown'}
                compact={true}
              />
            </div>
            {/* Trial list - 2 columns */}
            <div className="lg:col-span-2 border-t lg:border-t-0 lg:border-l border-slate-200 flex flex-col max-h-[420px]">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between flex-shrink-0">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Competing Trials ({country.competing_trial_details?.length || 0})
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  country.competition_pressure === 'low' ? 'bg-green-50 text-green-600' :
                  country.competition_pressure === 'moderate' ? 'bg-amber-50 text-amber-600' :
                  'bg-red-50 text-red-600'
                }`}>
                  {country.competition_pressure || 'unknown'}
                </span>
              </div>
              <div className="flex-1 overflow-y-auto">
                {(country.competing_trial_details || []).map((trial, i) => (
                  <div key={i} className="px-4 py-3 border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                    <div className="flex items-center justify-between mb-1">
                      <a
                        href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-blue-600 hover:underline flex items-center gap-1"
                      >
                        {trial.nct_id}
                        <ExternalLink className="w-3 h-3" strokeWidth={1.5} />
                      </a>
                      <span className="text-xs font-semibold text-slate-700 tabular-nums">
                        {trial.enrollment ? `${trial.enrollment} target` : '—'}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {trial.sites_in_country || '?'} sites in {country.country_name} · {trial.sites_total || '?'} total
                    </div>
                  </div>
                ))}
                {(!country.competing_trial_details || country.competing_trial_details.length === 0) && (
                  <div className="px-4 py-8 text-center text-xs text-slate-400">
                    No competing trial data available
                  </div>
                )}
              </div>
              <div className="px-4 py-2 border-t border-slate-100 text-[11px] text-slate-400 flex-shrink-0">
                Source: ClinicalTrials.gov · Locations approximate
              </div>
              {trialtroveAnalytics && (
                <div className="px-4 py-2 border-t border-slate-100 text-[11px] text-blue-600 flex-shrink-0 bg-blue-50/50">
                  ↑ TrialTrove identifies {trialtroveAnalytics.competition_summary?.active_trials ?? 0} active indication trials across all phases in this market
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── RAW DATA (collapsed) ── */}
      {(country.regulatory_quality_raw != null || country.physician_density != null ||
        country.logistics_index != null || country.health_expenditure_pct != null) && (
        <details className="mb-10 group">
          <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600 transition-colors list-none flex items-center gap-1">
            <ChevronRight className="w-3.5 h-3.5 transition-transform group-open:rotate-90" strokeWidth={2} />
            World Bank Indicators
          </summary>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
            {country.regulatory_quality_raw != null && (
              <div className="border border-slate-200 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-slate-800 tabular-nums">{country.regulatory_quality_raw.toFixed(2)}</div>
                <div className="text-[11px] text-slate-400">Regulatory Quality</div>
              </div>
            )}
            {country.physician_density != null && (
              <div className="border border-slate-200 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-slate-800 tabular-nums">{country.physician_density.toFixed(1)}</div>
                <div className="text-[11px] text-slate-400">Physicians/1k</div>
              </div>
            )}
            {country.logistics_index != null && (
              <div className="border border-slate-200 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-slate-800 tabular-nums">{country.logistics_index.toFixed(2)}</div>
                <div className="text-[11px] text-slate-400">Logistics Index</div>
              </div>
            )}
            {country.health_expenditure_pct != null && (
              <div className="border border-slate-200 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-slate-800 tabular-nums">{country.health_expenditure_pct.toFixed(1)}%</div>
                <div className="text-[11px] text-slate-400">Health Exp/GDP</div>
              </div>
            )}
          </div>
        </details>
      )}

      {/* ── FOOTER ACTIONS ── */}
      <div className="flex items-center justify-between py-6 border-t border-slate-200">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to country ranking
        </button>
        <button
          onClick={() => onViewSites(country.country_code)}
          className="flex items-center gap-2 bg-slate-900 text-white text-sm font-medium px-5 py-2.5 rounded-lg hover:bg-slate-800 transition-colors"
        >
          Continue to site prioritization
          <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
