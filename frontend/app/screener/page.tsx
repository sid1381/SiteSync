'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Upload,
  FileText,
  Globe,
  Building2,
  Star,
  StarOff,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  Plus,
  Check,
  AlertCircle,
  Loader2,
  Search,
  Filter,
  Download,
  RefreshCw,
  X,
  Users,
  Clock,
  Target,
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FlaskConical,
  Stethoscope,
  Calendar,
  MapPin,
  Pill,
  Shield,
} from 'lucide-react';
import CountryDetailView from './components/CountryDetailView';
import SiteRankingView from './components/SiteRankingView';
import SiteDetailView from './components/SiteDetailView';

// =============================================================================
// TYPES
// =============================================================================

type ScreenerView = 'dashboard' | 'protocol_review' | 'country_ranking' | 'country_detail' | 'site_ranking' | 'site_detail';

interface Project {
  id: number;
  name: string;
  status: 'draft' | 'analyzing' | 'countries_ready' | 'sites_ready' | 'complete';
  indication?: string;
  therapeutic_area?: string;
  phase?: string;
  created_at: string;
  updated_at: string;
  countries_analyzed?: number;
  shortlisted_sites?: number;
  protocol_criteria?: ProtocolCriteria;
  site_weights?: SiteWeights;
  extra_data?: Record<string, any>;
}

interface ProtocolCriteria {
  // Study Identity
  study_title?: string;
  protocol_number?: string;
  sponsor?: string;
  phase: string;
  therapeutic_area: string;

  // Study Design
  design_type?: string;
  arm_count?: number;
  arms_description?: string[];
  allocation_ratio?: string;
  blinding?: string;
  control_type?: string;

  // Investigational Product
  drug_name?: string;
  drug_class?: string;
  dose_and_route?: string;
  dosing_frequency?: string;
  administration_duration?: string;

  // Patient Population
  indication: string;
  indication_detail?: string;
  age_range?: string;
  age_min?: number;
  age_max?: number;
  sex_eligibility?: string;
  enrollment_target?: number;
  patients_per_site?: number;
  target_countries?: string[];

  // Eligibility
  inclusion_criteria?: string[];
  exclusion_criteria?: string[];

  // Timeline
  screening_period?: string;
  treatment_duration?: string;
  follow_up_duration?: string;
  total_duration?: string;
  duration?: string;
  duration_weeks?: number;
  total_visits?: number;
  visit_count?: number;
  visit_frequency?: string;

  // Endpoints
  primary_endpoint?: string;
  secondary_endpoints?: string[];
  primary_assessment?: string;

  // Site Requirements
  required_equipment?: string[];
  required_staff?: string[];
  procedures?: string[];

  // Site Capability Flags
  requires_endoscopy?: boolean;
  requires_infusion?: boolean;
  requires_imaging?: string[];
  requires_biopsy?: boolean;
  storage_requirements?: string[];
  sample_processing?: string[];
  lab_requirements?: string[];
  ecg_required?: boolean;

  // Safety
  dsmb_required?: boolean;
  safety_monitoring?: string;

  // Metadata
  extraction_confidence?: string;
  extraction_warnings?: string[];
}

// Dimension breakdown for transparent scoring
interface DimensionBreakdown {
  trial_experience?: {
    score: number;
    weight: number;
    weighted_contribution: number;
    data: {
      indication_trials: number;
      total_trials: number;
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
      source?: string;
    };
    explanation: string;
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
  // World Bank indicator raw values
  regulatory_quality_raw?: number;  // RQ.EST (-2.5 to 2.5)
  physician_density?: number;       // Physicians per 1,000
  logistics_index?: number;         // LPI (1-5)
  health_expenditure_pct?: number;  // Health exp % of GDP
  // Population data
  population?: number;
  // Prevalence data (data-driven from GPT epidemiology lookup)
  prevalence_per_100k?: number;     // Published prevalence rate
  incidence_per_100k?: number;      // Annual incidence rate
  prevalence_source?: string;       // Citation string
  prevalence_confidence?: string;   // 'published', 'regional_estimate', 'modeled'
  prevalence_data_year?: number;
  // Addressable patient pool (calculated)
  estimated_patients?: number;      // Total patients in country
  eligibility_fraction?: number;    // Fraction after exclusion criteria
  addressable_pool?: number;        // Patients eligible for trial
  // Competition pressure (demand/supply model)
  competition_demand?: number;      // Estimated recruiting demand
  competition_ratio?: number;       // demand / supply ratio
  competition_pressure?: string;    // 'low', 'moderate', 'high', 'extreme'
  // Dimension breakdown for transparent scoring
  dimension_breakdown?: DimensionBreakdown;
}

interface CitelinePIDiscoveryPage {
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

interface PubMedPaperPage {
  pmid: string;
  title: string;
  authors: string;
  journal: string;
  pub_date: string;
  pub_year?: number;
  is_clinical_trial: boolean;
}

interface PubMedDataPage {
  pi_name: string;
  search_query?: string;
  total_publications: number;
  clinical_trial_publications: number;
  recent_papers: PubMedPaperPage[];
  search_success?: boolean;
  error?: string;
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
}

interface CountryWeights {
  trial_experience: number;
  site_density: number;
  competition: number;
  regulatory: number;
  prevalence: number;
}

interface SiteWeights {
  experience: number;
  pi_strength: number;
  capacity: number;
  compliance: number;
  protocol_match: number;
}

type SortDirection = 'asc' | 'desc';

interface SortConfig {
  key: string;
  direction: SortDirection;
}

// =============================================================================
// API CLIENT
// =============================================================================

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const screenerApi = {
  async getProjects(): Promise<{ projects: Project[] }> {
    const res = await fetch(`${API_URL}/screener/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  async createProject(name: string): Promise<Project> {
    const res = await fetch(`${API_URL}/screener/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  },

  async getProject(id: number): Promise<Project> {
    const res = await fetch(`${API_URL}/screener/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  async uploadProtocol(projectId: number, file: File): Promise<{ project_id: number; status: string; extracted_criteria: ProtocolCriteria }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/upload-protocol`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Failed to upload protocol');
    return res.json();
  },

  async confirmProtocol(projectId: number, criteria: ProtocolCriteria): Promise<{ status: string }> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/confirm-protocol`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ criteria })
    });
    if (!res.ok) throw new Error('Failed to confirm protocol');
    return res.json();
  },

  async getCountries(projectId: number): Promise<{ project_id: number; total_countries: number; countries: CountryScore[] }> {
    // include_ai=true enables GPT-4o regulatory/prevalence analysis for top 15 countries
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/countries?include_ai=true`);
    if (!res.ok) throw new Error('Failed to fetch countries');
    return res.json();
  },

  async refreshCountries(projectId: number, weights: CountryWeights): Promise<{ project_id: number; total_countries: number; countries: CountryScore[] }> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/countries/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weights })
    });
    if (!res.ok) throw new Error('Failed to refresh countries');
    return res.json();
  },

  async getSitesInCountry(projectId: number, countryCode: string): Promise<{ project_id: number; country_code: string; country_name: string; total_sites: number; sites: SiteScore[] }> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/countries/${countryCode}/sites`);
    if (!res.ok) throw new Error('Failed to fetch sites');
    return res.json();
  },

  async getSiteDetail(projectId: number, siteId: string): Promise<SiteScore> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/sites/${siteId}`);
    if (!res.ok) throw new Error('Failed to fetch site detail');
    return res.json();
  },

  async toggleShortlist(projectId: number, siteId: string, action: 'add' | 'remove'): Promise<{ success: boolean }> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/shortlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site_id: siteId, action })
    });
    if (!res.ok) throw new Error('Failed to update shortlist');
    return res.json();
  },

  async getShortlist(projectId: number): Promise<{ total: number; sites: SiteScore[] }> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/shortlist`);
    if (!res.ok) throw new Error('Failed to fetch shortlist');
    return res.json();
  },

  async exportProject(projectId: number): Promise<Blob> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/export`);
    if (!res.ok) throw new Error('Failed to export project');
    return res.blob();
  },

  async updateSiteWeights(
    projectId: number,
    weights: SiteWeights,
    presetName?: string
  ): Promise<{ status: string; weights: SiteWeights; preset_name?: string }> {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/site-weights`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weights, preset_name: presetName })
    });
    if (!res.ok) throw new Error('Failed to update site weights');
    return res.json();
  }
};

// =============================================================================
// UTILITY COMPONENTS
// =============================================================================

function ScoreBadge({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' | 'lg' }) {
  const color = score >= 70
    ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
    : score >= 50
    ? 'bg-amber-100 text-amber-800 border-amber-200'
    : 'bg-red-100 text-red-800 border-red-200';

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base'
  };

  return (
    <span className={`inline-flex items-center font-bold rounded-full border ${color} ${sizeClasses[size]}`}>
      {Math.round(score)}
    </span>
  );
}

function ScoreBar({ score, label, className = '' }: { score: number; label?: string; className?: string }) {
  const color = score >= 70
    ? 'bg-emerald-500'
    : score >= 50
    ? 'bg-amber-500'
    : 'bg-red-500';

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {label && <span className="text-xs text-slate-700 w-20 truncate">{label}</span>}
      <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all duration-300`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-8 text-right">{Math.round(score)}</span>
    </div>
  );
}

function LoadingState({ messages }: { messages: string[] }) {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex(i => (i + 1) % messages.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [messages.length]);

  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="relative">
        <div className="w-16 h-16 border-4 border-blue-200 rounded-full animate-spin border-t-blue-600" />
        <FlaskConical className="absolute inset-0 m-auto w-6 h-6 text-blue-600" />
      </div>
      <p className="mt-6 text-lg font-medium text-slate-800">{messages[currentIndex]}</p>
      <div className="mt-4 flex gap-1">
        {messages.map((_, i) => (
          <div key={i} className={`w-2 h-2 rounded-full ${i === currentIndex ? 'bg-blue-600' : 'bg-slate-300'}`} />
        ))}
      </div>
    </div>
  );
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-4">
      <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
      <div className="flex-1">
        <p className="text-red-800 font-medium">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors font-medium"
      >
        Retry
      </button>
    </div>
  );
}

function EmptyState({ icon: Icon, title, description, action }: {
  icon: React.ElementType;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void }
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-slate-700" />
      </div>
      <h3 className="text-lg font-semibold text-slate-800 mb-2">{title}</h3>
      <p className="text-slate-700 max-w-md mb-6">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

function SkeletonRow({ columns }: { columns: number }) {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-slate-200 rounded w-3/4" />
        </td>
      ))}
    </tr>
  );
}

function WeightSlider({
  label,
  value,
  onChange,
  total
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  total?: number;
}) {
  const rawValue = Math.round(value * 100);
  const normalizedPct = total && total > 0 ? Math.round((value / total) * 100) : rawValue;

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-700 w-32 truncate">{label}</span>
      <input
        type="range"
        min="0"
        max="100"
        value={rawValue}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
      />
      <span className="text-sm font-semibold text-slate-800 w-16 text-right">
        {rawValue} → {normalizedPct}%
      </span>
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  currentSort,
  onSort,
  className = ''
}: {
  label: string;
  sortKey: string;
  currentSort: SortConfig | null;
  onSort: (key: string) => void;
  className?: string;
}) {
  const isActive = currentSort?.key === sortKey;
  const direction = isActive ? currentSort.direction : null;

  return (
    <th
      className={`px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider cursor-pointer hover:bg-slate-100 transition-colors select-none ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <div className="flex items-center gap-1">
        {label}
        <span className="text-slate-700">
          {direction === 'asc' ? <ChevronUp className="w-3 h-3" /> :
           direction === 'desc' ? <ChevronDown className="w-3 h-3" /> :
           <ChevronDown className="w-3 h-3 opacity-50" />}
        </span>
      </div>
    </th>
  );
}

function StatusBadge({ status }: { status: Project['status'] }) {
  const config = {
    draft: { bg: 'bg-slate-100', text: 'text-slate-700', label: 'Draft' },
    analyzing: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Analyzing' },
    countries_ready: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Countries Ready' },
    sites_ready: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Sites Ready' },
    complete: { bg: 'bg-green-100', text: 'text-green-700', label: 'Complete' }
  };
  const { bg, text, label } = config[status] || config.draft;

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${bg} ${text}`}>
      {label}
    </span>
  );
}

function FlagList({ flags, type }: { flags: string[]; type: 'red' | 'yellow' | 'green' }) {
  if (!flags.length) return null;

  const config = {
    red: { icon: XCircle, bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', iconColor: 'text-red-500' },
    yellow: { icon: AlertTriangle, bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', iconColor: 'text-amber-500' },
    green: { icon: CheckCircle2, bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', iconColor: 'text-emerald-500' }
  };
  const { icon: Icon, bg, border, text, iconColor } = config[type];

  return (
    <div className={`${bg} ${border} border rounded-lg p-3`}>
      <ul className="space-y-1">
        {flags.map((flag, i) => (
          <li key={i} className={`flex items-start gap-2 text-sm ${text}`}>
            <Icon className={`w-4 h-4 ${iconColor} flex-shrink-0 mt-0.5`} />
            {flag}
          </li>
        ))}
      </ul>
    </div>
  );
}

// =============================================================================
// NAVIGATION
// =============================================================================

function TopNav({ currentPath }: { currentPath: string }) {
  return (
    <nav className="bg-white border-b border-slate-200 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-blue-600" />
            <span className="text-xl font-bold text-slate-900">SiteSync</span>
          </div>
          <div className="flex gap-1">
            <a
              href="/"
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                currentPath === '/'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              Core
            </a>
            <a
              href="/sponsor"
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                currentPath === '/sponsor'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              Sponsor
            </a>
            <a
              href="/screener"
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                currentPath === '/screener'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              Screener
            </a>
          </div>
        </div>
      </div>
    </nav>
  );
}

function Breadcrumb({ items }: { items: Array<{ label: string; onClick?: () => void }> }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {items.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <ChevronRight className="w-4 h-4 text-slate-700" />}
          {item.onClick ? (
            <button
              onClick={item.onClick}
              className="text-blue-600 hover:text-blue-800 hover:underline"
            >
              {item.label}
            </button>
          ) : (
            <span className="text-slate-700 font-medium">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// =============================================================================
// VIEW 1: DASHBOARD
// =============================================================================

function DashboardView({
  projects,
  loading,
  error,
  onCreateProject,
  onSelectProject,
  onRetry
}: {
  projects: Project[];
  loading: boolean;
  error: string | null;
  onCreateProject: (name: string) => void;
  onSelectProject: (project: Project) => void;
  onRetry: () => void;
}) {
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [sortConfig, setSortConfig] = useState<SortConfig | null>({ key: 'updated_at', direction: 'desc' });

  const handleSort = useCallback((key: string) => {
    setSortConfig(current => {
      if (current?.key === key) {
        return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { key, direction: 'desc' };
    });
  }, []);

  const sortedProjects = useMemo(() => {
    if (!sortConfig) return projects;
    return [...projects].sort((a, b) => {
      const aVal = a[sortConfig.key as keyof Project];
      const bVal = b[sortConfig.key as keyof Project];
      if (aVal === undefined || bVal === undefined) return 0;
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortConfig.direction === 'asc' ? cmp : -cmp;
    });
  }, [projects, sortConfig]);

  const handleCreateProject = () => {
    if (newProjectName.trim()) {
      onCreateProject(newProjectName.trim());
      setNewProjectName('');
      setShowNewProject(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">SiteSync Screener</h1>
          <p className="text-slate-700 mt-1">AI-Powered Site Selection Intelligence</p>
        </div>
        <button
          onClick={() => setShowNewProject(true)}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold shadow-sm"
        >
          <Plus className="w-5 h-5" />
          New Project
        </button>
      </div>

      {/* New Project Modal */}
      {showNewProject && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-slate-900 mb-4">Create New Project</h2>
            <input
              type="text"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="Project name..."
              className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-slate-800"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
            />
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowNewProject(false)}
                className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                disabled={!newProjectName.trim()}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && <ErrorBanner message={error} onRetry={onRetry} />}

      {/* Projects Table */}
      {loading ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Indication</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Created</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Countries</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Shortlisted</th>
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3].map(i => <SkeletonRow key={i} columns={6} />)}
            </tbody>
          </table>
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No projects yet"
          description="Create your first project to start analyzing clinical trial sites worldwide."
          action={{ label: 'Create Project', onClick: () => setShowNewProject(true) }}
        />
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <SortableHeader label="Name" sortKey="name" currentSort={sortConfig} onSort={handleSort} />
                <SortableHeader label="Status" sortKey="status" currentSort={sortConfig} onSort={handleSort} />
                <SortableHeader label="Indication" sortKey="indication" currentSort={sortConfig} onSort={handleSort} />
                <SortableHeader label="Created" sortKey="created_at" currentSort={sortConfig} onSort={handleSort} />
                <SortableHeader label="Countries" sortKey="countries_analyzed" currentSort={sortConfig} onSort={handleSort} />
                <SortableHeader label="Shortlisted" sortKey="shortlisted_sites" currentSort={sortConfig} onSort={handleSort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sortedProjects.map(project => (
                <tr
                  key={project.id}
                  onClick={() => onSelectProject(project)}
                  className="hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-4">
                    <span className="font-semibold text-slate-900">{project.name}</span>
                  </td>
                  <td className="px-4 py-4">
                    <StatusBadge status={project.status} />
                  </td>
                  <td className="px-4 py-4 text-slate-700">
                    {project.indication || <span className="text-slate-700">—</span>}
                  </td>
                  <td className="px-4 py-4 text-slate-700">
                    {new Date(project.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-4 text-slate-700 font-medium">
                    {project.countries_analyzed ?? 0}
                  </td>
                  <td className="px-4 py-4">
                    <span className="flex items-center gap-1 text-slate-700">
                      <Star className="w-4 h-4 text-amber-500" />
                      {project.shortlisted_sites ?? 0}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// VIEW 2: PROTOCOL REVIEW
// =============================================================================

// Helper: Deduplicate treatment arms by normalizing and keeping longest
function deduplicateArms(arms: string[]): string[] {
  if (!arms || arms.length === 0) return [];

  const normalize = (s: string) => {
    // Remove special chars, lowercase, sort words alphabetically
    const words = s.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/).filter(Boolean).sort();
    return words.join(' ');
  };

  const groups: Map<string, string[]> = new Map();
  arms.forEach(arm => {
    const key = normalize(arm);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(arm);
  });

  // Keep the longest version from each group
  return Array.from(groups.values()).map(group =>
    group.reduce((longest, current) => current.length > longest.length ? current : longest)
  );
}

// Collapsible list component for progressive disclosure
function CollapsibleList({
  items,
  maxVisible = 3,
  renderItem,
  emptyMessage = "None extracted"
}: {
  items: string[] | undefined;
  maxVisible?: number;
  renderItem: (item: string, index: number) => React.ReactNode;
  emptyMessage?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  if (!items || items.length === 0) {
    return <li className="text-slate-700 italic">{emptyMessage}</li>;
  }

  const visibleItems = expanded ? items : items.slice(0, maxVisible);
  const hasMore = items.length > maxVisible;

  return (
    <>
      {visibleItems.map((item, i) => renderItem(item, i))}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium mt-2 flex items-center gap-1"
        >
          {expanded ? (
            <>Show less <ChevronUp className="w-4 h-4" /></>
          ) : (
            <>Show all {items.length} items <ChevronDown className="w-4 h-4" /></>
          )}
        </button>
      )}
    </>
  );
}

// Auto-expanding textarea for long fields
function AutoTextarea({
  value,
  onChange,
  placeholder,
  className = ""
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.max(40, textareaRef.current.scrollHeight) + 'px';
    }
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800 resize-none overflow-hidden ${className}`}
      rows={1}
    />
  );
}

function ProtocolReviewView({
  project,
  criteria,
  onUpload,
  onConfirm,
  onBack,
  loading,
  analyzing
}: {
  project: Project;
  criteria: ProtocolCriteria | null;
  onUpload: (file: File) => void;
  onConfirm: (criteria: ProtocolCriteria) => void;
  onBack: () => void;
  loading: boolean;
  analyzing: boolean;
}) {
  const [editedCriteria, setEditedCriteria] = useState<ProtocolCriteria | null>(criteria);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Expansion states for collapsible sections
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setEditedCriteria(criteria);
  }, [criteria]);

  // Get deduplicated arms
  const dedupedArms = useMemo(() => {
    return deduplicateArms(editedCriteria?.arms_description || []);
  }, [editedCriteria?.arms_description]);

  // Check if indication_detail is just repeating indication
  const getIndicationDetailValue = () => {
    const detail = editedCriteria?.indication_detail || '';
    const indication = editedCriteria?.indication || '';

    // If they're essentially the same, return empty to show placeholder
    if (detail && indication && detail.toLowerCase().trim() === indication.toLowerCase().trim()) {
      return '';
    }
    return detail;
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
    }
  };

  const updateCriteria = (key: keyof ProtocolCriteria, value: any) => {
    if (editedCriteria) {
      setEditedCriteria({ ...editedCriteria, [key]: value });
    }
  };

  // Upload State
  if (!criteria && !loading) {
    return (
      <div>
        <Breadcrumb items={[
          { label: 'Projects', onClick: onBack },
          { label: project.name }
        ]} />

        <h1 className="text-2xl font-bold text-slate-900 mb-2 mt-4">{project.name}</h1>
        <p className="text-slate-700 mb-8">Upload the study protocol PDF to begin analysis</p>

        <div
          className={`border-2 border-dashed rounded-xl p-16 text-center transition-colors ${
            dragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-slate-300 hover:border-slate-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="hidden"
          />
          <Upload className="w-12 h-12 text-slate-700 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-800 mb-2">
            Drop your protocol PDF here
          </h3>
          <p className="text-slate-700 mb-4">
            or click to browse your files
          </p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Select PDF
          </button>
          <p className="text-sm text-slate-700 mt-4">
            Our AI will extract key requirements to search for qualified sites worldwide.
          </p>
        </div>
      </div>
    );
  }

  // Loading State
  if (loading) {
    return (
      <div>
        <Breadcrumb items={[
          { label: 'Projects', onClick: onBack },
          { label: project.name }
        ]} />
        <h1 className="text-2xl font-bold text-slate-900 mb-8 mt-4">{project.name}</h1>
        <LoadingState messages={[
          'Uploading protocol...',
          'Extracting study requirements...',
          'Analyzing eligibility criteria...',
          'Processing equipment needs...'
        ]} />
      </div>
    );
  }

  // Analyzing State (after confirm)
  if (analyzing) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-slate-900 mb-8">{project.name}</h1>
        <LoadingState messages={[
          'Searching ClinicalTrials.gov...',
          'Analyzing country feasibility...',
          'Scoring regulatory environments...',
          'Ranking sites by capability...',
          'Generating recommendations...'
        ]} />
      </div>
    );
  }

  // Calculate extraction confidence percentage
  const getConfidencePercent = () => {
    const conf = editedCriteria?.extraction_confidence;
    if (conf === 'high') return 90;
    if (conf === 'medium') return 70;
    if (conf === 'low') return 50;
    return 75;
  };

  // Review State - Comprehensive 9-Section Layout
  return (
    <div>
      <Breadcrumb items={[
        { label: 'Projects', onClick: onBack },
        { label: project.name }
      ]} />

      <div className="flex items-center justify-between mb-6 mt-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
          <p className="text-slate-700 mt-1">Review extracted protocol data • All fields are editable</p>
        </div>
        <button
          onClick={() => editedCriteria && onConfirm(editedCriteria)}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
        >
          <Check className="w-5 h-5" />
          Confirm & Analyze
        </button>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Left Column - All Sections */}
        <div className="col-span-3 space-y-6">

          {/* Section 1: Study Identity & Design */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-blue-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              Study Identity & Design
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Study Title</label>
                <AutoTextarea
                  value={editedCriteria?.study_title || ''}
                  onChange={(value) => updateCriteria('study_title', value)}
                  placeholder="Full study title"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Protocol Number</label>
                <input type="text" value={editedCriteria?.protocol_number || ''} onChange={(e) => updateCriteria('protocol_number', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Sponsor</label>
                <input type="text" value={editedCriteria?.sponsor || ''} onChange={(e) => updateCriteria('sponsor', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Phase</label>
                <input type="text" value={editedCriteria?.phase || ''} onChange={(e) => updateCriteria('phase', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Therapeutic Area</label>
                <input type="text" value={editedCriteria?.therapeutic_area || ''} onChange={(e) => updateCriteria('therapeutic_area', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Design Type</label>
                <AutoTextarea
                  value={editedCriteria?.design_type || ''}
                  onChange={(value) => updateCriteria('design_type', value)}
                  placeholder="e.g., Randomized, double-blind, placebo-controlled"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Blinding</label>
                <input type="text" value={editedCriteria?.blinding || ''} onChange={(e) => updateCriteria('blinding', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Arm Count</label>
                <input type="number" value={editedCriteria?.arm_count || ''} onChange={(e) => updateCriteria('arm_count', parseInt(e.target.value) || null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Allocation Ratio</label>
                <input type="text" value={editedCriteria?.allocation_ratio || ''} onChange={(e) => updateCriteria('allocation_ratio', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., 1:1:1" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Control Type</label>
                <input type="text" value={editedCriteria?.control_type || ''} onChange={(e) => updateCriteria('control_type', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
            </div>
            <div className="mt-4">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                Treatment Arms ({dedupedArms.length || 0})
              </label>
              <div className="flex flex-wrap gap-2">
                <CollapsibleList
                  items={dedupedArms}
                  maxVisible={3}
                  emptyMessage="None extracted"
                  renderItem={(arm, i) => (
                    <span key={i} className="px-3 py-1 bg-blue-50 text-blue-800 rounded-full text-sm">{arm}</span>
                  )}
                />
              </div>
            </div>
          </div>

          {/* Section 2: Investigational Product */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-purple-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Pill className="w-5 h-5 text-purple-600" />
              Investigational Product
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Drug Name</label>
                <input type="text" value={editedCriteria?.drug_name || ''} onChange={(e) => updateCriteria('drug_name', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Drug Class</label>
                <input type="text" value={editedCriteria?.drug_class || ''} onChange={(e) => updateCriteria('drug_class', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., Monoclonal antibody" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Dose & Route</label>
                <input type="text" value={editedCriteria?.dose_and_route || ''} onChange={(e) => updateCriteria('dose_and_route', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., 300mg IV" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Dosing Frequency</label>
                <input type="text" value={editedCriteria?.dosing_frequency || ''} onChange={(e) => updateCriteria('dosing_frequency', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., Q2W" />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Administration Duration</label>
                <input type="text" value={editedCriteria?.administration_duration || ''} onChange={(e) => updateCriteria('administration_duration', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., 60-minute IV infusion" />
              </div>
            </div>
          </div>

          {/* Section 3: Patient Population */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-green-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-green-600" />
              Patient Population
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Indication</label>
                <input type="text" value={editedCriteria?.indication || ''} onChange={(e) => updateCriteria('indication', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800 font-medium" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Enrollment Target</label>
                <input type="number" value={editedCriteria?.enrollment_target || ''} onChange={(e) => updateCriteria('enrollment_target', parseInt(e.target.value) || null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div className="col-span-3">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Indication Detail</label>
                <AutoTextarea
                  value={getIndicationDetailValue()}
                  onChange={(value) => updateCriteria('indication_detail', value)}
                  placeholder="e.g., Moderate-to-severe active UC with Mayo score ≥6"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Age Range</label>
                <input type="text" value={editedCriteria?.age_range || ''} onChange={(e) => updateCriteria('age_range', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Sex Eligibility</label>
                <input type="text" value={editedCriteria?.sex_eligibility || ''} onChange={(e) => updateCriteria('sex_eligibility', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="All / Male / Female" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Patients per Site</label>
                <input type="number" value={editedCriteria?.patients_per_site || ''} onChange={(e) => updateCriteria('patients_per_site', parseInt(e.target.value) || null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
            </div>
          </div>

          {/* Section 4: Eligibility Criteria */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-teal-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-teal-600" />
              Eligibility Criteria
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Inclusion Criteria ({editedCriteria?.inclusion_criteria?.length || 0})
                </label>
                <ul className="space-y-2 text-sm text-slate-700">
                  <CollapsibleList
                    items={editedCriteria?.inclusion_criteria}
                    maxVisible={3}
                    emptyMessage="No inclusion criteria extracted"
                    renderItem={(c, i) => (
                      <li key={i} className="flex items-start gap-2 p-2 bg-emerald-50 rounded-lg">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                        <span>{c}</span>
                      </li>
                    )}
                  />
                </ul>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Exclusion Criteria ({editedCriteria?.exclusion_criteria?.length || 0})
                </label>
                <ul className="space-y-2 text-sm text-slate-700">
                  <CollapsibleList
                    items={editedCriteria?.exclusion_criteria}
                    maxVisible={3}
                    emptyMessage="No exclusion criteria extracted"
                    renderItem={(c, i) => (
                      <li key={i} className="flex items-start gap-2 p-2 bg-red-50 rounded-lg">
                        <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                        <span>{c}</span>
                      </li>
                    )}
                  />
                </ul>
              </div>
            </div>
          </div>

          {/* Section 5: Study Timeline */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-amber-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-amber-600" />
              Study Timeline & Visits
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Screening Period</label>
                <input type="text" value={editedCriteria?.screening_period || ''} onChange={(e) => updateCriteria('screening_period', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., Up to 4 weeks" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Treatment Duration</label>
                <input type="text" value={editedCriteria?.treatment_duration || ''} onChange={(e) => updateCriteria('treatment_duration', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., 12 weeks" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Follow-up Duration</label>
                <input type="text" value={editedCriteria?.follow_up_duration || ''} onChange={(e) => updateCriteria('follow_up_duration', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., 4 weeks safety" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Total Duration</label>
                <input type="text" value={editedCriteria?.total_duration || ''} onChange={(e) => updateCriteria('total_duration', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Total Visits</label>
                <input type="number" value={editedCriteria?.total_visits || ''} onChange={(e) => updateCriteria('total_visits', parseInt(e.target.value) || null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Visit Frequency</label>
                <input type="text" value={editedCriteria?.visit_frequency || ''} onChange={(e) => updateCriteria('visit_frequency', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., Every 2 weeks" />
              </div>
            </div>
          </div>

          {/* Section 6: Endpoints */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-emerald-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-emerald-600" />
              Endpoints
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Primary Endpoint</label>
                <AutoTextarea
                  value={editedCriteria?.primary_endpoint || ''}
                  onChange={(value) => updateCriteria('primary_endpoint', value)}
                  placeholder="e.g., Clinical remission at Week 12"
                  className="font-medium text-slate-800"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Primary Assessment Instrument</label>
                <input type="text" value={editedCriteria?.primary_assessment || ''} onChange={(e) => updateCriteria('primary_assessment', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800" placeholder="e.g., Mayo Score, RECIST 1.1" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Secondary Endpoints ({editedCriteria?.secondary_endpoints?.length || 0})
                </label>
                <ul className="space-y-1">
                  <CollapsibleList
                    items={editedCriteria?.secondary_endpoints}
                    maxVisible={3}
                    emptyMessage="None extracted"
                    renderItem={(ep, i) => (
                      <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                        <span className="text-slate-700">{i + 1}.</span> {ep}
                      </li>
                    )}
                  />
                </ul>
              </div>
            </div>
          </div>

          {/* Section 7: Site Requirements */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-indigo-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Stethoscope className="w-5 h-5 text-indigo-600" />
              Site Requirements
            </h2>
            <div className="grid grid-cols-3 gap-6">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Required Equipment ({editedCriteria?.required_equipment?.length || 0})
                </label>
                <ul className="space-y-1 text-sm text-slate-700">
                  {editedCriteria?.required_equipment?.length ? editedCriteria.required_equipment.map((e, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                      {e}
                    </li>
                  )) : <li className="text-slate-700 italic">None extracted</li>}
                </ul>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Required Staff ({editedCriteria?.required_staff?.length || 0})
                </label>
                <ul className="space-y-1 text-sm text-slate-700">
                  {editedCriteria?.required_staff?.length ? editedCriteria.required_staff.map((s, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                      {s}
                    </li>
                  )) : <li className="text-slate-700 italic">None extracted</li>}
                </ul>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Key Procedures ({editedCriteria?.procedures?.length || 0})
                </label>
                <ul className="space-y-1 text-sm text-slate-700">
                  <CollapsibleList
                    items={editedCriteria?.procedures}
                    maxVisible={5}
                    emptyMessage="None extracted"
                    renderItem={(p, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                        {p}
                      </li>
                    )}
                  />
                </ul>
              </div>
            </div>
          </div>

          {/* Section 8: Site Capability Flags */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-orange-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Building2 className="w-5 h-5 text-orange-600" />
              Site Capability Requirements
            </h2>
            <div className="grid grid-cols-4 gap-4">
              {/* Boolean flags */}
              <label className="flex items-center gap-2 p-3 border rounded-lg cursor-pointer hover:bg-slate-50">
                <input type="checkbox" checked={editedCriteria?.requires_endoscopy || false} onChange={(e) => updateCriteria('requires_endoscopy', e.target.checked)}
                  className="w-4 h-4 text-blue-600" />
                <span className="text-sm text-slate-700">Endoscopy</span>
              </label>
              <label className="flex items-center gap-2 p-3 border rounded-lg cursor-pointer hover:bg-slate-50">
                <input type="checkbox" checked={editedCriteria?.requires_infusion || false} onChange={(e) => updateCriteria('requires_infusion', e.target.checked)}
                  className="w-4 h-4 text-blue-600" />
                <span className="text-sm text-slate-700">Infusion Capability</span>
              </label>
              <label className="flex items-center gap-2 p-3 border rounded-lg cursor-pointer hover:bg-slate-50">
                <input type="checkbox" checked={editedCriteria?.requires_biopsy || false} onChange={(e) => updateCriteria('requires_biopsy', e.target.checked)}
                  className="w-4 h-4 text-blue-600" />
                <span className="text-sm text-slate-700">Biopsy</span>
              </label>
              <label className="flex items-center gap-2 p-3 border rounded-lg cursor-pointer hover:bg-slate-50">
                <input type="checkbox" checked={editedCriteria?.ecg_required || false} onChange={(e) => updateCriteria('ecg_required', e.target.checked)}
                  className="w-4 h-4 text-blue-600" />
                <span className="text-sm text-slate-700">ECG Required</span>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-4">
              {editedCriteria?.requires_imaging && editedCriteria.requires_imaging.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Imaging Required</label>
                  <div className="flex flex-wrap gap-2">
                    {editedCriteria.requires_imaging.map((img, i) => (
                      <span key={i} className="px-2 py-1 bg-orange-100 text-orange-800 rounded text-sm">{img}</span>
                    ))}
                  </div>
                </div>
              )}
              {editedCriteria?.storage_requirements && editedCriteria.storage_requirements.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Storage Requirements</label>
                  <div className="flex flex-wrap gap-2">
                    {editedCriteria.storage_requirements.map((s, i) => (
                      <span key={i} className="px-2 py-1 bg-cyan-100 text-cyan-800 rounded text-sm">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {editedCriteria?.lab_requirements && editedCriteria.lab_requirements.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Lab Requirements</label>
                  <div className="flex flex-wrap gap-2">
                    {editedCriteria.lab_requirements.map((l, i) => (
                      <span key={i} className="px-2 py-1 bg-violet-100 text-violet-800 rounded text-sm">{l}</span>
                    ))}
                  </div>
                </div>
              )}
              {editedCriteria?.sample_processing && editedCriteria.sample_processing.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">Sample Processing</label>
                  <div className="flex flex-wrap gap-2">
                    {editedCriteria.sample_processing.map((s, i) => (
                      <span key={i} className="px-2 py-1 bg-rose-100 text-rose-800 rounded text-sm">{s}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Section 9: Safety & Oversight */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 border-l-4 border-l-red-500">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-red-600" />
              Safety & Oversight
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center gap-2 p-3 border rounded-lg cursor-pointer hover:bg-slate-50">
                <input type="checkbox" checked={editedCriteria?.dsmb_required || false} onChange={(e) => updateCriteria('dsmb_required', e.target.checked)}
                  className="w-4 h-4 text-blue-600" />
                <span className="text-sm text-slate-700">DSMB/DMC Required</span>
              </label>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">Safety Monitoring</label>
                <AutoTextarea
                  value={editedCriteria?.safety_monitoring || ''}
                  onChange={(value) => updateCriteria('safety_monitoring', value)}
                  placeholder="e.g., Independent DSMB reviews every 30 patients"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Summary & Actions */}
        <div className="col-span-1">
          <div className="sticky top-6 space-y-6">
          {/* Confidence Card */}
          <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl shadow-lg p-6 text-white">
            <h3 className="text-lg font-semibold mb-4">Extraction Quality</h3>
            <div className="flex items-center justify-center">
              <div className="relative w-28 h-28">
                <svg className="w-28 h-28 transform -rotate-90">
                  <circle cx="56" cy="56" r="48" stroke="rgba(255,255,255,0.2)" strokeWidth="8" fill="none" />
                  <circle cx="56" cy="56" r="48" stroke="white" strokeWidth="8" fill="none" strokeLinecap="round"
                    strokeDasharray={`${getConfidencePercent() * 3.02} 302`} />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-bold">{getConfidencePercent()}%</span>
                </div>
              </div>
            </div>
            <p className="text-center text-blue-100 mt-4 text-sm">
              {editedCriteria?.extraction_confidence === 'high' ? 'High confidence extraction' :
               editedCriteria?.extraction_confidence === 'medium' ? 'Medium confidence - review carefully' :
               'Low confidence - manual review recommended'}
            </p>
            {editedCriteria?.extraction_warnings && editedCriteria.extraction_warnings.length > 0 && (
              <div className="mt-4 p-3 bg-white/10 rounded-lg">
                <p className="text-xs font-semibold text-blue-200 mb-1">Warnings:</p>
                <ul className="text-xs text-blue-100 space-y-1">
                  {editedCriteria.extraction_warnings.map((w, i) => (
                    <li key={i}>• {w}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Quick Stats */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-bold text-slate-900 mb-3">Quick Summary</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-700">Phase</span>
                <span className="font-semibold text-slate-900">{editedCriteria?.phase || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-700">Enrollment</span>
                <span className="font-semibold text-slate-900">{editedCriteria?.enrollment_target || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-700">Treatment</span>
                <span className="font-semibold text-slate-900">{editedCriteria?.treatment_duration || editedCriteria?.duration || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-700">Visits</span>
                <span className="font-semibold text-slate-900">{editedCriteria?.total_visits || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-700">Arms</span>
                <span className="font-semibold text-slate-900">{editedCriteria?.arm_count || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-700">Procedures</span>
                <span className="font-semibold text-slate-900">{editedCriteria?.procedures?.length || 0}</span>
              </div>
            </div>
          </div>

          {/* Key Capabilities */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-bold text-slate-900 mb-3">Key Site Needs</h3>
            <div className="flex flex-wrap gap-2">
              {editedCriteria?.requires_infusion && <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">Infusion</span>}
              {editedCriteria?.requires_endoscopy && <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">Endoscopy</span>}
              {editedCriteria?.requires_biopsy && <span className="px-2 py-1 bg-amber-100 text-amber-800 rounded-full text-xs">Biopsy</span>}
              {editedCriteria?.ecg_required && <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded-full text-xs">ECG</span>}
              {editedCriteria?.requires_imaging?.map((img, i) => (
                <span key={i} className="px-2 py-1 bg-orange-100 text-orange-800 rounded-full text-xs">{img}</span>
              ))}
            </div>
          </div>

          {/* Help Text */}
          <div className="bg-slate-50 rounded-xl p-5 border border-slate-200">
            <h3 className="font-semibold text-slate-800 mb-2 text-sm">What happens next?</h3>
            <ul className="space-y-1.5 text-xs text-slate-700">
              <li className="flex items-start gap-2">
                <Check className="w-3 h-3 text-emerald-500 flex-shrink-0 mt-0.5" />
                Search ClinicalTrials.gov for matching sites
              </li>
              <li className="flex items-start gap-2">
                <Check className="w-3 h-3 text-emerald-500 flex-shrink-0 mt-0.5" />
                Rank countries by feasibility
              </li>
              <li className="flex items-start gap-2">
                <Check className="w-3 h-3 text-emerald-500 flex-shrink-0 mt-0.5" />
                Identify top sites per country
              </li>
              <li className="flex items-start gap-2">
                <Check className="w-3 h-3 text-emerald-500 flex-shrink-0 mt-0.5" />
                Generate gap analysis
              </li>
            </ul>
          </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// DIMENSION BREAKDOWN COMPONENTS
// =============================================================================

// Score color utility
function getScoreColor(score: number): string {
  if (score >= 70) return '#16a34a'; // green-600
  if (score >= 40) return '#ca8a04'; // yellow-600
  return '#dc2626'; // red-600
}

function getScoreBgColor(score: number): string {
  if (score >= 70) return 'bg-green-50 border-green-200';
  if (score >= 40) return 'bg-yellow-50 border-yellow-200';
  return 'bg-red-50 border-red-200';
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

// Progress bar component for dimension scores
function DimensionProgressBar({ score, label }: { score: number; label: string }) {
  const color = getScoreColor(score);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${Math.min(100, score)}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-sm font-semibold w-12 text-right" style={{ color }}>
        {Math.round(score)}
      </span>
    </div>
  );
}

// Single dimension card
function DimensionCard({
  title,
  icon,
  weight,
  score,
  weightedContribution,
  explanation,
  children,
}: {
  title: string;
  icon: string;
  weight: number;
  score: number;
  weightedContribution: number;
  explanation: string;
  children?: React.ReactNode;
}) {
  const borderColor = score >= 70 ? 'border-green-200' : score >= 40 ? 'border-yellow-200' : 'border-red-200';

  return (
    <div className={`bg-white rounded-lg p-4 shadow-sm border ${borderColor}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <h4 className="font-semibold text-slate-800">{title}</h4>
          <span className="text-xs text-slate-700">({(weight * 100).toFixed(0)}%)</span>
        </div>
        <span className="text-sm font-medium text-slate-700">
          +{weightedContribution.toFixed(1)} pts
        </span>
      </div>
      <DimensionProgressBar score={score} label={title} />
      <p className="text-sm text-slate-700 mt-2">{explanation}</p>
      {children && <div className="mt-3 pt-3 border-t border-slate-100">{children}</div>}
    </div>
  );
}

// Main dimension breakdown cards component
function DimensionBreakdownCards({ country }: { country: CountryScore }) {
  const bd = country.dimension_breakdown;
  if (!bd) return null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-700">
          Score Breakdown
        </span>
        <span className="text-xs text-slate-700">Transparent scoring with data sources</span>
      </div>

      {/* Dimension Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Trial Experience */}
        {bd.trial_experience && (
          <DimensionCard
            title="Trial Experience"
            icon="📊"
            weight={bd.trial_experience.weight}
            score={bd.trial_experience.score}
            weightedContribution={bd.trial_experience.weighted_contribution}
            explanation={bd.trial_experience.explanation}
          >
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-700">Indication trials:</span>
                <span className="font-medium ml-1 text-slate-800">{bd.trial_experience.data.indication_trials}</span>
              </div>
              <div>
                <span className="text-slate-700">Total trials:</span>
                <span className="font-medium ml-1 text-slate-800">{bd.trial_experience.data.total_trials}</span>
              </div>
              <div className="col-span-2">
                <span className="text-slate-700">Percentile:</span>
                <span className="font-medium ml-1 text-slate-800">{bd.trial_experience.data.rank_position}</span>
              </div>
            </div>
          </DimensionCard>
        )}

        {/* Site Density */}
        {bd.site_density && (
          <DimensionCard
            title="Site Density"
            icon="🏥"
            weight={bd.site_density.weight}
            score={bd.site_density.score}
            weightedContribution={bd.site_density.weighted_contribution}
            explanation={bd.site_density.explanation}
          >
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-700">Sites:</span>
                <span className="font-medium ml-1 text-slate-800">{bd.site_density.data.site_count}</span>
              </div>
              {bd.site_density.data.sites_per_10m_pop && (
                <div>
                  <span className="text-slate-700">Per 10M:</span>
                  <span className="font-medium ml-1 text-slate-800">{bd.site_density.data.sites_per_10m_pop}</span>
                </div>
              )}
              <div className="col-span-2">
                <span className="text-slate-700">Percentile:</span>
                <span className="font-medium ml-1 text-slate-800">{bd.site_density.data.rank_position}</span>
              </div>
            </div>
          </DimensionCard>
        )}

        {/* Competition */}
        {bd.competition && (
          <DimensionCard
            title="Competition"
            icon="⚔️"
            weight={bd.competition.weight}
            score={bd.competition.score}
            weightedContribution={bd.competition.weighted_contribution}
            explanation={bd.competition.explanation}
          >
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-700">Competing:</span>
                <span className="font-medium ml-1 text-slate-800">{bd.competition.data.competing_trials} trials</span>
              </div>
              <div>
                <span className="text-slate-700">Pressure:</span>
                <span className={`font-medium ml-1 px-1.5 py-0.5 rounded ${
                  bd.competition.data.pressure_level === 'low' ? 'bg-green-100 text-green-700' :
                  bd.competition.data.pressure_level === 'moderate' ? 'bg-yellow-100 text-yellow-700' :
                  bd.competition.data.pressure_level === 'high' ? 'bg-orange-100 text-orange-700' :
                  bd.competition.data.pressure_level === 'extreme' ? 'bg-red-100 text-red-700' :
                  'bg-slate-100 text-slate-700'
                }`}>
                  {bd.competition.data.pressure_level}
                </span>
              </div>
              {bd.competition.data.addressable_pool && (
                <div className="col-span-2">
                  <span className="text-slate-700">Pool:</span>
                  <span className="font-medium ml-1 text-slate-800">~{bd.competition.data.addressable_pool.toLocaleString()}</span>
                </div>
              )}
            </div>
          </DimensionCard>
        )}

        {/* Regulatory */}
        {bd.regulatory && (
          <DimensionCard
            title="Regulatory"
            icon="📋"
            weight={bd.regulatory.weight}
            score={bd.regulatory.score}
            weightedContribution={bd.regulatory.weighted_contribution}
            explanation={bd.regulatory.explanation}
          >
            {bd.regulatory.data.regulatory_quality && (
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="text-center p-1 bg-slate-50 rounded">
                  <p className="font-semibold text-slate-800">{bd.regulatory.data.regulatory_quality.normalized}</p>
                  <p className="text-slate-700">RQ</p>
                </div>
                {bd.regulatory.data.logistics_index?.normalized && (
                  <div className="text-center p-1 bg-slate-50 rounded">
                    <p className="font-semibold text-slate-800">{bd.regulatory.data.logistics_index.normalized}</p>
                    <p className="text-slate-700">LPI</p>
                  </div>
                )}
                {bd.regulatory.data.health_expenditure && (
                  <div className="text-center p-1 bg-slate-50 rounded">
                    <p className="font-semibold text-slate-800">{bd.regulatory.data.health_expenditure.normalized}</p>
                    <p className="text-slate-700">HE</p>
                  </div>
                )}
              </div>
            )}
          </DimensionCard>
        )}

        {/* Prevalence */}
        {bd.prevalence && (
          <DimensionCard
            title="Prevalence"
            icon="👥"
            weight={bd.prevalence.weight}
            score={bd.prevalence.score}
            weightedContribution={bd.prevalence.weighted_contribution}
            explanation={bd.prevalence.explanation}
          >
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs">
                {bd.prevalence.data.prevalence_per_100k && (
                  <div>
                    <span className="text-slate-700">Rate:</span>
                    <span className="font-medium ml-1 text-slate-800">{bd.prevalence.data.prevalence_per_100k}/100k</span>
                  </div>
                )}
                {bd.prevalence.data.estimated_patients && (
                  <div>
                    <span className="text-slate-700">Est. patients:</span>
                    <span className="font-medium ml-1 text-slate-800">{bd.prevalence.data.estimated_patients.toLocaleString()}</span>
                  </div>
                )}
                {bd.prevalence.data.source && (
                  <div className="col-span-2">
                    <span className="text-slate-700">Source:</span>
                    <span className="font-medium ml-1 text-slate-700">{bd.prevalence.data.source}</span>
                    {bd.prevalence.data.data_year && <span className="text-slate-700"> ({bd.prevalence.data.data_year})</span>}
                  </div>
                )}
              </div>
              {/* Confidence badge */}
              {bd.prevalence.data.confidence && (
                <div className="flex items-center gap-2">
                  <span className={getPrevalenceConfidenceBadge(bd.prevalence.data.confidence).className}>
                    {getPrevalenceConfidenceBadge(bd.prevalence.data.confidence).text}
                  </span>
                </div>
              )}
            </div>
          </DimensionCard>
        )}
      </div>

      {/* Overall Calculation */}
      {bd.overall && (
        <div className="bg-slate-800 text-white rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-slate-300 text-sm">Overall Score Calculation:</span>
              <p className="font-mono text-xs text-slate-200 mt-1">{bd.overall.formula}</p>
            </div>
            <div className="text-right">
              <span className="text-3xl font-bold">{bd.overall.result.toFixed(1)}</span>
              <span className="text-slate-300 text-sm ml-1">/ 100</span>
            </div>
          </div>
        </div>
      )}

      {/* AI Analysis Section (supplementary) */}
      {(country.regulatory_summary || country.prevalence_estimate) && (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-700">
              AI Analysis
            </span>
            <span className="text-xs text-slate-700">GPT-4o insights</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {country.regulatory_summary && (
              <div className="bg-white rounded-lg p-4 shadow-sm border border-slate-200">
                <h4 className="font-semibold text-slate-800 mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  Regulatory Environment
                </h4>
                <p className="text-sm text-slate-700 leading-relaxed">{country.regulatory_summary}</p>
              </div>
            )}
            {country.prevalence_estimate && (
              <div className="bg-white rounded-lg p-4 shadow-sm border border-slate-200">
                <h4 className="font-semibold text-slate-800 mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                  Recruitment Feasibility
                </h4>
                <p className="text-sm text-slate-700 leading-relaxed">{country.prevalence_estimate}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* World Bank Indicators (keep for reference) */}
      {(country.regulatory_quality_raw != null || country.physician_density != null) && (
        <div className="mt-4 bg-white rounded-lg p-4 shadow-sm border border-slate-200">
          <h4 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            World Bank Indicators (Raw Data)
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {country.regulatory_quality_raw != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.regulatory_quality_raw.toFixed(2)}</p>
                <p className="text-xs text-slate-700">Regulatory Quality</p>
              </div>
            )}
            {country.physician_density != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.physician_density.toFixed(1)}</p>
                <p className="text-xs text-slate-700">Physicians/1,000</p>
              </div>
            )}
            {country.logistics_index != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.logistics_index.toFixed(2)}</p>
                <p className="text-xs text-slate-700">Logistics Index</p>
              </div>
            )}
            {country.health_expenditure_pct != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.health_expenditure_pct.toFixed(1)}%</p>
                <p className="text-xs text-slate-700">Health Exp/GDP</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Legacy country analysis (fallback for old projects without dimension_breakdown)
function LegacyCountryAnalysis({ country }: { country: CountryScore }) {
  return (
    <>
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-700">
          AI Analysis
        </span>
        <span className="text-xs text-slate-700">Powered by GPT-4o</span>
      </div>
      {/* World Bank Indicators (if available) */}
      {(country.regulatory_quality_raw != null || country.physician_density != null) && (
        <div className="mb-4 bg-white rounded-lg p-4 shadow-sm border border-slate-200">
          <h4 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            World Bank Indicators
            <span className="text-xs font-normal text-slate-700">(Data-driven regulatory score)</span>
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {country.regulatory_quality_raw != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.regulatory_quality_raw.toFixed(2)}</p>
                <p className="text-xs text-slate-700">Regulatory Quality</p>
                <p className="text-[10px] text-slate-700">(-2.5 to 2.5 scale)</p>
              </div>
            )}
            {country.physician_density != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.physician_density.toFixed(1)}</p>
                <p className="text-xs text-slate-700">Physicians/1,000</p>
                <p className="text-[10px] text-slate-700">Healthcare capacity</p>
              </div>
            )}
            {country.logistics_index != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.logistics_index.toFixed(2)}</p>
                <p className="text-xs text-slate-700">Logistics Index</p>
                <p className="text-[10px] text-slate-700">(1-5 scale)</p>
              </div>
            )}
            {country.health_expenditure_pct != null && (
              <div className="text-center p-2 bg-slate-50 rounded">
                <p className="text-lg font-bold text-slate-800">{country.health_expenditure_pct.toFixed(1)}%</p>
                <p className="text-xs text-slate-700">Health Exp/GDP</p>
                <p className="text-[10px] text-slate-700">System investment</p>
              </div>
            )}
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg p-4 shadow-sm border border-slate-200">
          <h4 className="font-semibold text-slate-800 mb-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            Regulatory Environment
          </h4>
          <p className="text-sm text-slate-700 leading-relaxed">
            {country.regulatory_summary || 'No regulatory analysis available. Run country ranking with AI analysis enabled.'}
          </p>
        </div>
        <div className="bg-white rounded-lg p-4 shadow-sm border border-slate-200">
          <h4 className="font-semibold text-slate-800 mb-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500"></span>
            Recruitment Feasibility
          </h4>
          {/* Data-driven prevalence display */}
          {country.prevalence_per_100k != null ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-700">Prevalence:</span>
                <span className="font-medium text-slate-800">
                  {country.prevalence_per_100k.toLocaleString(undefined, {maximumFractionDigits: 1})} per 100,000
                  {country.prevalence_source && (
                    <span className="text-xs text-slate-700 ml-1">({country.prevalence_source})</span>
                  )}
                </span>
              </div>
              {country.estimated_patients != null && (
                <div className="flex justify-between">
                  <span className="text-slate-700">Estimated patients:</span>
                  <span className="font-medium text-slate-800">{country.estimated_patients.toLocaleString()}</span>
                </div>
              )}
              {country.addressable_pool != null && (
                <div className="flex justify-between">
                  <span className="text-slate-700">Addressable pool:</span>
                  <span className="font-medium text-slate-800">
                    ~{country.addressable_pool.toLocaleString()}
                  </span>
                </div>
              )}
              {country.competition_demand != null && (
                <div className="flex justify-between">
                  <span className="text-slate-700">Competing demand:</span>
                  <span className="font-medium text-slate-800">
                    {country.actively_recruiting} trials × 50 = {country.competition_demand.toLocaleString()} patients
                  </span>
                </div>
              )}
              {country.competition_ratio != null && (
                <div className="flex justify-between items-center">
                  <span className="text-slate-700">Competition pressure:</span>
                  <span className={`font-medium px-2 py-0.5 rounded text-xs ${
                    country.competition_pressure === 'low' ? 'bg-green-100 text-green-800' :
                    country.competition_pressure === 'moderate' ? 'bg-yellow-100 text-yellow-800' :
                    country.competition_pressure === 'high' ? 'bg-orange-100 text-orange-800' :
                    country.competition_pressure === 'extreme' ? 'bg-red-100 text-red-800' :
                    'bg-slate-100 text-slate-800'
                  }`}>
                    {(country.competition_ratio * 100).toFixed(2)}% — {(country.competition_pressure || 'unknown').toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-700 leading-relaxed">
              {country.prevalence_estimate || 'No prevalence data available. Run country ranking with AI analysis enabled.'}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

// =============================================================================
// VIEW 3: COUNTRY RANKING
// =============================================================================

function CountryRankingView({
  project,
  countries,
  weights,
  loading,
  error,
  onWeightsChange,
  onRefresh,
  onViewCountryDetail,
  onBack,
  onRetry,
  onViewProtocol
}: {
  project: Project;
  countries: CountryScore[];
  weights: CountryWeights;
  loading: boolean;
  error: string | null;
  onWeightsChange: (weights: CountryWeights) => void;
  onRefresh: () => void;
  onViewCountryDetail: (country: CountryScore) => void;
  onBack: () => void;
  onRetry: () => void;
  onViewProtocol: () => void;
}) {
  const [showWeights, setShowWeights] = useState(false);
  const [localWeights, setLocalWeights] = useState(weights);
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: 'composite_score', direction: 'desc' });
  const [filterRegion, setFilterRegion] = useState<string>('all');
  const [minScore, setMinScore] = useState(0);

  const handleSort = useCallback((key: string) => {
    setSortConfig(current => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc'
    }));
  }, []);

  const filteredCountries = useMemo(() => {
    return countries.filter(c => c.composite_score >= minScore);
  }, [countries, minScore]);

  const sortedCountries = useMemo(() => {
    return [...filteredCountries].sort((a, b) => {
      const aVal = a[sortConfig.key as keyof CountryScore] as number;
      const bVal = b[sortConfig.key as keyof CountryScore] as number;
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortConfig.direction === 'asc' ? cmp : -cmp;
    });
  }, [filteredCountries, sortConfig]);

  const totalTrials = useMemo(() => countries.reduce((sum, c) => sum + c.total_trials, 0), [countries]);
  const totalCompeting = useMemo(() => countries.reduce((sum, c) => sum + c.actively_recruiting, 0), [countries]);

  const handleWeightChange = (key: keyof CountryWeights, value: number) => {
    setLocalWeights(prev => ({ ...prev, [key]: value }));
  };

  const handleApplyWeights = () => {
    onWeightsChange(localWeights);
    onRefresh();
  };

  const handleResetWeights = () => {
    const defaultWeights: CountryWeights = {
      trial_experience: 0.30,
      site_density: 0.25,
      competition: 0.20,
      regulatory: 0.15,
      prevalence: 0.10
    };
    setLocalWeights(defaultWeights);
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Breadcrumb items={[
          { label: 'Projects', onClick: onBack },
          { label: project.name, onClick: onViewProtocol },
          { label: 'Countries' }
        ]} />
        <div className="flex items-center justify-between mt-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Countries</h1>
            <p className="text-slate-700">
              {project.name} • {project.indication} • {project.phase}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onViewProtocol}
              className="flex items-center gap-2 px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg font-medium"
            >
              <FileText className="w-4 h-4" />
              View Protocol
            </button>
            <button
              onClick={() => setShowWeights(!showWeights)}
              className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg hover:bg-slate-50 text-slate-700 font-medium"
            >
              <Filter className="w-4 h-4" />
              Adjust Weights
              {showWeights ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
          <p className="text-sm text-slate-700 uppercase tracking-wider">Countries</p>
          <p className="text-2xl font-bold text-slate-900">{countries.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
          <p className="text-sm text-slate-700 uppercase tracking-wider">Total Trials</p>
          <p className="text-2xl font-bold text-slate-900">{totalTrials.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
          <p className="text-sm text-slate-700 uppercase tracking-wider">Competing Trials</p>
          <p className="text-2xl font-bold text-amber-600">{totalCompeting.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
          <p className="text-sm text-slate-700 uppercase tracking-wider">Top Score</p>
          <p className="text-2xl font-bold text-emerald-600">
            {countries.length > 0 ? Math.round(Math.max(...countries.map(c => c.composite_score))) : 0}
          </p>
        </div>
      </div>

      {/* Weights Panel */}
      {showWeights && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-900">Country Scoring Weights</h3>
            <button
              onClick={handleResetWeights}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Reset to Default
            </button>
          </div>
          {(() => {
            const countryTotal = localWeights.trial_experience + localWeights.site_density + localWeights.competition + localWeights.regulatory + localWeights.prevalence;
            return (
              <>
                <div className="grid grid-cols-2 gap-6">
                  <WeightSlider
                    label="Trial Experience"
                    value={localWeights.trial_experience}
                    onChange={(v) => handleWeightChange('trial_experience', v)}
                    total={countryTotal}
                  />
                  <WeightSlider
                    label="Site Density"
                    value={localWeights.site_density}
                    onChange={(v) => handleWeightChange('site_density', v)}
                    total={countryTotal}
                  />
                  <WeightSlider
                    label="Competition (inverse)"
                    value={localWeights.competition}
                    onChange={(v) => handleWeightChange('competition', v)}
                    total={countryTotal}
                  />
                  <WeightSlider
                    label="Regulatory"
                    value={localWeights.regulatory}
                    onChange={(v) => handleWeightChange('regulatory', v)}
                    total={countryTotal}
                  />
                  <WeightSlider
                    label="Prevalence"
                    value={localWeights.prevalence}
                    onChange={(v) => handleWeightChange('prevalence', v)}
                    total={countryTotal}
                  />
                </div>
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-200">
                  <p className="text-sm text-slate-700">
                    Raw Total: {Math.round(countryTotal * 100)} (normalized to 100%)
                  </p>
                  <button
                    onClick={handleApplyWeights}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                  >
                    Recalculate
                  </button>
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-700">Min Score:</span>
          <input
            type="range"
            min="0"
            max="100"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-32 accent-blue-600"
          />
          <span className="text-sm font-semibold text-slate-800 w-8">{minScore}</span>
        </div>
        <div className="text-sm text-slate-700">
          Showing {sortedCountries.length} of {countries.length} countries
        </div>
      </div>

      {/* Error State */}
      {error && <ErrorBanner message={error} onRetry={onRetry} />}

      {/* Loading State */}
      {loading ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase">Rank</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase">Country</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase">Score</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase">Trials</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase">Sites</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase">Competing</th>
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3, 4, 5].map(i => <SkeletonRow key={i} columns={6} />)}
            </tbody>
          </table>
        </div>
      ) : countries.length === 0 ? (
        <EmptyState
          icon={Globe}
          title="No countries found"
          description="No countries matched the protocol criteria. Try adjusting the requirements."
        />
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider w-16">Rank</th>
                <SortableHeader label="Country" sortKey="country_name" currentSort={sortConfig} onSort={handleSort} />
                <SortableHeader label="Score" sortKey="composite_score" currentSort={sortConfig} onSort={handleSort} className="w-24" />
                <SortableHeader label="Trials" sortKey="indication_trials" currentSort={sortConfig} onSort={handleSort} className="w-20" />
                <SortableHeader label="Sites" sortKey="site_count" currentSort={sortConfig} onSort={handleSort} className="w-20" />
                <SortableHeader label="Competing" sortKey="actively_recruiting" currentSort={sortConfig} onSort={handleSort} className="w-24" />
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider">Sub-scores</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sortedCountries.map((country, index) => (
                <tr
                  key={`${country.country_code}-${index}`}
                  className="hover:bg-slate-50 transition-colors"
                >
                  <td className="px-4 py-4 text-slate-700 font-medium">{index + 1}</td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onViewCountryDetail(country)}
                        className="font-semibold text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                      >
                        {country.country_name}
                      </button>
                      <span className="text-slate-700 text-sm">{country.country_code}</span>
                      {(country.regulatory_summary || country.prevalence_estimate) && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-600" title="AI analysis available">
                          AI
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <ScoreBadge score={country.composite_score} />
                  </td>
                  <td className="px-4 py-4 font-medium text-slate-800">{country.indication_trials}</td>
                  <td className="px-4 py-4 font-medium text-slate-800">{country.site_count}</td>
                  <td className="px-4 py-4">
                    <span className={`font-medium ${country.actively_recruiting > 10 ? 'text-amber-600' : 'text-slate-700'}`}>
                      {country.actively_recruiting}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex gap-2">
                      <div className="flex flex-col items-center" title="Trial Experience (30%)">
                        <div className="w-9 h-6 flex items-center justify-center rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {Math.round(country.trial_experience_score)}
                        </div>
                        <span className="text-[10px] text-slate-700 mt-0.5">Exp</span>
                      </div>
                      <div className="flex flex-col items-center" title="Site Density (25%)">
                        <div className="w-9 h-6 flex items-center justify-center rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {Math.round(country.site_density_score)}
                        </div>
                        <span className="text-[10px] text-slate-700 mt-0.5">Sites</span>
                      </div>
                      <div className="flex flex-col items-center" title="Competition (20%) - Lower is better">
                        <div className="w-9 h-6 flex items-center justify-center rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {Math.round(country.competition_score)}
                        </div>
                        <span className="text-[10px] text-slate-700 mt-0.5">Comp</span>
                      </div>
                      <div className="flex flex-col items-center" title="Regulatory (15%)">
                        <div className="w-9 h-6 flex items-center justify-center rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {Math.round(country.regulatory_score)}
                        </div>
                        <span className="text-[10px] text-slate-700 mt-0.5">Reg</span>
                      </div>
                      <div className="flex flex-col items-center" title="Disease Prevalence (10%)">
                        <div className="w-9 h-6 flex items-center justify-center rounded text-xs font-semibold bg-slate-100 text-slate-700">
                          {Math.round(country.prevalence_score)}
                        </div>
                        <span className="text-[10px] text-slate-700 mt-0.5">Prev</span>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MAIN PAGE COMPONENT
// =============================================================================

export default function ScreenerPage() {
  // View state
  const [currentView, setCurrentView] = useState<ScreenerView>('dashboard');

  // Data state
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [protocolCriteria, setProtocolCriteria] = useState<ProtocolCriteria | null>(null);
  const [countries, setCountries] = useState<CountryScore[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<CountryScore | null>(null);
  const [sites, setSites] = useState<SiteScore[]>([]);
  const [selectedSite, setSelectedSite] = useState<SiteScore | null>(null);
  const [shortlist, setShortlist] = useState<SiteScore[]>([]);

  // Weight state
  const [countryWeights, setCountryWeights] = useState<CountryWeights>({
    trial_experience: 0.30,
    site_density: 0.25,
    competition: 0.20,
    regulatory: 0.15,
    prevalence: 0.10
  });
  const [siteWeights, setSiteWeights] = useState<SiteWeights>({
    experience: 0.35,
    pi_strength: 0.20,
    capacity: 0.20,
    compliance: 0.15,
    protocol_match: 0.10
  });
  const [scoringPreset, setScoringPreset] = useState<string>('phase_3');

  // Loading states
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await screenerApi.getProjects();
      setProjects(data.projects || []);
    } catch (err) {
      setError('Failed to load projects. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async (name: string) => {
    setLoading(true);
    setError(null);
    try {
      const project = await screenerApi.createProject(name);
      setProjects(prev => [project, ...prev]);
      setActiveProject(project);
      setCurrentView('protocol_review');
    } catch (err) {
      setError('Failed to create project. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectProject = async (project: Project) => {
    setLoading(true);
    setError(null);

    try {
      // Fetch full project data including protocol_criteria
      const fullProject = await screenerApi.getProject(project.id);
      setActiveProject(fullProject);

      // Set protocol criteria from fetched data (persists across navigation)
      if (fullProject.protocol_criteria) {
        setProtocolCriteria(fullProject.protocol_criteria);
      } else {
        setProtocolCriteria(null);
      }

      // Load saved site weights from project
      if (fullProject.site_weights) {
        setSiteWeights(fullProject.site_weights);
      }

      // Load saved scoring preset from project extra_data
      if (fullProject.extra_data?.scoring_preset) {
        setScoringPreset(fullProject.extra_data.scoring_preset);
      } else {
        // Default to phase_3 if not set
        setScoringPreset('phase_3');
      }

      // Navigate based on status
      if (fullProject.status === 'draft') {
        setCurrentView('protocol_review');
      } else if (fullProject.status === 'analyzing') {
        setCurrentView('protocol_review');
      } else {
        // Load countries and go to ranking
        await loadCountries(fullProject.id);
        setCurrentView('country_ranking');
      }
    } catch (err) {
      setError('Failed to load project. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleUploadProtocol = async (file: File) => {
    if (!activeProject) return;

    setLoading(true);
    setError(null);
    try {
      const result = await screenerApi.uploadProtocol(activeProject.id, file);
      setProtocolCriteria(result.extracted_criteria);
      setActiveProject(prev => prev ? { ...prev, status: 'analyzing' } : null);
    } catch (err) {
      setError('Failed to upload protocol. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmProtocol = async (criteria: ProtocolCriteria) => {
    if (!activeProject) return;

    setAnalyzing(true);
    setError(null);
    try {
      await screenerApi.confirmProtocol(activeProject.id, criteria);
      setProtocolCriteria(criteria);
      setActiveProject(prev => prev ? {
        ...prev,
        status: 'countries_ready',
        indication: criteria.indication,
        therapeutic_area: criteria.therapeutic_area,
        phase: criteria.phase
      } : null);

      // Load countries
      await loadCountries(activeProject.id);
      setCurrentView('country_ranking');
    } catch (err) {
      setError('Failed to analyze protocol. Please try again.');
      console.error(err);
    } finally {
      setAnalyzing(false);
    }
  };

  const loadCountries = async (projectId: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await screenerApi.getCountries(projectId);
      setCountries(data.countries || []);
    } catch (err) {
      setError('Failed to load countries. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshCountries = async () => {
    if (!activeProject) return;

    setLoading(true);
    setError(null);
    try {
      const data = await screenerApi.refreshCountries(activeProject.id, countryWeights);
      setCountries(data.countries || []);
    } catch (err) {
      setError('Failed to refresh countries. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCountry = async (country: CountryScore) => {
    if (!activeProject) return;

    setSelectedCountry(country);
    setLoading(true);
    setError(null);
    try {
      const data = await screenerApi.getSitesInCountry(activeProject.id, country.country_code);
      setSites(data.sites || []);

      // Load shortlist
      const shortlistData = await screenerApi.getShortlist(activeProject.id);
      setShortlist(shortlistData.sites || []);

      setCurrentView('site_ranking');
    } catch (err) {
      setError('Failed to load sites. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleViewCountryDetail = (country: CountryScore) => {
    setSelectedCountry(country);
    setCurrentView('country_detail');
  };

  const handleSelectSite = async (site: SiteScore) => {
    if (!activeProject) return;

    setSelectedSite(site);
    setCurrentView('site_detail');

    // Optionally load full details
    try {
      const fullSite = await screenerApi.getSiteDetail(activeProject.id, site.site_id);
      setSelectedSite(fullSite);
    } catch (err) {
      console.error('Failed to load full site details:', err);
    }
  };

  const handleToggleShortlist = async (site: SiteScore) => {
    if (!activeProject) return;

    const isCurrentlyShortlisted = shortlist.some(s => s.site_id === site.site_id);
    const action = isCurrentlyShortlisted ? 'remove' : 'add';

    try {
      await screenerApi.toggleShortlist(activeProject.id, site.site_id, action);

      if (action === 'add') {
        setShortlist(prev => [...prev, { ...site, is_shortlisted: true }]);
        setSites(prev => prev.map(s => s.site_id === site.site_id ? { ...s, is_shortlisted: true } : s));
        if (selectedSite?.site_id === site.site_id) {
          setSelectedSite(prev => prev ? { ...prev, is_shortlisted: true } : null);
        }
      } else {
        setShortlist(prev => prev.filter(s => s.site_id !== site.site_id));
        setSites(prev => prev.map(s => s.site_id === site.site_id ? { ...s, is_shortlisted: false } : s));
        if (selectedSite?.site_id === site.site_id) {
          setSelectedSite(prev => prev ? { ...prev, is_shortlisted: false } : null);
        }
      }
    } catch (err) {
      setError('Failed to update shortlist. Please try again.');
      console.error(err);
    }
  };

  const handleBackToProjects = () => {
    setActiveProject(null);
    setProtocolCriteria(null);
    setCountries([]);
    setSites([]);
    setSelectedCountry(null);
    setSelectedSite(null);
    setShortlist([]);
    setCurrentView('dashboard');
    loadProjects();
  };

  const handleBackToCountries = () => {
    setSites([]);
    setSelectedCountry(null);
    setSelectedSite(null);
    setCurrentView('country_ranking');
  };

  // Refresh project data (including extra_data) and countries
  const handleRefreshProjectAndCountries = async () => {
    if (!activeProject) return;
    try {
      const fullProject = await screenerApi.getProject(activeProject.id);
      setActiveProject(fullProject);

      // Update weights from refreshed project data
      if (fullProject.site_weights) {
        setSiteWeights(fullProject.site_weights);
      }
      if (fullProject.extra_data?.scoring_preset) {
        setScoringPreset(fullProject.extra_data.scoring_preset);
      }

      await loadCountries(activeProject.id);
    } catch (err) {
      console.error('Failed to refresh project data:', err);
    }
  };

  const handleBackToSites = () => {
    setSelectedSite(null);
    setCurrentView('site_ranking');
  };

  // Handle site weights change - persists to backend then refreshes
  const handleSiteWeightsChange = async (weights: SiteWeights, presetName?: string) => {
    if (!activeProject) return;

    try {
      // Update local state immediately for responsiveness
      setSiteWeights(weights);
      if (presetName) {
        setScoringPreset(presetName);
      }

      // Persist to backend
      await screenerApi.updateSiteWeights(activeProject.id, weights, presetName);

      // Refresh sites to get recalculated scores
      if (selectedCountry) {
        const data = await screenerApi.getSitesInCountry(activeProject.id, selectedCountry.country_code);
        setSites(data.sites || []);
      }
    } catch (err) {
      console.error('Failed to update site weights:', err);
      setError('Failed to update weights. Please try again.');
    }
  };

  // Handle preset change
  const handleScoringPresetChange = (preset: string) => {
    const presetWeights: Record<string, SiteWeights> = {
      phase_1: { experience: 0.25, pi_strength: 0.25, capacity: 0.20, compliance: 0.20, protocol_match: 0.10 },
      phase_2: { experience: 0.30, pi_strength: 0.25, capacity: 0.20, compliance: 0.15, protocol_match: 0.10 },
      phase_3: { experience: 0.35, pi_strength: 0.20, capacity: 0.20, compliance: 0.15, protocol_match: 0.10 },
    };

    if (preset !== 'custom' && presetWeights[preset]) {
      handleSiteWeightsChange(presetWeights[preset], preset);
    } else {
      setScoringPreset('custom');
    }
  };

  // Render current view
  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardView
            projects={projects}
            loading={loading}
            error={error}
            onCreateProject={handleCreateProject}
            onSelectProject={handleSelectProject}
            onRetry={loadProjects}
          />
        );

      case 'protocol_review':
        return (
          <ProtocolReviewView
            project={activeProject!}
            criteria={protocolCriteria}
            onUpload={handleUploadProtocol}
            onConfirm={handleConfirmProtocol}
            onBack={handleBackToProjects}
            loading={loading}
            analyzing={analyzing}
          />
        );

      case 'country_ranking':
        return (
          <CountryRankingView
            project={activeProject!}
            countries={countries}
            weights={countryWeights}
            loading={loading}
            error={error}
            onWeightsChange={setCountryWeights}
            onRefresh={handleRefreshCountries}
            onViewCountryDetail={handleViewCountryDetail}
            onBack={handleBackToProjects}
            onRetry={() => loadCountries(activeProject!.id)}
            onViewProtocol={() => setCurrentView('protocol_review')}
          />
        );

      case 'country_detail':
        return (
          <CountryDetailView
            country={selectedCountry!}
            projectId={activeProject!.id}
            projectName={activeProject?.name}
            extraData={activeProject?.extra_data}
            onBack={handleBackToCountries}
            onViewSites={(_countryCode: string) => handleSelectCountry(selectedCountry!)}
            onRefresh={handleRefreshProjectAndCountries}
          />
        );

      case 'site_ranking':
        // Extract country benchmarks from TrialTrove analytics
        const trialtroveData = activeProject?.extra_data?.trialtrove_analytics?.[selectedCountry?.country_code || ''];
        const countryBenchmarks = trialtroveData?.analytics || trialtroveData || undefined;

        return (
          <SiteRankingView
            project={activeProject!}
            country={selectedCountry!}
            sites={sites}
            shortlist={shortlist}
            weights={siteWeights}
            scoringPreset={scoringPreset}
            loading={loading}
            error={error}
            countryBenchmarks={countryBenchmarks}
            onWeightsChange={(weights) => handleSiteWeightsChange(weights, scoringPreset)}
            onPresetChange={handleScoringPresetChange}
            onRefresh={() => handleSelectCountry(selectedCountry!)}
            onSelectSite={handleSelectSite}
            onToggleShortlist={handleToggleShortlist}
            onBack={handleBackToCountries}
            onRetry={() => handleSelectCountry(selectedCountry!)}
            onViewProtocol={() => setCurrentView('protocol_review')}
            onBackToProjects={handleBackToProjects}
          />
        );

      case 'site_detail':
        return (
          <SiteDetailView
            project={activeProject!}
            site={selectedSite}
            onToggleShortlist={handleToggleShortlist}
            onBack={handleBackToSites}
            loading={loading}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <TopNav currentPath="/screener" />
      <main className="max-w-7xl mx-auto px-6 py-8">
        {renderView()}
      </main>
    </div>
  );
}
