"use client";

import React, { useState } from "react";

// Types
interface SiteResult {
  id: string;
  facility_name: string;
  city: string;
  state: string;
  country: string;
  total_trials: number;
  completed_trials: number;
  active_trials: number;
  completion_rate: number;
  therapeutic_experience: Record<string, number>;
  phase_experience: Record<string, number>;
  top_investigators: Array<{
    name: string;
    trial_count: number;
    primary_role: string;
  }>;
  competing_trials: number;
  has_demo_profile: boolean;
  data_source: string;
}

interface CategoryScore {
  category: string;
  weight: number;
  score: number;
  confidence: string;
  verification_status: string;
  details: string[];
  data_source: string;
}

interface Flag {
  severity: string;
  title: string;
  details: string;
  risk_assessment: string;
  recommendation: string;
  data_source: string;
  related_category: string;
}

interface SiteAssessment {
  site_id: string;
  facility_name: string;
  city: string;
  state: string;
  country: string;
  overall_score: number;
  confidence: string;
  category_scores: CategoryScore[];
  red_flags: Flag[];
  yellow_flags: Flag[];
  gray_flags: Flag[];
  recommendation: string;
  suggested_questions: string[];
  data_sources: string[];
  has_demo_profile: boolean;
  assessed_at: string;
}

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SponsorPage() {
  // Search state
  const [condition, setCondition] = useState("NASH");
  const [state, setState] = useState("California");
  const [minTrials, setMinTrials] = useState(2);
  const [searching, setSearching] = useState(false);
  const [sites, setSites] = useState<SiteResult[]>([]);
  const [selectedSites, setSelectedSites] = useState<Set<string>>(new Set());

  // Assessment state
  const [assessing, setAssessing] = useState(false);
  const [assessments, setAssessments] = useState<SiteAssessment[]>([]);
  const [assessmentSummary, setAssessmentSummary] = useState<any>(null);

  // Protocol state
  const [protocolName, setProtocolName] = useState("NASH Phase 3 Trial");
  const [protocolPhase, setProtocolPhase] = useState("Phase 3");
  const [targetEnrollment, setTargetEnrollment] = useState(200);

  // UI state
  const [activeTab, setActiveTab] = useState<"search" | "results">("search");
  const [expandedAssessment, setExpandedAssessment] = useState<string | null>(null);
  const [expandedFlags, setExpandedFlags] = useState<Set<string>>(new Set());

  // Search for sites
  const searchSites = async () => {
    setSearching(true);
    try {
      const response = await fetch(`${API_BASE}/sponsor/search-sites`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          condition,
          state: state || undefined,
          min_trials: minTrials,
        }),
      });

      if (!response.ok) throw new Error("Search failed");

      const data = await response.json();
      setSites(data.sites || []);
      setSelectedSites(new Set());
    } catch (error) {
      console.error("Search error:", error);
      alert("Failed to search sites. Check console for details.");
    } finally {
      setSearching(false);
    }
  };

  // Toggle site selection
  const toggleSiteSelection = (siteId: string) => {
    const newSelected = new Set(selectedSites);
    if (newSelected.has(siteId)) {
      newSelected.delete(siteId);
    } else {
      newSelected.add(siteId);
    }
    setSelectedSites(newSelected);
  };

  // Select all sites
  const selectAllSites = () => {
    if (selectedSites.size === sites.length) {
      setSelectedSites(new Set());
    } else {
      setSelectedSites(new Set(sites.map((s) => s.id)));
    }
  };

  // Assess selected sites
  const assessSites = async () => {
    if (selectedSites.size === 0) {
      alert("Please select at least one site to assess");
      return;
    }

    setAssessing(true);
    try {
      const selectedSiteData = sites.filter((s) => selectedSites.has(s.id));

      const response = await fetch(`${API_BASE}/sponsor/assess-sites`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          protocol: {
            protocol_name: protocolName,
            therapeutic_area: condition,
            phase: protocolPhase,
            target_enrollment: targetEnrollment,
            required_equipment: ["FibroScan", "MRI", "Ultrasound"],
          },
          site_ids: Array.from(selectedSites),
          sites_data: selectedSiteData,
        }),
      });

      if (!response.ok) throw new Error("Assessment failed");

      const data = await response.json();
      setAssessments(data.assessments || []);
      setAssessmentSummary(data.comparison_summary);
      setActiveTab("results");
    } catch (error) {
      console.error("Assessment error:", error);
      alert("Failed to assess sites. Check console for details.");
    } finally {
      setAssessing(false);
    }
  };

  // Toggle flag expansion
  const toggleFlagExpansion = (flagId: string) => {
    const newExpanded = new Set(expandedFlags);
    if (newExpanded.has(flagId)) {
      newExpanded.delete(flagId);
    } else {
      newExpanded.add(flagId);
    }
    setExpandedFlags(newExpanded);
  };

  // Render score bar
  const ScoreBar = ({ score, size = "normal" }: { score: number; size?: "normal" | "small" }) => {
    const getColor = (s: number) => {
      if (s >= 85) return "bg-green-500";
      if (s >= 70) return "bg-yellow-500";
      if (s >= 50) return "bg-orange-500";
      return "bg-red-500";
    };

    return (
      <div className={`w-full bg-gray-200 rounded-full ${size === "small" ? "h-2" : "h-3"}`}>
        <div
          className={`${getColor(score)} rounded-full ${size === "small" ? "h-2" : "h-3"} transition-all`}
          style={{ width: `${score}%` }}
        />
      </div>
    );
  };

  // Render confidence badge
  const ConfidenceBadge = ({ confidence }: { confidence: string }) => {
    const colors: Record<string, string> = {
      HIGH: "bg-green-100 text-green-800",
      MODERATE: "bg-yellow-100 text-yellow-800",
      LOW: "bg-gray-100 text-gray-600",
    };
    return (
      <span className={`px-2 py-1 text-xs rounded-full ${colors[confidence] || colors.LOW}`}>
        {confidence}
      </span>
    );
  };

  // Render verification status
  const VerificationBadge = ({ status }: { status: string }) => {
    const icons: Record<string, string> = {
      VERIFIED: "checkmark",
      PARTIAL: "warning",
      UNVERIFIED: "circle",
    };
    const colors: Record<string, string> = {
      VERIFIED: "text-green-600",
      PARTIAL: "text-yellow-600",
      UNVERIFIED: "text-gray-400",
    };
    const displayIcons: Record<string, string> = {
      VERIFIED: "V",
      PARTIAL: "!",
      UNVERIFIED: "O",
    };
    return (
      <span className={`${colors[status] || colors.UNVERIFIED} font-bold`}>
        {displayIcons[status] || "O"} {status}
      </span>
    );
  };

  // Render flag component
  const FlagCard = ({ flag, index }: { flag: Flag; index: number }) => {
    const flagId = `${flag.severity}-${index}`;
    const isExpanded = expandedFlags.has(flagId);

    const severityStyles: Record<string, { bg: string; border: string; icon: string }> = {
      RED: { bg: "bg-red-50", border: "border-red-300", icon: "RED" },
      YELLOW: { bg: "bg-yellow-50", border: "border-yellow-300", icon: "YLW" },
      GRAY: { bg: "bg-gray-50", border: "border-gray-300", icon: "GRY" },
    };

    const style = severityStyles[flag.severity] || severityStyles.GRAY;

    return (
      <div className={`${style.bg} border ${style.border} rounded-lg mb-2`}>
        <button
          onClick={() => toggleFlagExpansion(flagId)}
          className="w-full px-4 py-3 flex items-center justify-between text-left"
        >
          <span className="font-medium">
            [{style.icon}] {flag.title}
          </span>
          <span className="text-gray-500">{isExpanded ? "[-]" : "[+]"}</span>
        </button>

        {isExpanded && (
          <div className="px-4 pb-4 border-t border-gray-200 mt-2 pt-3">
            <div className="space-y-2 text-sm">
              <div>
                <span className="font-medium text-gray-700">Details:</span>
                <p className="text-gray-600 mt-1">{flag.details}</p>
              </div>
              <div>
                <span className="font-medium text-gray-700">Risk Assessment:</span>
                <p className="text-gray-600 mt-1">{flag.risk_assessment}</p>
              </div>
              <div>
                <span className="font-medium text-gray-700">Recommendation:</span>
                <p className="text-gray-600 mt-1">{flag.recommendation}</p>
              </div>
              <div className="text-xs text-gray-500 mt-2">
                Data Source: {flag.data_source} | Category: {flag.related_category}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">SiteSync Sponsor View</h1>
              <p className="text-sm text-gray-500">AI-Powered Site Feasibility Assessment</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500">Powered by ClinicalTrials.gov</span>
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                A
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab("search")}
              className={`px-4 py-3 font-medium border-b-2 transition-colors ${
                activeTab === "search"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Site Search
            </button>
            <button
              onClick={() => setActiveTab("results")}
              disabled={assessments.length === 0}
              className={`px-4 py-3 font-medium border-b-2 transition-colors ${
                activeTab === "results"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              } ${assessments.length === 0 ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              Assessment Results {assessments.length > 0 && `(${assessments.length})`}
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Search Tab */}
        {activeTab === "search" && (
          <div className="space-y-6">
            {/* Search Form */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Search Clinical Trial Sites</h2>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Therapeutic Area
                  </label>
                  <select
                    value={condition}
                    onChange={(e) => setCondition(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2"
                  >
                    <option value="NASH">NASH / NAFLD</option>
                    <option value="Hepatitis">Hepatitis</option>
                    <option value="Cirrhosis">Cirrhosis</option>
                    <option value="Diabetes">Diabetes</option>
                    <option value="Obesity">Obesity</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    State (Optional)
                  </label>
                  <input
                    type="text"
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    placeholder="e.g., California"
                    className="w-full border rounded-lg px-3 py-2"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Minimum Trials
                  </label>
                  <input
                    type="number"
                    value={minTrials}
                    onChange={(e) => setMinTrials(parseInt(e.target.value) || 1)}
                    min={1}
                    className="w-full border rounded-lg px-3 py-2"
                  />
                </div>

                <div className="flex items-end">
                  <button
                    onClick={searchSites}
                    disabled={searching}
                    className="w-full bg-blue-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
                  >
                    {searching ? "Searching..." : "Search Sites"}
                  </button>
                </div>
              </div>
            </div>

            {/* Protocol Configuration */}
            {sites.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold mb-4">Protocol Configuration</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Protocol Name
                    </label>
                    <input
                      type="text"
                      value={protocolName}
                      onChange={(e) => setProtocolName(e.target.value)}
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Phase</label>
                    <select
                      value={protocolPhase}
                      onChange={(e) => setProtocolPhase(e.target.value)}
                      className="w-full border rounded-lg px-3 py-2"
                    >
                      <option value="Phase 1">Phase 1</option>
                      <option value="Phase 2">Phase 2</option>
                      <option value="Phase 3">Phase 3</option>
                      <option value="Phase 4">Phase 4</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Target Enrollment
                    </label>
                    <input
                      type="number"
                      value={targetEnrollment}
                      onChange={(e) => setTargetEnrollment(parseInt(e.target.value) || 100)}
                      className="w-full border rounded-lg px-3 py-2"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Site Results */}
            {sites.length > 0 && (
              <div className="bg-white rounded-lg shadow">
                <div className="px-6 py-4 border-b flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">
                      Found {sites.length} Sites
                    </h2>
                    <p className="text-sm text-gray-500">
                      {selectedSites.size} selected for assessment
                    </p>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={selectAllSites}
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      {selectedSites.size === sites.length ? "Deselect All" : "Select All"}
                    </button>
                    <button
                      onClick={assessSites}
                      disabled={selectedSites.size === 0 || assessing}
                      className="bg-green-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-green-700 disabled:opacity-50"
                    >
                      {assessing ? "Assessing..." : `Assess ${selectedSites.size} Site(s)`}
                    </button>
                  </div>
                </div>

                <div className="divide-y max-h-[600px] overflow-y-auto">
                  {sites.slice(0, 50).map((site) => (
                    <div
                      key={site.id}
                      className={`px-6 py-4 flex items-center gap-4 hover:bg-gray-50 cursor-pointer ${
                        selectedSites.has(site.id) ? "bg-blue-50" : ""
                      }`}
                      onClick={() => toggleSiteSelection(site.id)}
                    >
                      <input
                        type="checkbox"
                        checked={selectedSites.has(site.id)}
                        onChange={() => {}}
                        className="w-5 h-5 rounded"
                      />

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-gray-900 truncate">
                            {site.facility_name}
                          </h3>
                          {site.has_demo_profile && (
                            <span className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded-full">
                              * Demo Profile
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-500">
                          {site.city}, {site.state}
                          {site.top_investigators?.[0] && (
                            <span> | PI: {site.top_investigators[0].name}</span>
                          )}
                        </p>
                      </div>

                      <div className="text-right text-sm">
                        <div className="font-medium">{site.total_trials} trials</div>
                        <div className="text-gray-500">
                          {(site.completion_rate * 100).toFixed(0)}% completion
                        </div>
                      </div>

                      <div className="text-right text-sm w-24">
                        <div className="text-gray-500">{site.active_trials} active</div>
                        {site.competing_trials > 0 && (
                          <div className="text-yellow-600">
                            {site.competing_trials} competing
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {sites.length > 50 && (
                  <div className="px-6 py-3 bg-gray-50 text-sm text-gray-500 text-center">
                    Showing first 50 of {sites.length} sites
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Results Tab */}
        {activeTab === "results" && assessments.length > 0 && (
          <div className="space-y-6">
            {/* Summary Card */}
            {assessmentSummary && (
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold mb-4">Assessment Summary</h2>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-3xl font-bold text-gray-900">
                      {assessments.length}
                    </div>
                    <div className="text-sm text-gray-500">Sites Assessed</div>
                  </div>
                  <div className="text-center p-4 bg-green-50 rounded-lg">
                    <div className="text-3xl font-bold text-green-600">
                      {assessmentSummary.highest_score}
                    </div>
                    <div className="text-sm text-gray-500">Highest Score</div>
                  </div>
                  <div className="text-center p-4 bg-blue-50 rounded-lg">
                    <div className="text-3xl font-bold text-blue-600">
                      {assessmentSummary.avg_score?.toFixed(0)}
                    </div>
                    <div className="text-sm text-gray-500">Average Score</div>
                  </div>
                  <div className="text-center p-4 bg-yellow-50 rounded-lg">
                    <div className="text-3xl font-bold text-yellow-600">
                      {assessmentSummary.sites_with_yellow_flags}
                    </div>
                    <div className="text-sm text-gray-500">Yellow Flags</div>
                  </div>
                  <div className="text-center p-4 bg-red-50 rounded-lg">
                    <div className="text-3xl font-bold text-red-600">
                      {assessmentSummary.sites_with_red_flags}
                    </div>
                    <div className="text-sm text-gray-500">Red Flags</div>
                  </div>
                </div>
              </div>
            )}

            {/* Individual Assessments */}
            {assessments.map((assessment, idx) => (
              <div key={assessment.site_id} className="bg-white rounded-lg shadow overflow-hidden">
                {/* Site Header */}
                <div
                  className="px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
                  onClick={() =>
                    setExpandedAssessment(
                      expandedAssessment === assessment.site_id ? null : assessment.site_id
                    )
                  }
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="text-2xl font-bold text-gray-400">#{idx + 1}</div>
                      <div>
                        <h3 className="text-lg font-semibold flex items-center gap-2">
                          {assessment.facility_name}
                          {assessment.has_demo_profile && (
                            <span className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded-full">
                              * Complete Profile
                            </span>
                          )}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {assessment.city}, {assessment.state}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <div className="text-3xl font-bold">{assessment.overall_score}</div>
                        <div className="text-sm text-gray-500">/100</div>
                      </div>
                      <div className="w-32">
                        <ScoreBar score={assessment.overall_score} />
                        <div className="mt-1 text-center">
                          <ConfidenceBadge confidence={assessment.confidence} />
                        </div>
                      </div>
                      <div className="text-sm">
                        {assessment.red_flags.length > 0 && (
                          <div className="text-red-600">[RED] {assessment.red_flags.length}</div>
                        )}
                        {assessment.yellow_flags.length > 0 && (
                          <div className="text-yellow-600">
                            [YLW] {assessment.yellow_flags.length}
                          </div>
                        )}
                        {assessment.gray_flags.length > 0 && (
                          <div className="text-gray-500">
                            [GRY] {assessment.gray_flags.length} Data Gaps
                          </div>
                        )}
                      </div>
                      <div className="text-gray-400">
                        {expandedAssessment === assessment.site_id ? "[-]" : "[+]"}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Details */}
                {expandedAssessment === assessment.site_id && (
                  <div className="px-6 py-4 space-y-6">
                    {/* Category Scores */}
                    <div>
                      <h4 className="font-semibold mb-3">Category Breakdown</h4>
                      <div className="space-y-3">
                        {assessment.category_scores.map((cat) => (
                          <div key={cat.category} className="flex items-center gap-4">
                            <div className="w-48 font-medium text-sm">{cat.category}</div>
                            <div className="flex-1">
                              <ScoreBar score={cat.score} size="small" />
                            </div>
                            <div className="w-16 text-right font-medium">{cat.score}/100</div>
                            <div className="w-32">
                              <VerificationBadge status={cat.verification_status} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Flags */}
                    {(assessment.red_flags.length > 0 ||
                      assessment.yellow_flags.length > 0 ||
                      assessment.gray_flags.length > 0) && (
                      <div>
                        <h4 className="font-semibold mb-3">Flags & Risks</h4>
                        {assessment.red_flags.map((flag, i) => (
                          <FlagCard key={`red-${i}`} flag={flag} index={i} />
                        ))}
                        {assessment.yellow_flags.map((flag, i) => (
                          <FlagCard key={`yellow-${i}`} flag={flag} index={i} />
                        ))}
                        {assessment.gray_flags.map((flag, i) => (
                          <FlagCard key={`gray-${i}`} flag={flag} index={i} />
                        ))}
                      </div>
                    )}

                    {/* AI Recommendation */}
                    <div className="bg-blue-50 rounded-lg p-4">
                      <h4 className="font-semibold mb-2">AI Recommendation</h4>
                      <p className="text-gray-700">{assessment.recommendation}</p>
                    </div>

                    {/* Suggested Questions */}
                    {assessment.suggested_questions.length > 0 && (
                      <div>
                        <h4 className="font-semibold mb-2">
                          Suggested Questions for Site Call
                        </h4>
                        <ul className="list-disc list-inside space-y-1 text-gray-700">
                          {assessment.suggested_questions.map((q, i) => (
                            <li key={i}>{q}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Data Sources */}
                    <div className="text-sm text-gray-500 border-t pt-4">
                      <span className="font-medium">Data Sources:</span>{" "}
                      {assessment.data_sources.join(", ")}
                      <span className="mx-2">|</span>
                      <span className="font-medium">Assessed:</span>{" "}
                      {new Date(assessment.assessed_at).toLocaleString()}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Actions */}
            <div className="flex justify-end gap-4">
              <button
                onClick={() => setActiveTab("search")}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Back to Search
              </button>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Export to Excel
              </button>
              <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                Download All Reports
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
