// app/page.tsx - Full integrated SiteSync frontend
'use client';

import React, { useState, useEffect } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, ChevronRight, Loader2, BarChart3, Users, ClipboardCheck, Sliders, Send, ArrowLeft, Building2, Clock, Target, TrendingUp, AlertTriangle } from 'lucide-react';

// API Configuration - connects to your FastAPI backend
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Real API service connecting to your FastAPI backend
const api = {
  // Get sites from backend
  async getSites() {
    try {
      const response = await fetch(`${API_URL}/sites`);
      if (!response.ok) throw new Error('Failed to fetch sites');
      return await response.json();
    } catch (error) {
      console.error('Error fetching sites:', error);
      return { data: [] };
    }
  },

  // Get protocols/studies
  async getProtocols() {
    try {
      const response = await fetch(`${API_URL}/protocols`);
      if (!response.ok) throw new Error('Failed to fetch protocols');
      return await response.json();
    } catch (error) {
      console.error('Error fetching protocols:', error);
      return { data: [] };
    }
  },

  // Main feature: Upload protocol and get AI analysis
  async uploadProtocol(file: File, siteId: number) {
    console.log('API uploadProtocol called with:', file.name, file.size, 'bytes, siteId:', siteId);

    try {
      const formData = new FormData();
      formData.append('protocol_file', file);  // Make sure the field name matches backend
      console.log('FormData created, sending request to:', `${API_URL}/feasibility/process-protocol?site_id=${siteId}`);

      const response = await fetch(`${API_URL}/feasibility/process-protocol?site_id=${siteId}`, {
        method: 'POST',
        body: formData,
        // Don't set Content-Type header - let browser set it with boundary
      });

      console.log('Response received:', response.status, response.statusText);

      const text = await response.text();
      console.log('Raw response text:', text);

      if (!response.ok) {
        console.error('Response not OK:', response.status, text);
        throw new Error(`Upload failed: ${response.statusText} - ${text}`);
      }

      let data;
      try {
        data = JSON.parse(text);
        console.log('Parsed response data:', data);
      } catch (parseError) {
        console.error('Failed to parse response:', text);
        throw new Error('Invalid response from server');
      }

      // Transform backend response to match our UI needs
      const result = {
        success: data.success,
        data: {
          protocol_id: data.data?.protocol_id,
          assessment_id: data.data?.assessment_id || Math.random(),
          protocol_name: data.data?.protocol_name || file.name.replace('.pdf', ''),
          nct_id: data.data?.nct_id || 'NCT-PENDING',
          match_score: data.data?.match_score || 0,
          auto_filled_count: data.data?.completion_stats?.fields_completed || 0,
          total_questions: data.data?.completion_stats?.total_fields || 40,
          completion_percentage: data.data?.completion_stats?.completion_percentage || 0,
          score_breakdown: data.data?.score_details?.category_scores || {
            'Patient Population': 35,
            'Study Procedures': 30,
            'Operational Capacity': 20,
            'Equipment': 15
          },
          flags: data.data?.score_details?.flags || [],
          form_responses: {
            objective: data.data?.form_data?.objective || [],
            subjective: data.data?.form_data?.subjective || []
          },
          raw_extraction: data.data?.extracted_data || {}
        }
      };

      console.log('Transformed result:', result);
      return result;
    } catch (error) {
      console.error('Upload exception:', error);
      throw error;
    }
  },

  // Get form template structure
  async getFormTemplate() {
    try {
      const response = await fetch(`${API_URL}/feasibility/form-templates`);
      if (!response.ok) throw new Error('Failed to fetch form template');
      return await response.json();
    } catch (error) {
      console.error('Error fetching form template:', error);
      return null;
    }
  },

  // Save/update form responses
  async updateResponses(assessmentId: number, responses: any) {
    try {
      const response = await fetch(`${API_URL}/feasibility/save-responses`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          assessment_id: assessmentId,
          responses: responses
        })
      });

      if (!response.ok) throw new Error('Failed to save responses');
      return await response.json();
    } catch (error) {
      console.error('Error saving responses:', error);
      throw error;
    }
  },

  // Score protocol for site
  async scoreProtocol(protocolId: number, siteId: number) {
    try {
      const response = await fetch(`${API_URL}/protocols/${protocolId}/score?site_id=${siteId}`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Failed to score protocol');
      return await response.json();
    } catch (error) {
      console.error('Error scoring protocol:', error);
      return null;
    }
  }
};

// Type definitions
interface Site {
  id: number;
  name: string;
  address: string;
  emr: string;
  capabilities?: string;
}

interface Protocol {
  id: number;
  name: string;
  nct_id: string;
  sponsor: string;
  phase: string;
  indication: string;
  target_enrollment?: number;
}

interface AssessmentData {
  protocol_id: number;
  assessment_id: number;
  protocol_name: string;
  nct_id: string;
  match_score: number;
  auto_filled_count: number;
  total_questions: number;
  completion_percentage: number;
  score_breakdown: Record<string, number>;
  flags: Array<{level: string, message: string}>;
  form_responses: {
    objective: Array<FormResponse>;
    subjective: Array<FormResponse>;
  };
  raw_extraction?: any;
}

interface FormResponse {
  key: string;
  question: string;
  value: string;
  locked: boolean;
  confidence?: number;
  required?: boolean;
}

export default function SiteSync() {
  // State management
  const [currentScreen, setCurrentScreen] = useState<string>('inbox');
  const [sites, setSites] = useState<Site[]>([]);
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [selectedSite, setSelectedSite] = useState<Site | null>(null);
  const [selectedStudy, setSelectedStudy] = useState<any>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [assessmentData, setAssessmentData] = useState<AssessmentData | null>(null);
  const [formResponses, setFormResponses] = useState<any>(null);
  const [whatIfScore, setWhatIfScore] = useState(86);
  const [processingStage, setProcessingStage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [subjectiveAnswers, setSubjectiveAnswers] = useState<Record<string, string>>({});

  // Load initial data
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setIsLoading(true);

        // Load sites
        const sitesData = await api.getSites();
        console.log('Sites loaded:', sitesData);
        setSites(sitesData);

        // Auto-select first site if available and not already selected
        if (sitesData && sitesData.length > 0 && !selectedSite) {
          console.log('Auto-selecting site:', sitesData[0]);
          setSelectedSite(sitesData[0]);
        }

        // Load protocols
        const protocolsData = await api.getProtocols();
        console.log('Protocols loaded:', protocolsData);
        setProtocols(protocolsData);

      } catch (error) {
        console.error('Failed to load initial data:', error);
        setError('Failed to load data from server');
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, []); // Empty dependency array - only run once on mount

  // Handle file upload and processing
  const handleFileUpload = async (file: File) => {
    console.log('Starting file upload:', file.name, file.size, 'bytes');

    if (!selectedSite) {
      console.error('No site selected');
      setError('No site selected');
      return;
    }

    console.log('Selected site:', selectedSite);

    setUploadedFile(file);
    setIsProcessing(true);
    setError(null);
    setCurrentScreen('processing');

    // Show processing stages
    const stages = [
      'Uploading protocol document...',
      'AI extracting protocol data...',
      'Mapping to site capabilities...',
      'Calculating feasibility score...'
    ];

    try {
      console.log('Starting processing stages...');

      // Show each stage with delay for UX
      for (let i = 0; i < stages.length; i++) {
        console.log('Processing stage:', stages[i]);
        setProcessingStage(stages[i]);

        if (i === 0) {
          console.log('Calling uploadProtocol API...');
          // Start actual upload after first stage shows
          const uploadPromise = api.uploadProtocol(file, selectedSite.id);

          // Show remaining stages while upload happens
          for (let j = 1; j < stages.length; j++) {
            await new Promise(resolve => setTimeout(resolve, 800));
            setProcessingStage(stages[j]);
          }

          console.log('Waiting for upload result...');
          // Wait for actual result
          const result = await uploadPromise;
          console.log('Upload result received:', result);

          if (result.success) {
            console.log('Upload successful, processing data...');
            setAssessmentData(result.data);
            setFormResponses(result.data.form_responses);
            setWhatIfScore(result.data.match_score);
            setCurrentScreen('score');
          } else {
            console.error('Upload failed:', result);
            throw new Error(result.error || 'Processing failed');
          }
        }
      }
    } catch (error: any) {
      console.error('Upload exception:', error);
      setError(error.message || 'Failed to process protocol. Please check the file and try again.');
      setCurrentScreen('intake');
    } finally {
      console.log('Upload process finished');
      setIsProcessing(false);
    }
  };

  // Inbox Screen - List of studies
  const InboxScreen = () => (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-semibold text-green-600">SiteSync</h1>
            <span className="text-gray-500">
              {selectedSite ? selectedSite.name : 'Loading...'}
            </span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <Clock className="w-4 h-4" />
            <span>{protocols.length} studies available</span>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
            <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {/* Study Cards */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Available Studies for Feasibility Assessment</h2>

        <div className="space-y-4">
          {/* If we have protocols from backend, show them */}
          {protocols.length > 0 ? (
            protocols.map((protocol) => (
              <div
                key={protocol.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => {
                  setSelectedStudy({
                    id: protocol.id,
                    name: protocol.name,
                    nct: protocol.nct_id,
                    sponsor: protocol.sponsor,
                    phase: protocol.phase,
                    indication: protocol.indication
                  });
                  setCurrentScreen('intake');
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <h3 className="text-lg font-medium text-gray-900">{protocol.name}</h3>
                      <span className="px-2 py-1 text-xs font-medium text-white bg-green-500 rounded-full">New</span>
                    </div>
                    <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                      <span>📋 {protocol.nct_id}</span>
                      <span>🏢 {protocol.sponsor}</span>
                      <span>📊 {protocol.phase}</span>
                      <span>🔬 {protocol.indication}</span>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-400" />
                </div>
              </div>
            ))
          ) : (
            // Fallback demo card if no protocols in database
            <div
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => {
                setSelectedStudy({
                  name: "Upload New Protocol",
                  nct: "NCT-NEW",
                  sponsor: "Any Sponsor"
                });
                setCurrentScreen('intake');
              }}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <h3 className="text-lg font-medium text-gray-900">Upload New Protocol for Assessment</h3>
                    <span className="px-2 py-1 text-xs font-medium text-white bg-blue-500 rounded-full">Quick Start</span>
                  </div>
                  <div className="mt-2 text-sm text-gray-500">
                    Upload any protocol PDF to see AI-powered feasibility scoring
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </div>
            </div>
          )}
        </div>

        {/* Site selector if multiple sites */}
        {sites.length > 1 && (
          <div className="mt-8 p-4 bg-blue-50 rounded-lg">
            <label className="block text-sm font-medium text-gray-700 mb-2">Active Site</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              value={selectedSite?.id}
              onChange={(e) => {
                const site = sites.find(s => s.id === parseInt(e.target.value));
                setSelectedSite(site || null);
              }}
            >
              {sites.map(site => (
                <option key={site.id} value={site.id}>
                  {site.name} - {site.address}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );

  // Intake Screen - Upload protocol
  const IntakeScreen = () => {
    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type === 'application/pdf') {
        handleFileUpload(file);
      }
    };

    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <button onClick={() => setCurrentScreen('inbox')} className="hover:text-gray-900">
              Inbox
            </button>
            <ChevronRight className="w-4 h-4" />
            <span className="text-gray-900">{selectedStudy?.name || 'New Protocol'}</span>
          </div>
        </div>

        {/* Upload Section */}
        <div className="max-w-3xl mx-auto px-6 py-12">
          {/* Show selected site */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-blue-700">
              <strong>Selected Site:</strong> {selectedSite?.name || 'No site selected'}
            </p>
            {selectedSite && (
              <p className="text-xs text-blue-600 mt-1">
                {selectedSite.address} • EMR: {selectedSite.emr}
              </p>
            )}
            {!selectedSite && (
              <p className="text-red-600 mt-2">⚠️ Please refresh the page to load site data</p>
            )}
          </div>

          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Upload Protocol Document</h2>
          <p className="text-gray-600 mb-8">Upload a protocol PDF to get instant AI-powered feasibility scoring</p>

          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-green-500 transition-colors cursor-pointer bg-white"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => {
              const input = document.createElement('input');
              input.type = 'file';
              input.accept = '.pdf';
              input.onchange = (e: any) => {
                const file = e.target.files[0];
                if (file) handleFileUpload(file);
              };
              input.click();
            }}
          >
            <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">
              Drop Protocol PDF here
            </p>
            <p className="text-gray-500 mb-4">or click to browse</p>
            <button className="mt-6 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
              Select Protocol PDF
            </button>
            <p className="text-xs text-gray-500 mt-4">
              Supports: Clinical trial protocols, feasibility questionnaires, study synopses
            </p>
          </div>

          {/* Backend status */}
          <div className="mt-8 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-medium text-gray-900 mb-2">🔌 Backend Status</h3>
            <p className="text-sm text-gray-600">
              Site: {selectedSite?.name || 'Not selected'}<br/>
              EMR: {selectedSite?.emr || 'Unknown'}<br/>
              API: {API_URL}
            </p>
          </div>
        </div>
      </div>
    );
  };

  // Processing Screen - Show while AI works
  const ProcessingScreen = () => (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="mb-8">
          <Loader2 className="w-16 h-16 text-green-600 animate-spin mx-auto" />
        </div>
        <h2 className="text-2xl font-semibold text-gray-900 mb-2">AI Processing Protocol</h2>
        <p className="text-gray-600">{processingStage}</p>
        <p className="text-xs text-gray-500 mt-4">Using GPT-4 to extract and analyze protocol requirements...</p>
      </div>
    </div>
  );

  // Score Screen - Show results
  const ScoreScreen = () => {
    if (!assessmentData) return null;

    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">{assessmentData.protocol_name}</h2>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setCurrentScreen('autofill')}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Review Auto-Filled Answers
              </button>
              <button
                onClick={() => setCurrentScreen('whatif')}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                What-if Analysis
              </button>
            </div>
          </div>
        </div>

        {/* Score Display */}
        <div className="max-w-4xl mx-auto px-6 py-8">
          <div className="bg-white rounded-lg shadow-lg p-8 mb-6">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-32 h-32 rounded-full bg-green-100 mb-4">
                <div className="text-center">
                  <div className="text-4xl font-bold text-green-600">{assessmentData.match_score}</div>
                  <div className="text-sm text-green-700">/100</div>
                </div>
              </div>
              <h3 className="text-2xl font-semibold text-gray-900">
                {assessmentData.match_score >= 80 ? 'Strong Fit' :
                 assessmentData.match_score >= 60 ? 'Good Fit' : 'Needs Review'}
              </h3>
              <p className="text-gray-600 mt-2">
                Auto-filled {assessmentData.auto_filled_count} of {assessmentData.total_questions} fields ({assessmentData.completion_percentage}% complete)
              </p>
            </div>

            {/* Score Breakdown */}
            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Score Contributors</h4>
              {Object.entries(assessmentData.score_breakdown).map(([category, value]) => (
                <div key={category} className="flex items-center space-x-3">
                  <span className="text-sm text-gray-600 w-48">{category}</span>
                  <div className="flex-1 bg-gray-200 rounded-full h-4">
                    <div
                      className="bg-green-600 h-4 rounded-full transition-all duration-500"
                      style={{ width: `${value}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-900 w-12">{value}%</span>
                </div>
              ))}
            </div>

            {/* Flags */}
            {assessmentData.flags && assessmentData.flags.length > 0 && (
              <div className="mt-6 p-4 bg-yellow-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">⚠️ Flags & Gaps</h4>
                <ul className="space-y-1">
                  {assessmentData.flags.map((flag, idx) => (
                    <li key={idx} className="text-sm text-yellow-800">
                      🟡 {flag.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Extracted Data Preview */}
            {assessmentData.raw_extraction && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">📄 Extracted Protocol Data</h4>
                <div className="text-sm text-gray-600 space-y-1">
                  <p>NCT ID: {assessmentData.raw_extraction.nct_id || 'Not found'}</p>
                  <p>Phase: {assessmentData.raw_extraction.phase || 'Not specified'}</p>
                  <p>Indication: {assessmentData.raw_extraction.indication || 'Not specified'}</p>
                  <p>Target Enrollment: {assessmentData.raw_extraction.target_enrollment || 'Not specified'}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Auto-fill Review Screen
  const AutofillScreen = () => {
    const [activeTab, setActiveTab] = useState('objective');

    if (!formResponses) return null;

    const handleSubmit = async () => {
      try {
        // Combine objective and subjective responses
        const allResponses = [
          ...formResponses.objective,
          ...formResponses.subjective.map((item: FormResponse) => ({
            ...item,
            value: subjectiveAnswers[item.key] || item.value
          }))
        ];

        // Save to backend
        if (assessmentData) {
          await api.updateResponses(assessmentData.assessment_id, allResponses);
        }

        setCurrentScreen('submit');
      } catch (error) {
        console.error('Error submitting assessment:', error);
        setError('Failed to submit assessment');
      }
    };

    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button onClick={() => setCurrentScreen('score')} className="text-gray-600 hover:text-gray-900">
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h2 className="text-xl font-semibold text-gray-900">Review & Complete Assessment</h2>
            </div>
            <button
              onClick={handleSubmit}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              Submit Assessment
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-4xl mx-auto px-6 py-8">
          <div className="bg-white rounded-lg shadow">
            <div className="border-b border-gray-200">
              <nav className="flex -mb-px">
                <button
                  onClick={() => setActiveTab('objective')}
                  className={`py-3 px-6 font-medium text-sm ${
                    activeTab === 'objective'
                      ? 'border-b-2 border-green-600 text-green-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Objective (Auto-filled) ✅
                </button>
                <button
                  onClick={() => setActiveTab('subjective')}
                  className={`py-3 px-6 font-medium text-sm ${
                    activeTab === 'subjective'
                      ? 'border-b-2 border-green-600 text-green-600'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Subjective (Needs Input) ❗
                </button>
              </nav>
            </div>

            <div className="p-6">
              {activeTab === 'objective' ? (
                <div className="space-y-4">
                  {formResponses.objective.length > 0 ? (
                    formResponses.objective.map((item: FormResponse) => (
                      <div key={item.key} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-700">{item.question}</p>
                          <p className="text-gray-900 mt-1">{item.value}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          {item.confidence && (
                            <span className="text-xs text-gray-500">{item.confidence}% confidence</span>
                          )}
                          {item.locked && <span className="text-gray-400">🔒</span>}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500">No auto-filled fields available</p>
                  )}
                </div>
              ) : (
                <div className="space-y-6">
                  {formResponses.subjective.length > 0 ? (
                    formResponses.subjective.map((item: FormResponse) => (
                      <div key={item.key}>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          {item.question} {item.required && <span className="text-red-500">*</span>}
                        </label>
                        <textarea
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                          rows={4}
                          placeholder="Enter your response..."
                          value={subjectiveAnswers[item.key] || ''}
                          onChange={(e) => setSubjectiveAnswers({
                            ...subjectiveAnswers,
                            [item.key]: e.target.value
                          })}
                        />
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500">No subjective fields require input</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // What-If Analysis Screen
  const WhatIfScreen = () => {
    const [crcFte, setCrcFte] = useState(1.5);
    const [mriHours, setMriHours] = useState(8);
    const [recruitChannels, setRecruitChannels] = useState({ ehr: true, community: true, social: false });

    useEffect(() => {
      if (!assessmentData) return;

      // Calculate new score based on changes
      let newScore = assessmentData.match_score;
      if (crcFte > 1.5) newScore += Math.round((crcFte - 1.5) * 8);
      if (mriHours > 8) newScore += Math.round((mriHours - 8) * 0.375);
      if (recruitChannels.social) newScore += 2;
      setWhatIfScore(Math.min(100, newScore));
    }, [crcFte, mriHours, recruitChannels, assessmentData]);

    if (!assessmentData) return null;

    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button onClick={() => setCurrentScreen('score')} className="text-gray-600 hover:text-gray-900">
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h2 className="text-xl font-semibold text-gray-900">What-If Scenario Analysis</h2>
            </div>
          </div>
        </div>

        <div className="max-w-4xl mx-auto px-6 py-8">
          <div className="bg-white rounded-lg shadow-lg p-8">
            {/* Score Comparison */}
            <div className="grid grid-cols-2 gap-8 mb-8">
              <div className="text-center">
                <div className="text-3xl font-bold text-gray-600">{assessmentData.match_score}/100</div>
                <p className="text-sm text-gray-500">Current Score</p>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">
                  {whatIfScore}/100
                  {whatIfScore > assessmentData.match_score && (
                    <span className="text-lg ml-1">⬆️ +{whatIfScore - assessmentData.match_score}</span>
                  )}
                </div>
                <p className="text-sm text-gray-500">Adjusted Score</p>
              </div>
            </div>

            {/* Adjustment Controls */}
            <div className="space-y-6">
              <h3 className="font-medium text-gray-900">Adjust Resources</h3>

              {/* CRC FTE */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700">CRC FTE</label>
                  <span className="text-sm text-gray-900">{crcFte.toFixed(1)} FTE</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="3"
                  step="0.5"
                  value={crcFte}
                  onChange={(e) => setCrcFte(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              {/* MRI Hours */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700">MRI Access Hours</label>
                  <span className="text-sm text-gray-900">{mriHours} hours/day</span>
                </div>
                <input
                  type="range"
                  min="4"
                  max="16"
                  step="2"
                  value={mriHours}
                  onChange={(e) => setMriHours(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>

              {/* Recruitment Channels */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">Recruitment Channels</label>
                <div className="space-y-2">
                  {Object.entries({ ehr: 'EHR', community: 'Community', social: 'Social Media' }).map(([key, label]) => (
                    <label key={key} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={recruitChannels[key as keyof typeof recruitChannels]}
                        onChange={(e) => setRecruitChannels({
                          ...recruitChannels,
                          [key]: e.target.checked
                        })}
                        className="mr-2"
                      />
                      <span className="text-sm text-gray-700">{label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* Rationale */}
            {whatIfScore > assessmentData.match_score && (
              <div className="mt-6 p-4 bg-green-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Improvement Rationale</h4>
                <p className="text-sm text-gray-700">
                  Adding {(crcFte - 1.5).toFixed(1)} FTE CRC during startup phase increases bandwidth score.
                  Extended MRI hours reduce scheduling conflicts, improving patient access.
                  {recruitChannels.social && 'Social media recruitment expands reach beyond traditional channels.'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Submit Success Screen
  const SubmitScreen = () => (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-6 py-12">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Assessment Complete!</h2>
          <p className="text-gray-600 mb-8">
            Your feasibility assessment has been saved and is ready for submission
          </p>

          {/* Results Summary */}
          <div className="border-t border-b border-gray-200 py-4 mb-6">
            <h3 className="font-medium text-gray-900 mb-4">Assessment Summary</h3>
            <div className="text-left space-y-2">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Protocol:</span> {assessmentData?.protocol_name}
              </p>
              <p className="text-sm text-gray-600">
                <span className="font-medium">Match Score:</span> {assessmentData?.match_score}/100
              </p>
              <p className="text-sm text-gray-600">
                <span className="font-medium">Auto-completion:</span> {assessmentData?.completion_percentage}%
              </p>
              <p className="text-sm text-gray-600">
                <span className="font-medium">Time Saved:</span> ~45 minutes
              </p>
            </div>
          </div>

          {/* Export Options */}
          <div className="flex justify-center space-x-4 mb-6">
            <button className="flex items-center space-x-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">
              <FileText className="w-4 h-4" />
              <span>Download PDF</span>
            </button>
            <button className="flex items-center space-x-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">
              <BarChart3 className="w-4 h-4" />
              <span>Export Excel</span>
            </button>
          </div>

          <button
            onClick={() => {
              setCurrentScreen('inbox');
              setAssessmentData(null);
              setFormResponses(null);
            }}
            className="mt-4 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            Return to Inbox
          </button>
        </div>
      </div>
    </div>
  );

  // Main app render
  return (
    <div className="min-h-screen bg-gray-50">
      {currentScreen === 'inbox' && <InboxScreen />}
      {currentScreen === 'intake' && <IntakeScreen />}
      {currentScreen === 'processing' && <ProcessingScreen />}
      {currentScreen === 'score' && <ScoreScreen />}
      {currentScreen === 'autofill' && <AutofillScreen />}
      {currentScreen === 'whatif' && <WhatIfScreen />}
      {currentScreen === 'submit' && <SubmitScreen />}
    </div>
  );
}