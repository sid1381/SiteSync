'use client';

import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  ChevronRight,
  ChevronDown,
  Star,
  StarOff,
  Building2,
  User,
  Shield,
  ClipboardCheck,
  Activity,
  FlaskConical,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  MapPin,
  ExternalLink,
  Globe,
  BookOpen,
  Target,
  Search,
  FileText,
  Minus,
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface CitelinePIDiscovery {
  pi_name?: string;
  pi_city?: string;
  pi_org?: string;
  npi?: string;
  tier?: string;
  total_trials?: number;
  specialties?: string[];
  disease_areas?: string[];
  regulatory_actions?: number;
  org_type?: string;
}

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
  // Citeline enrichment (using Record for API compatibility, cast when using)
  citeline_enriched?: boolean;
  citeline_match_type?: string;
  citeline_tier?: string;
  citeline_pi_discovery?: Record<string, unknown>;
  citeline_enrichment?: Record<string, unknown>;
  // PubMed enrichment (using Record for API compatibility, cast to PubMedData when using)
  pubmed_data?: Record<string, unknown>;
  pubmed_enriched?: boolean;
  // FDA enrichment
  fda_data?: Record<string, unknown>;
  fda_enriched?: boolean;
  // Compliance data
  compliance_data?: Record<string, unknown>;
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

interface Project {
  id: number;
  name: string;
  indication?: string;
  phase?: string;
}

interface SiteDetailViewProps {
  project: Project;
  site: SiteScore | null;
  onToggleShortlist: (site: SiteScore) => void;
  onBack: () => void;
  loading: boolean;
}

interface WebIntelligence {
  institution_name?: string;
  institution_type?: string;
  parent_organization?: string;
  website_url?: string;
  description?: string;
  bed_count?: number;
  has_research_office?: boolean;
  therapeutic_areas?: string[];
  notable_investigators?: Array<{
    name: string;
    role: string;
    department: string;
  }>;
  recent_news?: Array<{
    headline: string;
    date: string;
    source_url: string;
  }>;
  confidence?: 'high' | 'medium' | 'low';
  sources?: string[];
  enrichment_notes?: string;
  _error?: string;
}

interface PubMedPaper {
  pmid: string;
  title: string;
  authors: string;
  journal: string;
  pub_date: string;
  pub_year?: number;
  is_clinical_trial: boolean;
}

interface PubMedData {
  pi_name: string;
  search_query?: string;
  total_publications: number;
  clinical_trial_publications: number;
  recent_papers: PubMedPaper[];
  search_success: boolean;
  error?: string;
}

interface OIGExclusion {
  checked: boolean;
  checked_at?: string;
  excluded: boolean;
  exclusion_type?: string;
  exclusion_date?: string;
  reinstatement_date?: string;
  reinstated?: boolean;
  match_confidence?: string;
}

interface FDAInspection {
  legal_name: string;
  city: string;
  state: string;
  inspection_end_date: string;
  classification: string;  // NAI, VAI, OAI
  project_area: string;
  posted_citations: number;
}

interface FDAInspections {
  checked: boolean;
  checked_at?: string;
  inspections: FDAInspection[];
  total_inspections: number;
  nai_count: number;  // No Action Indicated
  vai_count: number;  // Voluntary Action Indicated
  oai_count: number;  // Official Action Indicated
  most_recent_date?: string;
}

interface ComplianceData {
  npi?: string;
  npi_source?: string;
  npi_resolved_at?: string;
  oig_exclusion?: OIGExclusion;
  fda_inspections?: FDAInspections;
  checked_sources?: Array<{ source: string; checked_at: string }>;
}

// =============================================================================
// HELPERS
// =============================================================================

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-amber-600';
  return 'text-red-600';
}

function getBarColor(score: number): string {
  if (score >= 80) return 'bg-green-500';
  if (score >= 60) return 'bg-amber-500';
  return 'bg-red-500';
}

function getRecommendation(score: number) {
  if (score >= 80)
    return {
      label: 'Strong Candidate',
      bg: 'bg-green-50',
      text: 'text-green-700',
      border: 'border-green-200',
    };
  if (score >= 65)
    return {
      label: 'Viable Candidate',
      bg: 'bg-blue-50',
      text: 'text-blue-700',
      border: 'border-blue-200',
    };
  if (score >= 50)
    return {
      label: 'Conditional',
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      border: 'border-amber-200',
    };
  return {
    label: 'Weak Candidate',
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
  };
}

function getCoverage(site: SiteScore): { pct: number; label: string } {
  let filled = 0;
  const total = 9; // Updated total to include PubMed and Citeline
  if (site.investigators.length > 0 && site.investigators[0]?.name) filled++;
  if (site.trial_count > 0) filled++;
  if (site.indication_trial_count > 0) filled++;
  if (site.city) filled++;
  if (site.experience_score > 0) filled++;
  if (site.red_flags.length > 0 || site.yellow_flags.length > 0 || site.strengths.length > 0) filled++;
  if (site.completion_rate >= 0) filled++;
  // New enrichment checks
  if (site.pubmed_enriched || site.pubmed_data) filled++;
  if (site.citeline_enriched) filled++;
  const pct = Math.round((filled / total) * 100);
  return { pct, label: pct >= 80 ? 'High' : pct >= 50 ? 'Medium' : 'Low' };
}

function generateStrengths(site: SiteScore): string[] {
  const strengths: string[] = [];
  if (site.experience_score >= 80)
    strengths.push(`${site.trial_count} trials including ${site.indication_trial_count} in this indication`);
  if (site.capacity_score >= 70)
    strengths.push('Historical capacity supports protocol workload');
  if (site.compliance_score >= 80)
    strengths.push('Clean regulatory record with no adverse findings');
  if (site.protocol_match_score >= 70)
    strengths.push('Strong protocol-to-capabilities alignment');
  if (site.pi_strength_score >= 70 && site.investigators.length > 0)
    strengths.push(`Experienced PI: ${site.investigators[0]?.name || 'Unknown'}`);
  if (strengths.length === 0)
    strengths.push('Baseline registry profile — consider enrichment for deeper assessment');
  return strengths.slice(0, 3);
}

function generateRisks(site: SiteScore): string[] {
  const risks: string[] = [];
  if (!site.investigators.length || !site.investigators[0]?.name)
    risks.push('PI identity not reported in registry — manual verification needed');
  if (site.pi_strength_score < 40)
    risks.push('Limited PI publication or trial leadership evidence');
  if (site.capacity_score < 50)
    risks.push('Limited enrollment history may indicate capacity constraints');
  if (site.experience_score < 50)
    risks.push('Thin trial history in this therapeutic area');
  if (site.completion_rate < 0.5 && site.completion_rate > 0)
    risks.push(`Low historical completion rate (${Math.round(site.completion_rate * 100)}%)`);
  if (risks.length === 0)
    risks.push('Profile based on public registry data — operational validation recommended');
  return risks.slice(0, 3);
}

// =============================================================================
// DIMENSION CARD
// =============================================================================

function DimensionCard({
  icon: Icon,
  title,
  weight,
  score,
  percentile,
  explanation,
  source,
  children,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  title: string;
  weight: string;
  score: number | null;
  percentile?: number;
  explanation?: string;
  source: string;
  children?: React.ReactNode;
}) {
  const s = score ?? 0;
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" strokeWidth={1.5} />
          <span className="text-sm font-semibold text-slate-900">{title}</span>
          <span className="text-xs text-slate-400">{weight}</span>
        </div>
      </div>
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
        {percentile != null && (
          <span className="text-xs text-slate-400 ml-1">P{Math.round(percentile)}</span>
        )}
      </div>
      {explanation && <p className="text-xs text-slate-600 leading-relaxed mb-2">{explanation}</p>}
      {children && <div className="mt-auto">{children}</div>}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100 text-[11px] text-slate-400">
        <span className="truncate">{source}</span>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function SiteDetailView({
  project,
  site,
  onToggleShortlist,
  onBack,
  loading,
}: SiteDetailViewProps) {
  const [webIntel, setWebIntel] = useState<WebIntelligence | null>(null);
  const [webIntelLoading, setWebIntelLoading] = useState(false);
  const [showMethodology, setShowMethodology] = useState(false);
  const [pubmedData, setPubmedData] = useState<PubMedData | null>(null);
  const [pubmedLoading, setPubmedLoading] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Use API-returned pubmed_data first, fall back to state-based lookup
  // Cast to PubMedData for type safety
  const effectivePubmedData: PubMedData | null = (site?.pubmed_data as PubMedData | undefined) || pubmedData;
  const hasPubmedData = Boolean(effectivePubmedData && (effectivePubmedData.total_publications > 0 || effectivePubmedData.pi_name));

  // Combine citeline_pi_discovery and citeline_enrichment for PI Profile display
  // Cast from Record<string, unknown> to CitelinePIDiscovery
  const citelinePIDiscoveryData = site?.citeline_pi_discovery as CitelinePIDiscovery | undefined;
  const citelineEnrichmentData = site?.citeline_enrichment as CitelinePIDiscovery | undefined;
  const citelinePIData: CitelinePIDiscovery | null = citelinePIDiscoveryData || (citelineEnrichmentData ? {
    pi_name: citelineEnrichmentData.pi_name,
    pi_org: citelineEnrichmentData.pi_org,
    tier: citelineEnrichmentData.tier,
    total_trials: citelineEnrichmentData.total_trials,
    specialties: citelineEnrichmentData.specialties,
    disease_areas: citelineEnrichmentData.disease_areas,
    regulatory_actions: citelineEnrichmentData.regulatory_actions,
    org_type: citelineEnrichmentData.org_type,
    npi: citelineEnrichmentData.npi,
  } : null);

  // Function to look up PubMed publications for a PI
  const lookupPubMed = async (piName: string) => {
    if (!site || !piName) return;

    setPubmedLoading(true);
    try {
      const response = await fetch(
        `${API_URL}/screener/projects/${project.id}/sites/${site.site_id}/pubmed-lookup`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            pi_name: piName,
            specialty: project.indication,
            max_results: 10,
          }),
        }
      );

      if (!response.ok) throw new Error('PubMed lookup failed');

      const data = await response.json();
      setPubmedData(data);
    } catch (error) {
      console.error('PubMed lookup error:', error);
      setPubmedData({
        pi_name: piName,
        total_publications: 0,
        clinical_trial_publications: 0,
        recent_papers: [],
        search_success: false,
        error: 'Lookup failed',
      });
    } finally {
      setPubmedLoading(false);
    }
  };

  // Fetch web intelligence when site loads
  useEffect(() => {
    if (!site) return;
    const siteName = site.site_name;
    const city = site.city;
    if (!siteName || !city) return;

    setWebIntelLoading(true);
    fetch(`${API_URL}/screener/projects/${project.id}/sites/enrich-web`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        site_name: siteName,
        city: city,
        country: site.country,
        indication: project.indication,
        pi_name: site.investigators[0]?.name,
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error('Enrichment not available');
        return r.json();
      })
      .then((data) => {
        setWebIntel(data);
        setWebIntelLoading(false);
      })
      .catch(() => {
        setWebIntel(null);
        setWebIntelLoading(false);
      });
  }, [site, project.id, project.indication, API_URL]);

  // Loading state
  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4">
        <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-slate-600 mb-6">
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to Sites
        </button>
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-500">Loading site details...</p>
          </div>
        </div>
      </div>
    );
  }

  // Not found state
  if (!site) {
    return (
      <div className="max-w-6xl mx-auto px-4">
        <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-slate-600 mb-6">
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to Sites
        </button>
        <div className="border border-slate-200 rounded-lg p-12 text-center">
          <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-3" strokeWidth={1.5} />
          <p className="text-sm text-slate-500">Site not found</p>
        </div>
      </div>
    );
  }

  const score = site.final_score;
  const rec = getRecommendation(score);
  // Note: getCoverage is kept for potential future use but not used in current UI
  const strengths = generateStrengths(site);
  const risks = generateRisks(site);

  return (
    <div className="max-w-6xl mx-auto px-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-slate-400 mb-8">
        <span className="hover:text-slate-600 cursor-pointer">Projects</span>
        <ChevronRight className="w-3 h-3" />
        <span className="hover:text-slate-600 cursor-pointer">{project.name}</span>
        <ChevronRight className="w-3 h-3" />
        <span className="hover:text-slate-600 cursor-pointer">Countries</span>
        <ChevronRight className="w-3 h-3" />
        <span className="hover:text-slate-600 cursor-pointer">{site.country}</span>
        <ChevronRight className="w-3 h-3" />
        <button onClick={onBack} className="hover:text-slate-600 transition-colors">
          Sites
        </button>
        <ChevronRight className="w-3 h-3" />
        <span className="text-slate-700 font-medium">{site.site_name}</span>
      </nav>

      {/* Hero */}
      <div className="mb-10">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1.5">
              <h1 className="text-2xl font-bold text-slate-900">{site.site_name}</h1>
              <span
                className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${rec.bg} ${rec.text} ${rec.border}`}
              >
                {rec.label}
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-500 mb-3">
              <MapPin className="w-3.5 h-3.5" strokeWidth={1.5} />
              {site.city}
              {site.state ? `, ${site.state}` : ''}, {site.country}
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-400 mb-4">
              <span className="flex items-center gap-2">
                PI: {site.investigators[0]?.name || <span className="italic">Not reported</span>}
                {site.citeline_enriched && (
                  <>
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full text-[10px] font-medium">
                      {site.citeline_match_type?.includes('name') || site.citeline_match_type?.includes('npi')
                        ? 'Verified via Citeline'
                        : 'Discovered via Citeline'}
                    </span>
                    {site.citeline_tier && (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        site.citeline_tier === 'Gold' ? 'bg-amber-100 text-amber-700' :
                        site.citeline_tier === 'Silver' ? 'bg-slate-200 text-slate-600' :
                        'bg-orange-100 text-orange-700'
                      }`}>
                        {site.citeline_tier}
                      </span>
                    )}
                  </>
                )}
              </span>
              <span className="text-slate-200">·</span>
              <span>{site.trial_count} trials</span>
              <span className="text-slate-200">·</span>
              <span>{site.indication_trial_count} in indication</span>
              <span className="text-slate-200">·</span>
              <span>Data: {site.data_confidence === 'high' ? 'High' : site.data_confidence === 'medium' ? 'Medium' : 'Low'} confidence</span>
            </div>
          </div>
          <div className="text-right pl-8 flex-shrink-0">
            <div className={`text-5xl font-bold tabular-nums leading-none ${getScoreColor(score)}`}>
              {Math.round(score)}
            </div>
            <div className="flex items-center justify-end gap-2 mt-1">
              <span className="text-xs text-slate-400">P{Math.round(site.percentile || 0)}</span>
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
            <div className="text-xs text-slate-400 mt-1">Site Score</div>
          </div>
        </div>

        {/* Strengths + Risks */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-green-600" strokeWidth={2} />
              Strengths
            </h3>
            <ul className="space-y-2">
              {strengths.map((s, i) => (
                <li key={i} className="text-xs text-slate-700 leading-relaxed flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-green-500 mt-1.5 flex-shrink-0" />
                  {s}
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" strokeWidth={2} />
              Risks & Data Gaps
            </h3>
            <ul className="space-y-2">
              {risks.map((r, i) => (
                <li key={i} className="text-xs text-slate-700 leading-relaxed flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Methodology toggle */}
      <button
        onClick={() => setShowMethodology(!showMethodology)}
        className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors mb-6"
      >
        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform ${showMethodology ? 'rotate-0' : '-rotate-90'}`}
          strokeWidth={2}
        />
        Score methodology
      </button>
      {showMethodology && (
        <div className="mb-6 p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600">
          <p className="mb-2">
            <strong>Site scoring</strong> combines 5 weighted dimensions:{' '}
            <span className="text-slate-500">
              Experience (35%), PI Strength (20%), Capacity (20%), Compliance (15%), Protocol Match (10%)
            </span>
          </p>
          <p>
            The final score is then blended with the country score at a configurable ratio (default 70% site / 30%
            country) to produce the displayed Site Score.
          </p>
        </div>
      )}

      {/* Score dimensions */}
      <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Score Breakdown</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        <DimensionCard
          icon={FlaskConical}
          title="Experience"
          weight="35%"
          score={site.experience_score}
          percentile={site.dimension_percentiles?.experience}
          explanation={`${site.trial_count} total trials, ${site.indication_trial_count} indication-matched`}
          source="ClinicalTrials.gov"
        />
        <DimensionCard
          icon={User}
          title="PI Strength"
          weight="20%"
          score={site.pi_strength_score}
          percentile={site.dimension_percentiles?.pi_strength}
          explanation={
            citelinePIData?.pi_name
              ? `Lead PI: ${citelinePIData.pi_name}${citelinePIData.specialties?.[0] ? ` (${citelinePIData.specialties[0]})` : ''}`
              : site.investigators[0]?.name
                ? `Lead PI: ${site.investigators[0].name}${site.investigators[0].specialty ? ` (${site.investigators[0].specialty})` : ''}`
                : 'PI not identified in registry'
          }
          source={
            hasPubmedData
              ? `PubMed · ${effectivePubmedData?.total_publications || 0} publications`
              : citelinePIData?.pi_name
                ? 'Citeline SiteTrove'
                : site.investigators[0]?.name
                  ? 'ClinicalTrials.gov'
                  : 'No public data'
          }
        >
          {hasPubmedData && effectivePubmedData && (
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <FileText className="w-3 h-3 text-slate-400" />
                <span className="text-slate-600">
                  <span className="font-semibold text-slate-900">{effectivePubmedData.total_publications}</span> publications
                </span>
              </div>
              {effectivePubmedData.clinical_trial_publications > 0 && (
                <span className="text-green-600">
                  {effectivePubmedData.clinical_trial_publications} clinical trial
                </span>
              )}
            </div>
          )}
        </DimensionCard>
        <DimensionCard
          icon={Activity}
          title="Capacity"
          weight="20%"
          score={site.capacity_score}
          percentile={site.dimension_percentiles?.capacity}
          explanation="Based on historical enrollment volume and concurrent trial load"
          source="ClinicalTrials.gov"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        <DimensionCard
          icon={Shield}
          title="Compliance"
          weight="15%"
          score={site.compliance_score}
          percentile={site.dimension_percentiles?.compliance}
          explanation="FDA inspection record and debarment status"
          source="FDA BMIS · ClinicalTrials.gov"
        />
        <DimensionCard
          icon={ClipboardCheck}
          title="Protocol Match"
          weight="10%"
          score={site.protocol_match_score}
          percentile={site.dimension_percentiles?.protocol_match}
          explanation="AI gap analysis comparing protocol requirements vs site capabilities"
          source="AI analysis"
        />
      </div>

      {/* Investigators */}
      {site.investigators.length > 0 && (
        <div className="mb-10">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Investigators</h2>
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50">
                  <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-2.5">
                    Name
                  </th>
                  <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-2.5">
                    Role
                  </th>
                  <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-2.5">
                    Specialty
                  </th>
                  <th className="text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-4 py-2.5">
                    Trials
                  </th>
                </tr>
              </thead>
              <tbody>
                {site.investigators.map((inv, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-4 py-2.5 text-sm text-slate-900 font-medium">{inv.name}</td>
                    <td className="px-4 py-2.5 text-sm text-slate-600">{inv.role || '—'}</td>
                    <td className="px-4 py-2.5 text-sm text-slate-600">{inv.specialty || '—'}</td>
                    <td className="px-4 py-2.5 text-sm text-slate-600 tabular-nums">{inv.trial_count ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* PubMed lookup button - show if we have investigators but no Citeline PI data and no PubMed data yet */}
            {!citelinePIData && site.investigators[0]?.name && !hasPubmedData && (
              <div className="px-4 py-3 bg-slate-50 border-t border-slate-100">
                <button
                  onClick={() => lookupPubMed(site.investigators[0].name)}
                  disabled={pubmedLoading}
                  className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 transition-colors disabled:opacity-50"
                >
                  {pubmedLoading ? (
                    <>
                      <div className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin" />
                      Searching PubMed...
                    </>
                  ) : (
                    <>
                      <Search className="w-3 h-3" strokeWidth={1.5} />
                      Look up publications for {site.investigators[0].name}
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* PI Profile from Citeline - show for citeline_pi_discovery OR citeline_enrichment */}
      {citelinePIData && citelinePIData.pi_name && (
        <div className="mb-10">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
            PI Profile
            <span className="ml-2 text-slate-300 font-normal normal-case">via Citeline SiteTrove</span>
          </h2>
          <div className="border border-slate-200 rounded-lg p-5 bg-white">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left column: PI identity */}
              <div>
                <p className="text-lg font-semibold text-slate-900 mb-1">
                  {citelinePIData.pi_name}
                </p>
                {citelinePIData.npi && (
                  <p className="text-xs font-mono text-slate-400 mb-2">
                    NPI: {citelinePIData.npi}
                  </p>
                )}
                {citelinePIData.pi_org && (
                  <div className="text-sm text-slate-600">
                    {citelinePIData.pi_org}
                    {citelinePIData.org_type && (
                      <span className="text-slate-400"> · {citelinePIData.org_type}</span>
                    )}
                  </div>
                )}
              </div>
              {/* Right column: Stats */}
              <div className="flex flex-wrap items-start gap-4">
                {citelinePIData.total_trials != null && (
                  <div>
                    <span className="text-[11px] text-slate-400 block">Total Trials</span>
                    <span className="text-xl font-bold text-slate-900 tabular-nums">
                      {citelinePIData.total_trials}
                    </span>
                  </div>
                )}
                {citelinePIData.specialties && citelinePIData.specialties.length > 0 && (
                  <div className="flex-1 min-w-[120px]">
                    <span className="text-[11px] text-slate-400 block">Specialties</span>
                    <span className="text-sm text-slate-700">
                      {citelinePIData.specialties.join(', ')}
                    </span>
                  </div>
                )}
                {citelinePIData.tier && (
                  <div>
                    <span className="text-[11px] text-slate-400 block mb-1">Tier</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      citelinePIData.tier === 'Gold' ? 'bg-amber-100 text-amber-700' :
                      citelinePIData.tier === 'Silver' ? 'bg-slate-200 text-slate-600' :
                      'bg-orange-100 text-orange-700'
                    }`}>
                      {citelinePIData.tier}
                    </span>
                  </div>
                )}
              </div>
            </div>
            {/* Disease areas */}
            {citelinePIData.disease_areas && citelinePIData.disease_areas.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <span className="text-[11px] text-slate-400 block mb-2">Disease Areas</span>
                <div className="flex flex-wrap gap-1.5">
                  {citelinePIData.disease_areas.map((area, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                      {area}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {/* Regulatory history - only show if non-zero */}
            {citelinePIData.regulatory_actions != null && citelinePIData.regulatory_actions > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-100">
                <span className="text-xs text-amber-600">
                  ⚠ {citelinePIData.regulatory_actions} regulatory action{citelinePIData.regulatory_actions > 1 ? 's' : ''} on record
                </span>
              </div>
            )}
            {/* PubMed lookup button - only show if no pubmed data yet */}
            {!hasPubmedData && citelinePIData.pi_name && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <button
                  onClick={() => lookupPubMed(citelinePIData.pi_name!)}
                  disabled={pubmedLoading}
                  className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 transition-colors disabled:opacity-50"
                >
                  {pubmedLoading ? (
                    <>
                      <div className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin" />
                      Searching PubMed...
                    </>
                  ) : (
                    <>
                      <Search className="w-3 h-3" strokeWidth={1.5} />
                      Look up publications
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Publications - PubMed */}
      {hasPubmedData && effectivePubmedData && (
        <div className="mb-10">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
            Publications
            <span className="ml-2 text-slate-300 font-normal normal-case">via PubMed</span>
          </h2>
          <div className="border border-slate-200 rounded-lg p-5 bg-white">
            {/* Summary stats */}
            <div className="flex items-center gap-6 mb-4 pb-4 border-b border-slate-100">
              <div>
                <span className="text-[11px] text-slate-400 block">Total Publications</span>
                <span className="text-2xl font-bold text-slate-900 tabular-nums">
                  {effectivePubmedData.total_publications}
                </span>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block">Clinical Trial Papers</span>
                <span className="text-2xl font-bold text-green-600 tabular-nums">
                  {effectivePubmedData.clinical_trial_publications}
                </span>
              </div>
              <div className="flex-1 text-right">
                <span className="text-[11px] text-slate-400">
                  Searched: {effectivePubmedData.pi_name}
                </span>
              </div>
            </div>

            {/* Recent papers */}
            {effectivePubmedData.recent_papers && effectivePubmedData.recent_papers.length > 0 ? (
              <div>
                <span className="text-[11px] text-slate-400 block mb-3">Recent Papers</span>
                <div className="space-y-3">
                  {effectivePubmedData.recent_papers.slice(0, 5).map((paper) => (
                    <div key={paper.pmid} className="border-l-2 border-slate-200 pl-3">
                      <a
                        href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-slate-900 hover:text-blue-600 font-medium line-clamp-2"
                      >
                        {paper.title}
                      </a>
                      <div className="text-xs text-slate-500 mt-1">
                        {paper.authors} · {paper.journal} · {paper.pub_date}
                        {paper.is_clinical_trial && (
                          <span className="ml-2 px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-[10px]">
                            Clinical Trial
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                {effectivePubmedData.total_publications > 5 && (
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(effectivePubmedData.search_query || effectivePubmedData.pi_name)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mt-4"
                  >
                    <ExternalLink className="w-3 h-3" strokeWidth={1.5} />
                    View all {effectivePubmedData.total_publications} publications on PubMed
                  </a>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No recent papers found</p>
            )}
          </div>
        </div>
      )}

      {/* Compliance & Regulatory */}
      {(() => {
        const complianceData = site?.compliance_data as ComplianceData | undefined;
        const hasComplianceData = complianceData && (
          complianceData.npi ||
          complianceData.oig_exclusion?.checked ||
          complianceData.fda_inspections?.checked
        );

        // Check if OIG exclusion found (serious red flag)
        const oigExcluded = complianceData?.oig_exclusion?.excluded && !complianceData?.oig_exclusion?.reinstated;

        return hasComplianceData ? (
          <div className="mb-10">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
              Compliance & Regulatory
              <span className="ml-2 text-slate-300 font-normal normal-case">via OIG LEIE, FDA, NPPES</span>
            </h2>

            {/* OIG Exclusion Alert Banner */}
            {oigExcluded && (
              <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" strokeWidth={2} />
                <div>
                  <p className="text-sm font-semibold text-red-800">OIG LEIE Exclusion Found</p>
                  <p className="text-xs text-red-700 mt-1">
                    This investigator appears on the OIG List of Excluded Individuals/Entities.
                    {complianceData?.oig_exclusion?.exclusion_type && (
                      <> Type: {complianceData.oig_exclusion.exclusion_type}.</>
                    )}
                    {complianceData?.oig_exclusion?.exclusion_date && (
                      <> Date: {complianceData.oig_exclusion.exclusion_date}.</>
                    )}
                  </p>
                  <p className="text-xs text-red-600 mt-2 font-medium">
                    ⚠️ Excluded individuals cannot participate in federally funded healthcare programs.
                  </p>
                </div>
              </div>
            )}

            <div className="border border-slate-200 rounded-lg p-5 bg-white">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* NPI */}
                <div>
                  <span className="text-[11px] text-slate-400 block mb-1">NPI (National Provider ID)</span>
                  {complianceData?.npi ? (
                    <div>
                      <span className="text-sm font-mono text-slate-900">{complianceData.npi}</span>
                      <span className="text-xs text-slate-400 ml-2">
                        via {complianceData.npi_source === 'citeline' ? 'Citeline' : 'NPPES'}
                      </span>
                    </div>
                  ) : (
                    <span className="text-sm text-slate-400">Not resolved</span>
                  )}
                </div>

                {/* OIG Status */}
                <div>
                  <span className="text-[11px] text-slate-400 block mb-1">OIG Exclusion Status</span>
                  {complianceData?.oig_exclusion?.checked ? (
                    complianceData.oig_exclusion.excluded ? (
                      complianceData.oig_exclusion.reinstated ? (
                        <div className="flex items-center gap-1.5">
                          <AlertTriangle className="w-4 h-4 text-amber-500" strokeWidth={2} />
                          <span className="text-sm text-amber-700">Previously excluded (reinstated)</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <XCircle className="w-4 h-4 text-red-600" strokeWidth={2} />
                          <span className="text-sm text-red-700 font-medium">Excluded</span>
                        </div>
                      )
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-green-600" strokeWidth={2} />
                        <span className="text-sm text-green-700">Clear</span>
                      </div>
                    )
                  ) : (
                    <span className="text-sm text-slate-400">Not checked</span>
                  )}
                </div>

                {/* FDA Inspections */}
                <div>
                  <span className="text-[11px] text-slate-400 block mb-1">FDA Inspections</span>
                  {complianceData?.fda_inspections?.checked ? (
                    complianceData.fda_inspections.total_inspections > 0 ? (
                      <div>
                        <span className="text-sm text-slate-900">{complianceData.fda_inspections.total_inspections} inspections</span>
                        <div className="flex items-center gap-2 mt-1">
                          {complianceData.fda_inspections.nai_count > 0 && (
                            <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                              {complianceData.fda_inspections.nai_count} NAI
                            </span>
                          )}
                          {complianceData.fda_inspections.vai_count > 0 && (
                            <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">
                              {complianceData.fda_inspections.vai_count} VAI
                            </span>
                          )}
                          {complianceData.fda_inspections.oai_count > 0 && (
                            <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                              {complianceData.fda_inspections.oai_count} OAI
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <span className="text-sm text-slate-500">No inspections on record</span>
                    )
                  ) : (
                    <span className="text-sm text-slate-400">Not checked</span>
                  )}
                </div>
              </div>

              {/* Data sources and timestamps */}
              {complianceData?.checked_sources && complianceData.checked_sources.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <span className="text-[11px] text-slate-400">
                    Checked: {complianceData.checked_sources.map(s => s.source.replace('_', ' ').toUpperCase()).join(', ')}
                    {complianceData.checked_sources[0]?.checked_at && (
                      <> · {new Date(complianceData.checked_sources[0].checked_at).toLocaleDateString()}</>
                    )}
                  </span>
                </div>
              )}
            </div>
          </div>
        ) : null;
      })()}

      {/* Site Intelligence */}
      <div className="mb-10">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Site Intelligence
          <span className="ml-2 text-slate-300 font-normal normal-case">AI-gathered from public web sources</span>
        </h2>
        {webIntelLoading ? (
          <div className="border border-slate-200 rounded-lg p-8 text-center bg-white">
            <div className="w-5 h-5 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-slate-400">Researching site information...</p>
          </div>
        ) : webIntel && !webIntel._error ? (
          <div className="border border-slate-200 rounded-lg p-5 bg-white">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                {webIntel.institution_type && webIntel.institution_type !== 'Unknown' && (
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400">Institution type</span>
                    <p className="text-sm text-slate-700">{webIntel.institution_type}</p>
                  </div>
                )}
                {webIntel.parent_organization && (
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400">Parent organization</span>
                    <p className="text-sm text-slate-700">{webIntel.parent_organization}</p>
                  </div>
                )}
                {webIntel.description && (
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400">Overview</span>
                    <p className="text-sm text-slate-700">{webIntel.description}</p>
                  </div>
                )}
                {webIntel.website_url && (
                  <a
                    href={webIntel.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                  >
                    <Globe className="w-3 h-3" strokeWidth={1.5} />
                    Visit website
                  </a>
                )}
              </div>
              <div>
                {webIntel.therapeutic_areas && webIntel.therapeutic_areas.length > 0 && (
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400">Key therapeutic areas</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {webIntel.therapeutic_areas.map((ta, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                          {ta}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {webIntel.bed_count && (
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400">Facility size</span>
                    <p className="text-sm text-slate-700">~{webIntel.bed_count} beds</p>
                  </div>
                )}
                {webIntel.has_research_office && (
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400">Research infrastructure</span>
                    <p className="text-sm text-slate-700">Dedicated clinical trials office</p>
                  </div>
                )}
              </div>
            </div>
            {/* Source attribution */}
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
              <span>
                Confidence: {webIntel.confidence || 'unknown'} · Sources: {(webIntel.sources || []).length} web pages
              </span>
              {webIntel.enrichment_notes && <span>{webIntel.enrichment_notes}</span>}
            </div>
          </div>
        ) : (
          <div className="border border-dashed border-slate-200 rounded-lg p-6 text-center text-xs text-slate-400 bg-white">
            Web enrichment unavailable for this site
          </div>
        )}
      </div>

      {/* Trial History */}
      <div className="mb-10">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Trial Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="border border-slate-200 rounded-lg p-4 bg-white text-center">
            <div className="text-2xl font-bold text-slate-900 tabular-nums">{site.trial_count}</div>
            <div className="text-xs text-slate-400 mt-1">Total Trials</div>
          </div>
          <div className="border border-slate-200 rounded-lg p-4 bg-white text-center">
            <div className="text-2xl font-bold text-green-600 tabular-nums">{site.indication_trial_count}</div>
            <div className="text-xs text-slate-400 mt-1">Indication Trials</div>
          </div>
          <div className="border border-slate-200 rounded-lg p-4 bg-white text-center">
            <div className={`text-2xl font-bold tabular-nums ${site.competing_trial_count > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
              {site.competing_trial_count}
            </div>
            <div className="text-xs text-slate-400 mt-1">Competing Trials</div>
          </div>
          <div className="border border-slate-200 rounded-lg p-4 bg-white text-center">
            <div className="text-2xl font-bold text-slate-900 tabular-nums">
              {site.completion_rate > 0 ? `${Math.round(site.completion_rate * 100)}%` : 'N/A'}
            </div>
            <div className="text-xs text-slate-400 mt-1">Completion Rate</div>
          </div>
        </div>
      </div>

      {/* Competing Trials */}
      <div className="mb-10">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Competing Trials</h2>
        <div className="border border-slate-200 rounded-lg p-5 bg-white">
          {site.competing_trial_count > 0 ? (
            <div>
              <p className="text-sm text-slate-700 mb-4">
                <span className="font-semibold text-amber-600">{site.competing_trial_count}</span> actively recruiting trial{site.competing_trial_count !== 1 ? 's' : ''} at this site that may compete for the same patient population.
              </p>
              <a
                href={`https://clinicaltrials.gov/search?cond=${encodeURIComponent(project.indication || '')}&locStr=${encodeURIComponent(`${site.city}${site.state ? `, ${site.state}` : ''}`)}&aggFilters=status:rec`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 underline"
              >
                View on ClinicalTrials.gov
                <ExternalLink className="w-3.5 h-3.5" strokeWidth={1.5} />
              </a>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" strokeWidth={2} />
              <span className="text-sm text-slate-700">No actively recruiting competing trials at this site</span>
            </div>
          )}
        </div>
      </div>

      {/* Gap Analysis */}
      {site.gap_analysis && (
        <div className="mb-10">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Gap Analysis</h2>
          <div className="border border-slate-200 rounded-lg p-5 bg-white">
            <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{site.gap_analysis}</p>
          </div>
        </div>
      )}

      {/* Red Flags */}
      {site.red_flags.length > 0 && (
        <div className="mb-10">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Red Flags</h2>
          <div className="space-y-2">
            {site.red_flags.map((flag, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-3 bg-white border border-slate-200 rounded-lg"
              >
                <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" strokeWidth={1.5} />
                <span className="text-sm text-slate-700">{flag}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Confidence */}
      <div className="mb-10">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Data Confidence
        </h2>
        <div className="border border-slate-200 rounded-lg p-5 bg-white">
          {/* Tier badge and source indicators */}
          <div className="flex items-center gap-6 mb-4">
            {/* Tier badge */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">Confidence:</span>
              <span
                className={`text-sm font-semibold rounded px-2 py-1 ${
                  site.data_confidence === 'high'
                    ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
                    : site.data_confidence === 'medium'
                    ? 'text-amber-700 bg-amber-50 border border-amber-200'
                    : 'text-slate-500 bg-slate-50 border border-slate-200'
                }`}
              >
                {site.data_confidence === 'high' ? 'High' : site.data_confidence === 'medium' ? 'Medium' : 'Low'}
              </span>
              <span className="text-xs text-slate-400">
                ({site.data_source_count || 1} of 4 sources)
              </span>
            </div>
          </div>

          {/* Source indicators - horizontal row */}
          <div className="flex items-center gap-4 flex-wrap">
            {[
              { key: 'ctgov', label: 'CT.gov', always: true },
              { key: 'citeline', label: 'Citeline', always: false },
              { key: 'pubmed', label: 'PubMed', always: false },
              { key: 'compliance', label: 'Compliance', always: false },
            ].map((source) => {
              const isChecked = source.always || (site.data_sources_checked?.includes(source.key) ?? false);
              return (
                <div key={source.key} className="flex items-center gap-1.5">
                  {isChecked ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" strokeWidth={2} />
                  ) : (
                    <Minus className="w-4 h-4 text-slate-300" strokeWidth={2} />
                  )}
                  <span className={`text-xs ${isChecked ? 'text-slate-600' : 'text-slate-300'}`}>
                    {source.label}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Collapsible Details section */}
          <details className="mt-4 pt-4 border-t border-slate-100">
            <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600">
              Field-level data coverage
            </summary>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2 text-xs mt-3">
              {[
                { label: 'Trial history', available: site.trial_count > 0, source: 'ClinicalTrials.gov' },
                {
                  label: 'PI identity',
                  available: !!(site.investigators[0]?.name || citelinePIData?.pi_name),
                  source: citelinePIData?.pi_name ? 'Citeline SiteTrove' : (site.investigators[0]?.name ? 'ClinicalTrials.gov' : 'Not available')
                },
                {
                  label: 'Regulatory record',
                  available: !!site.fda_enriched,
                  source: site.fda_enriched ? 'FDA CLIIL' : 'FDA BMIS'
                },
                {
                  label: 'Publications',
                  available: hasPubmedData,
                  source: hasPubmedData
                    ? `PubMed · ${effectivePubmedData?.total_publications || 0} found`
                    : (site.investigators[0]?.name || citelinePIData?.pi_name)
                      ? 'Click "Look up publications" above'
                      : 'Requires PI identity'
                },
                {
                  label: 'Enrollment performance',
                  available: !!site.citeline_enriched,
                  source: site.citeline_enriched ? 'Citeline SiteTrove' : 'Available with Citeline SiteTrove'
                },
                { label: 'Start-up cycle time', available: false, source: 'Available with CTMS integration' },
                { label: 'Catchment demographics', available: false, source: 'Coming soon · US Census / CDC' },
                {
                  label: 'PI regulatory history',
                  available: !!(citelinePIData?.regulatory_actions != null),
                  source: citelinePIData?.regulatory_actions != null ? 'Citeline SiteTrove' : 'Available with Citeline SiteTrove'
                },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-2">
                    {item.available ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-500" strokeWidth={2} />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-200" />
                    )}
                    <span className={item.available ? 'text-slate-700' : 'text-slate-400'}>{item.label}</span>
                  </div>
                  <span className={item.available ? 'text-green-600' : 'text-slate-300'}>{item.source}</span>
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between py-8 border-t border-slate-200">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to site ranking
        </button>
        <button
          onClick={() => onToggleShortlist(site)}
          className={`flex items-center gap-2 text-sm font-medium px-5 py-2.5 rounded-lg transition-colors ${
            site.is_shortlisted
              ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
              : 'bg-slate-900 text-white hover:bg-slate-800'
          }`}
        >
          {site.is_shortlisted ? (
            <>
              <Star className="w-4 h-4 fill-current" strokeWidth={1.5} />
              On Shortlist
            </>
          ) : (
            <>
              <StarOff className="w-4 h-4" strokeWidth={1.5} />
              Add to Shortlist
            </>
          )}
        </button>
      </div>
    </div>
  );
}
