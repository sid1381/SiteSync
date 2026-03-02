// frontend/app/page.tsx - Complete SiteSync Frontend with Survey Management

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Upload, FileText, CheckCircle, AlertCircle, ChevronRight, ChevronDown,
  Loader2, BarChart3, Users, ClipboardCheck, Sliders, Send,
  ArrowLeft, Building2, Clock, Target, TrendingUp, AlertTriangle,
  Plus, Calendar, Mail, Download, FileSpreadsheet, ExternalLink,
  CheckSquare, Square, Edit3, Save, X, Shield, Award, Zap, Check
} from 'lucide-react';
import emailjs from '@emailjs/browser';

const API_URL = 'http://localhost:8000';

// EmailJS configuration
const EMAILJS_SERVICE_ID = 'service_jr2iv58';
const EMAILJS_TEMPLATE_ID = 'template_b0anxpu';
const EMAILJS_PUBLIC_KEY = 'gexRjFVCz8zFgSra7';

// API client with all new survey endpoints
const api = {
  // Existing endpoints
  async getSites() {
    const response = await fetch(`${API_URL}/sites/`);
    if (!response.ok) throw new Error('Failed to fetch sites');
    return response.json();
  },

  // New survey endpoints
  async createSurvey(surveyData: any) {
    const response = await fetch(`${API_URL}/surveys/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(surveyData)
    });
    if (!response.ok) throw new Error('Failed to create survey');
    return response.json();
  },

  async getInbox(siteId: number) {
    const response = await fetch(`${API_URL}/surveys/inbox/${siteId}`);
    if (!response.ok) throw new Error('Failed to fetch inbox');
    return response.json();
  },

  async uploadProtocol(surveyId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}/surveys/${surveyId}/upload-protocol`, {
      method: 'POST',
      body: formData
    });
    if (!response.ok) throw new Error('Failed to upload protocol');
    return response.json();
  },

  async uploadSurvey(surveyId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}/surveys/${surveyId}/upload-survey`, {
      method: 'POST',
      body: formData
    });
    if (!response.ok) throw new Error('Failed to upload survey');
    return response.json();
  },

  async getSurveyDetails(surveyId: number) {
    const response = await fetch(`${API_URL}/surveys/${surveyId}`);
    if (!response.ok) throw new Error('Failed to fetch survey details');
    return response.json();
  },

  async submitSurvey(surveyId: number, sponsorEmail: string, responses: any[]) {
    const response = await fetch(`${API_URL}/surveys/${surveyId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sponsor_email: sponsorEmail,
        subjective_responses: responses
      })
    });
    if (!response.ok) throw new Error('Failed to submit survey');
    return response.json();
  },

  // Feasibility endpoints
  async getFeasibility(surveyId: number) {
    const response = await fetch(`${API_URL}/surveys/${surveyId}/feasibility`);
    return response.json();
  },

  async calculateFeasibility(surveyId: number) {
    const response = await fetch(`${API_URL}/surveys/${surveyId}/calculate-feasibility`, {
      method: 'POST'
    });
    return response.json();
  },

  // Site Profile endpoints
  async getSiteProfile(siteId: number) {
    const response = await fetch(`${API_URL}/site-profile/${siteId}`);
    if (!response.ok) throw new Error('Failed to fetch site profile');
    return response.json();
  },

  async updateSiteProfile(siteId: number, profileData: any) {
    const response = await fetch(`${API_URL}/site-profile/${siteId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData)
    });
    if (!response.ok) throw new Error('Failed to update site profile');
    return response.json();
  }
};

export default function SiteSync() {
  const [currentView, setCurrentView] = useState<string>('dashboard');
  const [selectedSite, setSelectedSite] = useState<any>(null);
  const [surveys, setSurveys] = useState<any[]>([]);
  const [selectedSurvey, setSelectedSurvey] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processingStage, setProcessingStage] = useState<string>('');
  const [surveyResponses, setSurveyResponses] = useState<any[]>([]);
  const [editedResponses, setEditedResponses] = useState<{[key: string]: string}>({});
  const [siteProfile, setSiteProfile] = useState<any>(null);
  const [feasibilityData, setFeasibilityData] = useState<any>(null);

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      // Fetch first available site dynamically
      const sites = await api.getSites();
      if (sites && sites.length > 0) {
        const firstSite = sites[0];
        setSelectedSite(firstSite);
        loadInbox(firstSite.id);
        loadSiteProfile(firstSite.id);
      } else {
        setError('No sites available');
      }
    } catch (err) {
      console.error('Error loading sites:', err);
      setError('Failed to load sites');
    }
  };

  const loadSiteProfile = async (siteId: number) => {
    try {
      const profileData = await api.getSiteProfile(siteId);
      setSiteProfile(profileData);
    } catch (err) {
      console.error('Error loading site profile:', err);
    }
  };

  const updateSiteProfile = async (profileData: any) => {
    setLoading(true);
    try {
      const result = await api.updateSiteProfile(1, profileData);
      await loadSiteProfile(1); // Reload updated profile
      setError(null);
    } catch (err) {
      setError('Failed to update site profile');
    } finally {
      setLoading(false);
    }
  };

  const loadInbox = async (siteId: number) => {
    try {
      const inboxData = await api.getInbox(siteId);
      setSurveys(inboxData.surveys || []);
    } catch (err) {
      console.error('Error loading inbox:', err);
    }
  };

  // Create new survey
  const handleCreateSurvey = async (surveyData: any) => {
    setLoading(true);
    try {
      const result = await api.createSurvey({
        ...surveyData,
        site_id: selectedSite?.id || 1
      });

      if (result.success) {
        await loadInbox(selectedSite?.id || 1);
        setCurrentView('inbox');
      }
    } catch (err) {
      setError('Failed to create survey');
    } finally {
      setLoading(false);
    }
  };

  // Upload protocol (SECOND step - requires survey to be uploaded first)
  const handleProtocolUpload = async (file: File) => {
    if (!selectedSurvey) return;

    // Verify survey was uploaded first
    if (selectedSurvey.status !== 'survey_processed' && selectedSurvey.status !== 'ready_for_autofill') {
      setError('Survey document must be uploaded first before protocol upload');
      return;
    }

    setLoading(true);
    setProcessingStage('Uploading protocol...');

    try {
      // Processing stages with correct workflow messaging
      setTimeout(() => setProcessingStage('Extracting protocol requirements...'), 1000);
      setTimeout(() => setProcessingStage('Mapping protocol needs to survey questions...'), 2500);
      setTimeout(() => setProcessingStage('Auto-filling with site profile data...'), 4000);
      setTimeout(() => setProcessingStage('Calculating feasibility score...'), 5500);

      const result = await api.uploadProtocol(selectedSurvey.id, file);

      // Load updated survey details with autofilled responses
      const details = await api.getSurveyDetails(selectedSurvey.id);
      setSurveyResponses(details.responses || []);

      setSelectedSurvey({
        ...selectedSurvey,
        feasibility_score: result.feasibility_score,
        completion_percentage: result.completion_percentage,
        flags: result.flags,
        protocol_uploaded: true,
        status: 'autofilled'
      });

      setProcessingStage('Protocol processed and survey auto-filled!');
      setTimeout(() => {
        setProcessingStage('');
        setCurrentView('feasibility');
      }, 2000);
    } catch (err) {
      setError('Failed to process protocol. ' + (err instanceof Error ? err.message : ''));
    } finally {
      setLoading(false);
    }
  };

  // Upload survey document (FIRST step - extracts questions to understand what needs answering)
  const handleSurveyUpload = async (file: File) => {
    if (!selectedSurvey) return;

    setLoading(true);
    setProcessingStage('Uploading survey document...');

    try {
      setTimeout(() => setProcessingStage('Extracting survey questions...'), 1000);
      setTimeout(() => setProcessingStage('Categorizing objective vs subjective questions...'), 2500);

      const result = await api.uploadSurvey(selectedSurvey.id, file);

      setSelectedSurvey({
        ...selectedSurvey,
        questions_extracted: result.questions_extracted,
        objective_questions: result.objective_questions,
        subjective_questions: result.subjective_questions,
        survey_uploaded: true,
        status: 'survey_processed'
      });

      setProcessingStage(`Survey processed! Found ${result.questions_extracted} questions (${result.objective_questions} can be auto-filled).`);
      setTimeout(() => {
        setProcessingStage('');
        // Don't automatically go to review - need protocol upload first
        setCurrentView('upload');
      }, 3000);
    } catch (err) {
      setError('Failed to process survey. ' + (err instanceof Error ? err.message : ''));
    } finally {
      setLoading(false);
    }
  };

  // Handle response editing
  const handleResponseEdit = (questionId: string, value: string) => {
    setEditedResponses({
      ...editedResponses,
      [questionId]: value
    });
  };

  // Submit survey
  const handleSubmitSurvey = async (sponsorEmail: string) => {
    if (!selectedSurvey) return;

    setLoading(true);
    try {
      // Prepare subjective responses with edits
      const subjectiveResponses = surveyResponses
        .filter(r => !r.is_objective || editedResponses[r.id])
        .map(r => ({
          question_id: r.id,
          response: editedResponses[r.id] || r.response || ''
        }));

      const result = await api.submitSurvey(
        selectedSurvey.id,
        sponsorEmail,
        subjectiveResponses
      );

      // Send the actual email via EmailJS
      const emailParams = {
        email: sponsorEmail,
        sponsor_name: selectedSurvey.sponsor_name || 'Sponsor',
        study_name: selectedSurvey.study_name || 'Study',
        site_name: 'UCSD NAFLD Research Center',
        feasibility_score: selectedSurvey.feasibility_score || 'N/A',
        completion_rate: selectedSurvey.completion_percentage?.toFixed(1) || 'N/A',
      };

      await emailjs.send(
        EMAILJS_SERVICE_ID,
        EMAILJS_TEMPLATE_ID,
        emailParams,
        EMAILJS_PUBLIC_KEY
      );

      console.log('Email sent successfully to:', sponsorEmail);

      setCurrentView('submitted');
      setSelectedSurvey({
        ...selectedSurvey,
        submitted: true,
        pdf_download: result.pdf_download,
        excel_download: result.excel_download
      });
    } catch (err) {
      console.error('Submission error:', err);
      setError('Failed to submit survey. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Render different views
  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardView
          siteId={selectedSite?.id || 1}
          onNavigateToInbox={() => setCurrentView('inbox')}
        />;

      case 'inbox':
        return <InboxView
          surveys={surveys}
          onSelectSurvey={(survey: any) => {
            setSelectedSurvey(survey);
            setCurrentView('upload');
          }}
          onCreateNew={() => setCurrentView('create')}
        />;

      case 'create':
        return <CreateSurveyView
          onSubmit={handleCreateSurvey}
          onCancel={() => setCurrentView('inbox')}
        />;

      case 'profile':
        return <SiteProfileView
          profile={siteProfile}
          onUpdate={(profileData: any) => updateSiteProfile(profileData)}
          onBack={() => setCurrentView('dashboard')}
        />;

      case 'upload':
        return <UploadView
          survey={selectedSurvey}
          onProtocolUpload={handleProtocolUpload}
          onSurveyUpload={handleSurveyUpload}
          processingStage={processingStage}
          loading={loading}
        />;

      case 'review':
        return <ReviewView
          survey={selectedSurvey}
          responses={surveyResponses}
          editedResponses={editedResponses}
          onEdit={handleResponseEdit}
          onSubmit={() => setCurrentView('submit')}
          onBack={() => setCurrentView('upload')}
          onViewFeasibility={() => setCurrentView('feasibility')}
        />;

      case 'feasibility':
        return <FeasibilityView
          survey={selectedSurvey}
          feasibilityData={feasibilityData}
          setFeasibilityData={setFeasibilityData}
          setCurrentView={setCurrentView}
          siteProfile={siteProfile}
        />;

      case 'submit':
        return <SubmitView
          survey={selectedSurvey}
          onSubmit={handleSubmitSurvey}
          onBack={() => setCurrentView('review')}
        />;

      case 'submitted':
        return <SubmittedView
          survey={selectedSurvey}
          onReturnToInbox={() => {
            setCurrentView('inbox');
            loadInbox(1);
          }}
        />;

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1
              className="text-2xl font-bold text-green-600 cursor-pointer"
              onClick={() => setCurrentView('dashboard')}
            >
              SiteSync
            </h1>
            {selectedSite && (
              <div className="flex items-center text-black">
                <Building2 className="w-4 h-4 mr-2" />
                <span>{selectedSite.name}</span>
              </div>
            )}
          </div>
          <div className="flex items-center space-x-6">
            <nav className="flex space-x-4">
              <button
                onClick={() => setCurrentView('dashboard')}
                className={`px-3 py-1 rounded text-sm font-medium ${
                  currentView === 'dashboard'
                    ? 'text-green-600 bg-green-50'
                    : 'text-black hover:text-black'
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setCurrentView('inbox')}
                className={`px-3 py-1 rounded text-sm font-medium ${
                  currentView === 'inbox'
                    ? 'text-green-600 bg-green-50'
                    : 'text-black hover:text-black'
                }`}
              >
                Inbox
              </button>
              <button
                onClick={() => setCurrentView('profile')}
                className={`px-3 py-1 rounded text-sm font-medium ${
                  currentView === 'profile'
                    ? 'text-green-600 bg-green-50'
                    : 'text-black hover:text-black'
                }`}
              >
                Site Profile
              </button>
            </nav>
            <span className="text-sm text-black">
              Transform 60-minute surveys into 15-minute workflows
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <AlertCircle className="inline w-4 h-4 mr-2" />
            {error}
            <button onClick={() => setError(null)} className="float-right">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {renderView()}
      </main>
    </div>
  );
}

// Inbox View Component
function InboxView({ surveys, onSelectSurvey, onCreateNew }: any) {
  const getSurveyStateInfo = (status: string) => {
    switch (status) {
      case 'pending':
        return {
          badge: 'Ready for Upload',
          bgColor: 'bg-green-100',
          textColor: 'text-green-800',
          clickable: true,
          description: 'Upload survey document to start'
        };
      case 'survey_processed':
        return {
          badge: 'Ready for Protocol',
          bgColor: 'bg-blue-100',
          textColor: 'text-blue-800',
          clickable: true,
          description: 'Upload protocol document for autofill'
        };
      case 'autofilled':
      case 'protocol_processed':
        return {
          badge: 'Completed',
          bgColor: 'bg-gray-100',
          textColor: 'text-gray-800',
          clickable: false,
          description: 'Review and submit complete'
        };
      case 'submitted':
        return {
          badge: 'Submitted',
          bgColor: 'bg-green-100',
          textColor: 'text-green-800',
          clickable: false,
          description: 'Successfully submitted to sponsor'
        };
      default:
        return {
          badge: status,
          bgColor: 'bg-gray-100',
          textColor: 'text-gray-800',
          clickable: false,
          description: 'Unknown status'
        };
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-black">Survey Inbox</h2>
        <button
          onClick={onCreateNew}
          className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Survey
        </button>
      </div>

      <div className="space-y-4">
        {surveys.map((survey: any) => {
          const stateInfo = getSurveyStateInfo(survey.status);
          return (
            <div
              key={survey.id}
              className={`bg-white p-6 rounded-lg shadow transition ${
                stateInfo.clickable
                  ? 'hover:shadow-lg cursor-pointer hover:border-l-4 hover:border-blue-500'
                  : 'opacity-75 cursor-default'
              }`}
              onClick={() => stateInfo.clickable && onSelectSurvey(survey)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h3 className={`text-lg font-semibold ${
                      stateInfo.clickable ? 'text-black' : 'text-black'
                    }`}>
                      {survey.study_name}
                    </h3>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${stateInfo.bgColor} ${stateInfo.textColor}`}>
                      {stateInfo.badge}
                    </span>
                  </div>

                  <p className={`${stateInfo.clickable ? 'text-black' : 'text-black'}`}>
                    {survey.sponsor_name}
                  </p>

                  <p className={`text-sm mt-1 ${stateInfo.clickable ? 'text-blue-600' : 'text-black'}`}>
                    {stateInfo.description}
                  </p>

                  <div className={`mt-3 flex items-center space-x-4 text-sm ${
                    stateInfo.clickable ? 'text-black' : 'text-black'
                  }`}>
                    <span>{survey.study_type}</span>
                    {survey.nct_number && <span>NCT: {survey.nct_number}</span>}
                    {survey.due_date && (
                      <span className="flex items-center">
                        <Calendar className="w-3 h-3 mr-1" />
                        Due: {new Date(survey.due_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-end space-y-2">
                  {survey.feasibility_score && (
                    <div className={`text-2xl font-bold ${
                      stateInfo.clickable ? 'text-green-600' : 'text-green-400'
                    }`}>
                      {survey.feasibility_score}/100
                    </div>
                  )}

                  {survey.completion_percentage > 0 && (
                    <span className={`text-sm ${
                      stateInfo.clickable ? 'text-black' : 'text-black'
                    }`}>
                      {survey.completion_percentage.toFixed(0)}% complete
                    </span>
                  )}

                  {stateInfo.clickable && (
                    <div className="flex items-center text-sm text-blue-600 mt-2">
                      <span>Click to continue</span>
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </div>
                  )}

                  {!stateInfo.clickable && (
                    <div className="flex items-center text-sm text-black mt-2">
                      <CheckCircle className="w-4 h-4 mr-1" />
                      <span>Complete</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {surveys.length === 0 && (
        <div className="bg-white p-12 rounded-lg text-center">
          <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
          <p className="text-black">No surveys in inbox</p>
          <button
            onClick={onCreateNew}
            className="mt-4 text-green-600 hover:text-green-700"
          >
            Create your first survey
          </button>
        </div>
      )}
    </div>
  );
}

// Create Survey View
function CreateSurveyView({ onSubmit, onCancel }: any) {
  const [formData, setFormData] = useState({
    sponsor_name: '',
    study_name: '',
    study_type: 'Phase II',
    nct_number: '',
    due_date: ''
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-black mb-6">Create New Survey Entry</h2>

      <form onSubmit={handleSubmit} className="bg-white p-6 rounded-lg shadow">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-black mb-1">
              Sponsor Name
            </label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500 text-black"
              value={formData.sponsor_name}
              onChange={(e) => setFormData({...formData, sponsor_name: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black mb-1">
              Study Name
            </label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500 text-black"
              value={formData.study_name}
              onChange={(e) => setFormData({...formData, study_name: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black mb-1">
              Study Type
            </label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500 text-black"
              value={formData.study_type}
              onChange={(e) => setFormData({...formData, study_type: e.target.value})}
            >
              <option>Phase I</option>
              <option>Phase II</option>
              <option>Phase III</option>
              <option>Phase IV</option>
              <option>Device</option>
              <option>Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-black mb-1">
              NCT Number (Optional)
            </label>
            <input
              type="text"
              placeholder="NCT12345678"
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500 text-black"
              value={formData.nct_number}
              onChange={(e) => setFormData({...formData, nct_number: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black mb-1">
              Due Date
            </label>
            <input
              type="date"
              placeholder="mm/dd/yyyy"
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500 text-black"
              value={formData.due_date}
              onChange={(e) => setFormData({...formData, due_date: e.target.value})}
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end space-x-3">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Create Survey
          </button>
        </div>
      </form>
    </div>
  );
}

// Upload View with dual upload zones
function UploadView({ survey, onProtocolUpload, onSurveyUpload, processingStage, loading }: any) {
  const [protocolFile, setProtocolFile] = useState<File | null>(null);
  const [surveyFile, setSurveyFile] = useState<File | null>(null);

  const handleDrop = (e: React.DragEvent, type: 'protocol' | 'survey') => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (type === 'protocol') {
      setProtocolFile(file);
    } else {
      setSurveyFile(file);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-black">{survey.study_name}</h2>
        <p className="text-black">{survey.sponsor_name}</p>
      </div>

      {processingStage && (
        <div className="mb-6 bg-blue-50 border border-blue-200 px-4 py-3 rounded">
          <div className="flex items-center">
            <Loader2 className="animate-spin w-5 h-5 mr-2 text-blue-600" />
            <span className="text-blue-700">{processingStage}</span>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Protocol Upload */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold text-black mb-4 flex items-center">
            <FileText className="w-5 h-5 mr-2 text-green-600" />
            Protocol Document
          </h3>

          {survey.protocol_uploaded ? (
            <div className="text-center py-8">
              <CheckCircle className="w-16 h-16 mx-auto text-green-500 mb-4" />
              <p className="text-green-600 font-medium">Protocol Uploaded</p>
              {survey.feasibility_score && (
                <div className="mt-4">
                  <div className="text-3xl font-bold text-green-600">
                    {survey.feasibility_score}/100
                  </div>
                  <p className="text-sm text-black">Feasibility Score</p>
                </div>
              )}
            </div>
          ) : (
            <div
              className={`border-2 border-dashed border-gray-300 rounded-lg p-8 text-center transition cursor-pointer ${
                survey.survey_uploaded ? 'hover:border-green-500' : 'opacity-50 cursor-not-allowed'
              }`}
              onDrop={(e) => survey.survey_uploaded && handleDrop(e, 'protocol')}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => survey.survey_uploaded && document.getElementById('protocol-input')?.click()}
            >
              <Upload className="w-12 h-12 mx-auto text-gray-500 mb-3" />
              <p className="text-gray-800 font-medium">Drop protocol PDF here</p>
              <p className="text-sm text-black mt-1">or click to browse</p>
              {!survey.survey_uploaded && (
                <p className="text-xs text-yellow-700 font-medium mt-2">Upload survey document first</p>
              )}
              {survey.survey_uploaded && (
                <p className="text-xs text-green-700 font-medium mt-2">Ready to upload protocol for autofill</p>
              )}
              <input
                id="protocol-input"
                type="file"
                accept=".pdf"
                className="hidden"
                disabled={!survey.survey_uploaded}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    setProtocolFile(file);
                    onProtocolUpload(file);
                  }
                }}
              />
              {protocolFile && (
                <p className="mt-3 text-sm text-green-600">{protocolFile.name}</p>
              )}
            </div>
          )}
        </div>

        {/* Survey Upload */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold text-black mb-4 flex items-center">
            <ClipboardCheck className="w-5 h-5 mr-2 text-blue-600" />
            Survey Document
          </h3>

          {survey.survey_uploaded ? (
            <div className="text-center py-8">
              <CheckCircle className="w-16 h-16 mx-auto text-green-500 mb-4" />
              <p className="text-green-600 font-medium">Survey Uploaded</p>
              <div className="mt-4 space-y-2">
                <p className="text-sm text-black">
                  {survey.questions_extracted} questions extracted
                </p>
                <p className="text-sm text-black">
                  {survey.questions_autofilled} auto-filled
                </p>
                <div className="text-2xl font-bold text-blue-600">
                  {survey.completion_percentage?.toFixed(0)}%
                </div>
                <p className="text-sm text-black">Auto-completion</p>
              </div>
            </div>
          ) : (
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition cursor-pointer"
              onDrop={(e) => handleDrop(e, 'survey')}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => document.getElementById('survey-input')?.click()}
            >
              <Upload className="w-12 h-12 mx-auto text-gray-500 mb-3" />
              <p className="text-gray-800 font-medium">Drop survey PDF or Excel</p>
              <p className="text-sm text-black mt-1">or click to browse</p>
              <p className="text-xs text-blue-600 font-medium mt-2">Upload survey first to extract questions</p>
              <input
                id="survey-input"
                type="file"
                accept=".pdf,.xlsx,.xls"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    setSurveyFile(file);
                    onSurveyUpload(file);
                  }
                }}
              />
              {surveyFile && (
                <p className="mt-3 text-sm text-blue-600">{surveyFile.name}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Flags and recommendations */}
      {survey.flags && survey.flags.length > 0 && (
        <div className="mt-6 bg-yellow-50 border border-yellow-200 p-4 rounded">
          <h4 className="font-semibold text-yellow-800 mb-2">Attention Areas</h4>
          <ul className="space-y-1">
            {survey.flags.map((flag: string, idx: number) => (
              <li key={idx} className="text-sm text-yellow-700 flex items-start">
                <AlertTriangle className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" />
                {flag}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Review View with objective/subjective tabs
function ReviewView({ survey, responses, editedResponses, onEdit, onSubmit, onBack, onViewFeasibility }: any) {
  const [activeTab, setActiveTab] = useState<'objective' | 'subjective'>('objective');

  const objectiveResponses = responses.filter((r: any) => r.is_objective);
  const subjectiveResponses = responses.filter((r: any) => !r.is_objective);

  const activeResponses = activeTab === 'objective' ? objectiveResponses : subjectiveResponses;

  return (
    <div>
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-black">Review Responses</h2>
          <p className="text-black">{survey.study_name}</p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onViewFeasibility}
            className="flex items-center text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded"
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            View Feasibility Score
          </button>
          <button
            onClick={onBack}
            className="flex items-center text-black hover:text-black"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </button>
        </div>
      </div>

      {/* Completion stats */}
      <div className="bg-white p-6 rounded-lg shadow-md mb-6 border border-gray-200">
        <div className="grid grid-cols-3 gap-6 text-center">
          <div className="border-r border-gray-200">
            <div className="text-3xl font-bold text-green-600">
              {objectiveResponses.length}
            </div>
            <p className="text-sm font-medium text-gray-800 mt-1">Objective (Auto-filled)</p>
          </div>
          <div className="border-r border-gray-200">
            <div className="text-3xl font-bold text-blue-600">
              {subjectiveResponses.length}
            </div>
            <p className="text-sm font-medium text-gray-800 mt-1">Subjective (Manual)</p>
          </div>
          <div>
            <div className="text-3xl font-bold text-purple-600">
              {survey.completion_percentage?.toFixed(0)}%
            </div>
            <p className="text-sm font-medium text-gray-800 mt-1">Auto-completion Rate</p>
          </div>
        </div>

        {/* Warning if subjective questions need input */}
        {subjectiveResponses.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-center text-amber-700 bg-amber-50 px-4 py-2 rounded-md">
              <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" />
              <span className="text-sm font-medium">
                {subjectiveResponses.length} subjective question{subjectiveResponses.length !== 1 ? 's' : ''} require{subjectiveResponses.length === 1 ? 's' : ''} manual input
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <div className="flex">
            <button
              onClick={() => setActiveTab('objective')}
              className={`px-6 py-3 font-medium ${
                activeTab === 'objective'
                  ? 'text-green-600 border-b-2 border-green-600'
                  : 'text-black hover:text-black'
              }`}
            >
              <CheckSquare className="inline w-4 h-4 mr-2" />
              Objective ({objectiveResponses.length})
            </button>
            <button
              onClick={() => setActiveTab('subjective')}
              className={`px-6 py-3 font-medium ${
                activeTab === 'subjective'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-black hover:text-black'
              }`}
            >
              <Edit3 className="inline w-4 h-4 mr-2" />
              Subjective ({subjectiveResponses.length})
            </button>
          </div>
        </div>

        {/* Responses list */}
        <div className="p-6">
          <div className="space-y-6">
            {activeResponses.map((response: any) => (
              <div key={response.id} className="border border-gray-200 rounded-lg p-4 bg-white shadow-sm">
                <div className="flex justify-between items-start mb-3">
                  <p className="text-base font-semibold text-black flex-1 leading-relaxed">
                    {response.text}
                  </p>
                  {response.confidence && (
                    <span className="ml-3 text-xs font-medium text-black bg-gray-100 px-2 py-1 rounded">
                      {response.confidence.toFixed(0)}% confidence
                    </span>
                  )}
                </div>

                {activeTab === 'objective' ? (
                  <div className="bg-green-50 border border-green-100 px-4 py-3 rounded-md">
                    <p className="text-sm text-black font-medium">{response.response || 'No data available'}</p>
                    <p className="text-xs text-black mt-2">
                      <span className="font-medium">Source:</span> {response.source}
                      {response.confidence && response.confidence > 0 && (
                        <span className="ml-2">• {Math.round(response.confidence)}% confidence</span>
                      )}
                    </p>
                  </div>
                ) : (
                  <textarea
                    className="w-full px-4 py-3 border-2 border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-black"
                    rows={3}
                    placeholder="Enter your response..."
                    value={editedResponses[response.id] || response.response || ''}
                    onChange={(e) => onEdit(response.id, e.target.value)}
                  />
                )}
              </div>
            ))}
          </div>

          {activeTab === 'subjective' && (
            <div className="mt-6 flex justify-end">
              <button
                onClick={onSubmit}
                className="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700 flex items-center"
              >
                Continue to Submit
                <ChevronRight className="w-4 h-4 ml-2" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Submit View
function SubmitView({ survey, onSubmit, onBack }: any) {
  const [sponsorEmail, setSponsorEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    await onSubmit(sponsorEmail);
    setSubmitting(false);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-black mb-6">Submit Survey</h2>

      <div className="bg-white p-6 rounded-lg shadow">
        <form onSubmit={handleSubmit}>
          <div className="mb-6">
            <h3 className="font-semibold text-black mb-3">Survey Summary</h3>
            <div className="bg-gray-50 p-4 rounded space-y-2 text-sm text-black">
              <p><strong>Study:</strong> {survey.study_name}</p>
              <p><strong>Sponsor:</strong> {survey.sponsor_name}</p>
              <p><strong>Feasibility Score:</strong> {survey.feasibility_score}/100</p>
              <p><strong>Auto-completion:</strong> {survey.completion_percentage?.toFixed(0)}%</p>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-black mb-1">
              Sponsor Email Address
            </label>
            <input
              type="email"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500 text-black"
              placeholder="sponsor@example.com"
              value={sponsorEmail}
              onChange={(e) => setSponsorEmail(e.target.value)}
            />
            <p className="text-xs text-black mt-1">
              The completed survey will be sent to this email with PDF and Excel attachments
            </p>
          </div>

          <div className="mb-6">
            <h4 className="font-semibold text-black mb-3">What will be sent:</h4>
            <ul className="space-y-2 text-sm text-black">
              <li className="flex items-center">
                <FileText className="w-4 h-4 mr-2 text-red-600" />
                PDF Report with all responses
              </li>
              <li className="flex items-center">
                <FileSpreadsheet className="w-4 h-4 mr-2 text-green-600" />
                Excel spreadsheet for analysis
              </li>
              <li className="flex items-center">
                <BarChart3 className="w-4 h-4 mr-2 text-blue-600" />
                Feasibility score breakdown
              </li>
            </ul>
          </div>

          <div className="flex justify-between">
            <button
              type="button"
              onClick={onBack}
              className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 text-black"
            >
              Back to Review
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700 flex items-center disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="animate-spin w-4 h-4 mr-2" />
                  Submitting...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Submit to Sponsor
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============== HELPER COMPONENTS FOR FEASIBILITY VIEW ==============

// Expandable Score Contributor Card with Criteria-Based Scoring Table
function ScoreContributorCard({ component }: { component: any }) {
  const [expanded, setExpanded] = useState(false);

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'bg-green-500';
    if (score >= 70) return 'bg-green-400';
    if (score >= 55) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getConfidenceBadge = (confidence: string) => {
    switch (confidence) {
      case 'HIGH': return 'bg-green-100 text-green-700';
      case 'MODERATE': return 'bg-yellow-100 text-yellow-700';
      case 'LOW': return 'bg-gray-100 text-gray-600';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  const criteriaScores = component.criteria_scores;
  const breakdown = component.scoring_breakdown;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-3">
            <span className="font-medium text-gray-900">{component.category}</span>
            {component.confidence && (
              <span className={`px-2 py-0.5 text-xs rounded-full ${getConfidenceBadge(component.confidence)}`}>
                {component.confidence}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold text-gray-900">{Math.round(component.score)}</span>
            <span className="text-gray-500">/100</span>
            <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </div>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div
            className={`h-2.5 rounded-full transition-all ${getScoreColor(component.score)}`}
            style={{ width: `${component.score}%` }}
          />
        </div>
        {/* Brief reasoning below progress bar */}
        <p className="text-sm text-gray-600 mt-2">
          {component.reasoning || component.rationale}
        </p>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 bg-gray-50">
          {/* Criteria-Based Scoring Table (New Format) */}
          {criteriaScores && criteriaScores.length > 0 ? (
            <div className="mt-4 space-y-4">
              {/* Criteria Table */}
              <div className="overflow-hidden rounded-lg border border-gray-200">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                        Criterion
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                        Site Data
                      </th>
                      <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">
                        Points
                      </th>
                      <th className="px-4 py-2 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {criteriaScores.map((criterion: any, i: number) => (
                      <tr key={i} className={criterion.is_max ? 'bg-green-50' : ''}>
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-gray-900">{criterion.criterion_name}</div>
                          <div className="text-xs text-gray-500">{criterion.threshold_matched}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-sm text-gray-700">{criterion.site_value_formatted}</div>
                          {criterion.data_source && (
                            <div className="text-xs text-gray-400 truncate max-w-[150px]" title={criterion.data_source}>
                              {criterion.data_source}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`font-mono font-bold ${criterion.is_max ? 'text-green-600' : 'text-gray-700'}`}>
                            {criterion.points_earned}
                          </span>
                          <span className="text-gray-400 font-mono">/{criterion.max_points}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {criterion.is_max ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                              <Check className="w-3 h-3" />
                              Max
                            </span>
                          ) : criterion.next_threshold ? (
                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">
                              +{criterion.next_threshold.points_gain} avail
                            </span>
                          ) : (
                            <span className="text-gray-400 text-xs">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-gray-100">
                    <tr>
                      <td colSpan={2} className="px-4 py-2 text-right font-medium text-gray-700">
                        Category Total
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span className="font-mono font-bold text-gray-900">
                          {component.total_points_earned ?? criteriaScores.reduce((sum: number, c: any) => sum + c.points_earned, 0)}
                        </span>
                        <span className="text-gray-400 font-mono">
                          /{component.total_max_points ?? criteriaScores.reduce((sum: number, c: any) => sum + c.max_points, 0)}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-center font-bold text-gray-900">
                        {Math.round(component.score)}%
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {/* Improvement Path - Show criteria with available points */}
              {criteriaScores.filter((c: any) => !c.is_max && c.next_threshold).length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                    <span className="text-lg">📈</span>
                    Improvement Path
                  </h4>
                  <div className="space-y-2">
                    {criteriaScores
                      .filter((c: any) => !c.is_max && c.next_threshold)
                      .sort((a: any, b: any) => b.next_threshold.points_gain - a.next_threshold.points_gain)
                      .map((criterion: any, i: number) => (
                        <div key={i} className="flex items-start gap-3 text-sm">
                          <span className="flex-shrink-0 font-mono font-bold text-blue-600 w-14 text-right">
                            +{criterion.next_threshold.points_gain} pts
                          </span>
                          <div className="text-gray-700">
                            <span className="font-medium">{criterion.criterion_name}:</span>{' '}
                            Reach {criterion.next_threshold.required_value}+ for "{criterion.next_threshold.label}"
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Improvement Suggestions (from AI) */}
              {component.improvement_suggestions && component.improvement_suggestions.length > 0 && (
                <div className="pt-4 border-t border-gray-200">
                  <h4 className="font-medium text-blue-700 mb-2 flex items-center gap-2">
                    <span className="text-lg">💡</span>
                    Recommendations
                  </h4>
                  <ul className="space-y-1">
                    {component.improvement_suggestions.map((s: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                        <span className="text-blue-500">→</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : breakdown ? (
            /* Legacy Format: Show scoring breakdown for backward compatibility */
            <div className="mt-4 space-y-4">
              {/* Base Score */}
              <div className="flex items-center justify-between py-2 border-b border-gray-200">
                <span className="text-sm text-gray-600">Base Score</span>
                <span className="font-mono font-medium text-gray-700">{breakdown.base_score} pts</span>
              </div>

              {/* Positive Factors */}
              {breakdown.positive_factors && breakdown.positive_factors.length > 0 && (
                <div>
                  <h4 className="font-medium text-green-700 mb-2 flex items-center gap-2">
                    <span className="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center text-sm">+</span>
                    Strengths
                  </h4>
                  <div className="space-y-2">
                    {breakdown.positive_factors.map((factor: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 bg-green-50 rounded-lg p-3">
                        <span className="flex-shrink-0 font-mono font-bold text-green-600 w-16 text-right">
                          +{factor.points} pts
                        </span>
                        <span className="text-sm text-gray-700">{factor.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Negative Factors */}
              {breakdown.negative_factors && breakdown.negative_factors.length > 0 && (
                <div>
                  <h4 className="font-medium text-red-700 mb-2 flex items-center gap-2">
                    <span className="w-6 h-6 bg-red-100 rounded-full flex items-center justify-center text-sm">−</span>
                    Areas for Improvement
                  </h4>
                  <div className="space-y-2">
                    {breakdown.negative_factors.map((factor: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 bg-red-50 rounded-lg p-3">
                        <span className="flex-shrink-0 font-mono font-bold text-red-600 w-16 text-right">
                          {factor.points} pts
                        </span>
                        <span className="text-sm text-gray-700">{factor.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Final Score Calculation */}
              <div className="flex items-center justify-between py-2 border-t border-gray-200 mt-2">
                <span className="font-medium text-gray-700">Final Score</span>
                <span className="font-mono font-bold text-lg text-gray-900">
                  {breakdown.final_score || component.score}/100
                </span>
              </div>

              {/* Improvement Suggestions */}
              {component.improvement_suggestions && component.improvement_suggestions.length > 0 && (
                <div className="pt-4 border-t border-gray-200">
                  <h4 className="font-medium text-blue-700 mb-2 flex items-center gap-2">
                    <span className="text-lg">💡</span>
                    How to Improve This Score
                  </h4>
                  <ul className="space-y-1">
                    {component.improvement_suggestions.map((s: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                        <span className="text-blue-500">→</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            /* Fallback for old data without any breakdown */
            <div className="mt-4 space-y-4">
              {/* Details */}
              {component.details && component.details.length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">Evidence</h5>
                  <ul className="space-y-1">
                    {component.details.map((detail: string, i: number) => (
                      <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                        <span className="text-green-500 mt-0.5">✓</span>
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Improvement Suggestions */}
              {component.improvement_suggestions && component.improvement_suggestions.length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">Improvement Suggestions</h5>
                  <ul className="space-y-1">
                    {component.improvement_suggestions.map((suggestion: string, i: number) => (
                      <li key={i} className="text-sm text-blue-700 flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">→</span>
                        {suggestion}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Flag Card Component
function FlagCard({ flag }: { flag: any }) {
  const getSeverityStyle = (severity: string) => {
    switch (severity) {
      case 'RED': return 'border-red-300 bg-red-50';
      case 'YELLOW': return 'border-yellow-300 bg-yellow-50';
      case 'GREEN': return 'border-green-300 bg-green-50';
      default: return 'border-gray-300 bg-gray-50';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'RED': return '🔴';
      case 'YELLOW': return '🟡';
      case 'GREEN': return '🟢';
      default: return '⚪';
    }
  };

  const getSeverityTextColor = (severity: string) => {
    switch (severity) {
      case 'RED': return 'text-red-800';
      case 'YELLOW': return 'text-yellow-800';
      case 'GREEN': return 'text-green-800';
      default: return 'text-gray-800';
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${getSeverityStyle(flag.severity)}`}>
      <div className="flex items-start gap-3">
        <span className="text-lg">{getSeverityIcon(flag.severity)}</span>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h4 className={`font-medium ${getSeverityTextColor(flag.severity)}`}>{flag.title}</h4>
            {flag.potential_score_gain && (
              <span className="text-sm font-semibold text-blue-600">+{flag.potential_score_gain} pts potential</span>
            )}
          </div>
          <p className="text-sm text-gray-700 mt-1">{flag.details}</p>
          {flag.impact && (
            <p className="text-xs text-gray-500 mt-2">
              <strong>Impact:</strong> {flag.impact}
            </p>
          )}
          {flag.recommendation && (
            <p className="text-xs text-blue-600 mt-1">
              <strong>Recommendation:</strong> {flag.recommendation}
            </p>
          )}
          {flag.category && (
            <span className="inline-block mt-2 px-2 py-0.5 text-xs bg-gray-200 text-gray-600 rounded">
              {flag.category}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// CT.gov Verification Section
function CTGovVerificationSection({ siteProfile }: { siteProfile: any }) {
  const piName = siteProfile?.staff_and_experience?.principal_investigator?.name;
  const piTrials = siteProfile?.staff_and_experience?.principal_investigator?.trials_conducted;
  const historicalData = siteProfile?.historical_performance;

  if (!piName && !historicalData) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <span>🔬</span> ClinicalTrials.gov Verification
      </h3>

      <div className="grid md:grid-cols-2 gap-6">
        {/* PI Verification */}
        {piName && (
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h4 className="font-medium text-blue-900 mb-2">Principal Investigator</h4>
            <p className="text-gray-800 font-semibold">{piName}</p>
            {piTrials && (
              <p className="text-sm text-blue-700 mt-1">
                {piTrials} trials conducted
              </p>
            )}
            <a
              href={`https://clinicaltrials.gov/search?intr=${encodeURIComponent(piName)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 mt-2"
            >
              View on CT.gov <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}

        {/* Historical Performance */}
        {historicalData && (
          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <h4 className="font-medium text-green-900 mb-2">Historical Performance</h4>
            <div className="space-y-1 text-sm">
              {historicalData.studies_completed_last_5_years && (
                <p className="text-gray-800">
                  <span className="font-semibold">{historicalData.studies_completed_last_5_years}</span> studies (5 years)
                </p>
              )}
              {historicalData.patients_enrolled_last_5_years && (
                <p className="text-gray-800">
                  <span className="font-semibold">{historicalData.patients_enrolled_last_5_years.toLocaleString()}</span> patients enrolled
                </p>
              )}
              {historicalData.enrollment_success_rate && (
                <p className="text-gray-800">
                  <span className="font-semibold">{historicalData.enrollment_success_rate}%</span> enrollment success
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Therapeutic Experience */}
      {historicalData?.therapeutic_experience && historicalData.therapeutic_experience.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Therapeutic Experience</h4>
          <div className="flex flex-wrap gap-2">
            {historicalData.therapeutic_experience.map((area: string, i: number) => (
              <span key={i} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                {area}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============== MAIN FEASIBILITY VIEW ==============
function FeasibilityView({ survey, feasibilityData, setFeasibilityData, setCurrentView, siteProfile }: any) {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadFeasibility = async () => {
      if (survey) {
        setLoading(true);
        const data = await api.getFeasibility(survey.id);
        if (data.success && data.components?.length > 0) {
          setFeasibilityData(data);
        } else {
          // Calculate if not exists
          const calculated = await api.calculateFeasibility(survey.id);
          setFeasibilityData(calculated);
        }
        setLoading(false);
      }
    };
    loadFeasibility();
  }, [survey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Analyzing feasibility with AI...</p>
          <p className="text-sm text-gray-400 mt-2">Comparing protocol requirements to site capabilities</p>
        </div>
      </div>
    );
  }

  if (!feasibilityData) {
    return <div className="text-center py-8 text-gray-500">Unable to load feasibility data</div>;
  }

  // Use total_score or feasibility_score for backward compatibility
  const totalScore = feasibilityData.total_score ?? feasibilityData.feasibility_score ?? 0;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Feasibility Analysis</h2>
          <p className="text-gray-600">{survey?.sponsor_name} • {survey?.study_name}</p>
        </div>
        {feasibilityData.confidence_level && (
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
            feasibilityData.confidence_level === 'HIGH' ? 'bg-green-100 text-green-800' :
            feasibilityData.confidence_level === 'MODERATE' ? 'bg-yellow-100 text-yellow-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {feasibilityData.confidence_level} Confidence
          </div>
        )}
      </div>

      {/* Score Card */}
      <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl p-8 text-center">
        <div className="text-6xl font-bold mb-2">
          <span className={
            totalScore >= 85 ? 'text-green-500' :
            totalScore >= 70 ? 'text-green-600' :
            totalScore >= 55 ? 'text-yellow-500' :
            'text-red-500'
          }>
            {Math.round(totalScore)}
          </span>
          <span className="text-3xl text-gray-400">/100</span>
        </div>
        <span className={`inline-block px-4 py-2 rounded-full text-sm font-semibold ${
          feasibilityData.grade === 'Strong Fit' ? 'bg-green-500 text-white' :
          feasibilityData.grade === 'Good Fit' ? 'bg-green-400 text-white' :
          feasibilityData.grade === 'Moderate Fit' ? 'bg-yellow-500 text-white' :
          'bg-red-500 text-white'
        }`}>
          {feasibilityData.grade || 'Unknown'}
        </span>
        {feasibilityData.data_completeness !== undefined && (
          <p className="text-sm text-gray-600 mt-3">
            Profile Completeness: {Math.round(feasibilityData.data_completeness * 100)}%
          </p>
        )}
      </div>

      {/* Score Contributors - Expandable */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Score Contributors</h3>
        <div className="space-y-2">
          {feasibilityData.components?.map((component: any, idx: number) => (
            <ScoreContributorCard key={idx} component={component} />
          ))}
        </div>
      </div>

      {/* Detailed Flags Section */}
      {feasibilityData.detailed_flags && feasibilityData.detailed_flags.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Assessment Flags</h3>
          <div className="space-y-3">
            {feasibilityData.detailed_flags.map((flag: any, idx: number) => (
              <FlagCard key={idx} flag={flag} />
            ))}
          </div>
        </div>
      )}

      {/* Legacy Flags & Gaps (backward compatibility) */}
      {!feasibilityData.detailed_flags && (feasibilityData.flags?.length > 0 || feasibilityData.gaps?.length > 0) && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <span className="mr-2">⚠️</span> Flags & Gaps
          </h3>
          <div className="flex flex-wrap gap-2">
            {feasibilityData.flags?.map((flag: string, index: number) => (
              <span key={index} className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm">
                {flag}
              </span>
            ))}
            {feasibilityData.gaps?.map((gap: string, index: number) => (
              <span key={index} className="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm">
                {gap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Improvement Opportunities */}
      {feasibilityData.improvement_opportunities && feasibilityData.improvement_opportunities.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">💡 Improvement Opportunities</h3>
          <div className="space-y-3">
            {feasibilityData.improvement_opportunities.map((opp: any, idx: number) => (
              <div key={idx} className="flex items-start gap-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex-shrink-0 w-16 text-center">
                  <span className="text-xl font-bold text-blue-600">+{opp.estimated_impact}</span>
                  <p className="text-xs text-blue-600">pts</p>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-gray-900">{opp.action}</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      opp.difficulty === 'Easy' ? 'bg-green-100 text-green-700' :
                      opp.difficulty === 'Medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {opp.difficulty}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">{opp.details}</p>
                  <p className="text-xs text-gray-500 mt-1">Category: {opp.category}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Assessment Summary */}
      {feasibilityData.ai_assessment && (feasibilityData.ai_assessment.summary || feasibilityData.ai_assessment.assessment) && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">🤖 AI Assessment</h3>

          {(feasibilityData.ai_assessment.summary || feasibilityData.ai_assessment.assessment) && (
            <p className="text-gray-700 mb-4">
              {feasibilityData.ai_assessment.summary || feasibilityData.ai_assessment.assessment}
            </p>
          )}

          <div className="grid md:grid-cols-2 gap-4 mb-4">
            {feasibilityData.ai_assessment.strengths && feasibilityData.ai_assessment.strengths.length > 0 && (
              <div>
                <h4 className="font-medium text-green-700 mb-2">✅ Strengths</h4>
                <ul className="space-y-1">
                  {feasibilityData.ai_assessment.strengths.map((s: string, i: number) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-green-500 mt-0.5">•</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {feasibilityData.ai_assessment.considerations && feasibilityData.ai_assessment.considerations.length > 0 && (
              <div>
                <h4 className="font-medium text-yellow-700 mb-2">⚠️ Considerations</h4>
                <ul className="space-y-1">
                  {feasibilityData.ai_assessment.considerations.map((c: string, i: number) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-yellow-500 mt-0.5">•</span>
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {feasibilityData.ai_assessment.recommendation && (
            <div className="pt-3 border-t border-blue-200">
              <span className="text-sm font-medium text-gray-600">Recommendation: </span>
              <span className={`font-semibold ${
                feasibilityData.ai_assessment.recommendation.includes('Highly') ? 'text-green-600' :
                feasibilityData.ai_assessment.recommendation.includes('Not') ? 'text-red-600' :
                'text-blue-600'
              }`}>
                {feasibilityData.ai_assessment.recommendation}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Protocol Requirements vs Site Capabilities */}
      {feasibilityData.requirements_comparison && feasibilityData.requirements_comparison.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Protocol Requirements vs Site Capabilities</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b-2 border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Requirement</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Protocol Needs</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Site Has</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-900">Status</th>
                </tr>
              </thead>
              <tbody>
                {feasibilityData.requirements_comparison.map((req: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <span className="font-medium text-gray-900">{req.requirement}</span>
                      {req.category && (
                        <span className="block text-xs text-gray-500">{req.category}</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-gray-700">
                      {req.protocol_need || req.protocol_needs || 'Required'}
                    </td>
                    <td className="py-3 px-4 text-gray-700">
                      {req.site_capability || req.site_has || '—'}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {typeof req.status === 'string' && ['MET', 'PARTIALLY_MET', 'NOT_MET', 'UNKNOWN'].includes(req.status) ? (
                        <span className={`inline-flex px-3 py-1 rounded-full text-sm font-medium ${
                          req.status === 'MET' ? 'bg-green-100 text-green-800' :
                          req.status === 'PARTIALLY_MET' ? 'bg-yellow-100 text-yellow-800' :
                          req.status === 'NOT_MET' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {req.status.replace('_', ' ')}
                        </span>
                      ) : (
                        <span className="text-xl">{req.status || '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {feasibilityData.requirements_comparison.some((r: any) => r.notes) && (
            <div className="mt-4 text-sm text-gray-600">
              {feasibilityData.requirements_comparison
                .filter((r: any) => r.notes)
                .map((r: any, i: number) => (
                  <p key={i}>• <strong>{r.requirement}:</strong> {r.notes}</p>
                ))}
            </div>
          )}
        </div>
      )}

      {/* CT.gov Verification Section */}
      <CTGovVerificationSection siteProfile={siteProfile} />

      {/* Data Sources Footer */}
      <div className="text-center text-sm text-gray-500">
        Data Sources: {feasibilityData.data_sources?.join(', ') || 'Site Profile, ClinicalTrials.gov'}
        {feasibilityData.assessed_at && (
          <span> | Assessed: {new Date(feasibilityData.assessed_at).toLocaleString()}</span>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex justify-center gap-4">
        <button
          onClick={() => setCurrentView('review')}
          className="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
        >
          Review Answers
        </button>
        <button
          onClick={() => setCurrentView('upload')}
          className="px-6 py-3 bg-white text-gray-700 border border-gray-300 rounded-lg font-medium hover:bg-gray-50 transition-colors"
        >
          Back to Upload
        </button>
      </div>
    </div>
  );
}

// Submitted View
function SubmittedView({ survey, onReturnToInbox }: any) {
  return (
    <div className="max-w-2xl mx-auto text-center">
      <div className="bg-white p-12 rounded-lg shadow">
        <CheckCircle className="w-20 h-20 mx-auto text-green-500 mb-6" />

        <h2 className="text-2xl font-bold text-black mb-4">Survey Submitted Successfully!</h2>

        <p className="text-black mb-6">
          The completed feasibility assessment for <strong>{survey.study_name}</strong> has been sent to the sponsor.
        </p>

        <div className="bg-gray-50 p-6 rounded mb-6">
          <h3 className="font-semibold text-black mb-4">Download Copies</h3>
          <div className="flex justify-center space-x-4">
            <a
              href={`${API_URL}${survey.pdf_download}`}
              className="flex items-center px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              <Download className="w-4 h-4 mr-2" />
              PDF Report
            </a>
            <a
              href={`${API_URL}${survey.excel_download}`}
              className="flex items-center px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              <Download className="w-4 h-4 mr-2" />
              Excel Export
            </a>
          </div>
        </div>

        <div className="space-y-3 mb-8">
          <div className="flex items-center justify-center text-sm text-black">
            <Clock className="w-4 h-4 mr-2" />
            Submitted at {new Date().toLocaleString()}
          </div>
          <div className="flex items-center justify-center text-sm text-black">
            <Mail className="w-4 h-4 mr-2" />
            Sent to sponsor via email
          </div>
        </div>

        <button
          onClick={onReturnToInbox}
          className="bg-gray-600 text-white px-6 py-2 rounded hover:bg-gray-700"
        >
          Return to Inbox
        </button>
      </div>
    </div>
  );
}

// Dashboard View Component
interface DashboardViewProps {
  siteId: number;
  onNavigateToInbox: () => void;
}

function DashboardView({ siteId, onNavigateToInbox }: DashboardViewProps) {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardStats();
  }, [siteId]);

  const loadDashboardStats = async () => {
    try {
      // In production, this would be a real endpoint
      // For now, we'll calculate from survey data
      const inboxData = await api.getInbox(siteId);

      const surveys = inboxData.surveys || [];

      // Calculate statistics
      const totalSurveys = surveys.length;
      const submittedSurveys = surveys.filter((s: any) => s.status === 'submitted').length;
      const pendingSurveys = surveys.filter((s: any) => s.status === 'pending').length;
      const avgFeasibilityScore = surveys
        .filter((s: any) => s.feasibility_score)
        .reduce((acc: number, s: any) => acc + s.feasibility_score, 0) /
        (surveys.filter((s: any) => s.feasibility_score).length || 1);

      const avgCompletionRate = surveys
        .filter((s: any) => s.completion_percentage)
        .reduce((acc: number, s: any) => acc + s.completion_percentage, 0) /
        (surveys.filter((s: any) => s.completion_percentage).length || 1);

      // Time savings calculation (45 minutes per survey with >50% completion)
      const timeSaved = surveys
        .filter((s: any) => s.completion_percentage > 50)
        .length * 45;

      setStats({
        totalSurveys,
        submittedSurveys,
        pendingSurveys,
        avgFeasibilityScore: Math.round(avgFeasibilityScore),
        avgCompletionRate: Math.round(avgCompletionRate),
        timeSaved,
        recentSurveys: surveys.slice(0, 5)
      });
    } catch (error) {
      console.error('Error loading dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="animate-spin w-8 h-8 text-green-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="bg-gradient-to-r from-green-600 to-green-700 text-white p-8 rounded-lg shadow-lg">
        <h1 className="text-3xl font-bold mb-2">SiteSync Dashboard</h1>
        <p className="text-green-100">
          Transforming clinical research feasibility assessments through AI
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid md:grid-cols-4 gap-6">
        <MetricCard
          icon={<Clock className="w-6 h-6" />}
          value={`${stats?.timeSaved || 0} min`}
          label="Time Saved"
          color="text-blue-600"
          bgColor="bg-blue-50"
        />
        <MetricCard
          icon={<Target className="w-6 h-6" />}
          value={`${stats?.avgFeasibilityScore || 0}/100`}
          label="Avg. Feasibility Score"
          color="text-green-600"
          bgColor="bg-green-50"
        />
        <MetricCard
          icon={<TrendingUp className="w-6 h-6" />}
          value={`${stats?.avgCompletionRate || 0}%`}
          label="Auto-completion Rate"
          color="text-purple-600"
          bgColor="bg-purple-50"
        />
        <MetricCard
          icon={<CheckCircle className="w-6 h-6" />}
          value={`${stats?.submittedSurveys || 0}/${stats?.totalSurveys || 0}`}
          label="Surveys Completed"
          color="text-orange-600"
          bgColor="bg-orange-50"
        />
      </div>

      {/* Efficiency Comparison */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold text-black mb-4">Efficiency Gains</h2>
        <div className="grid md:grid-cols-2 gap-8">
          <div>
            <h3 className="font-semibold text-black mb-3">Traditional Process</h3>
            <div className="space-y-3">
              <ProcessStep
                time="15 min"
                task="Manual protocol review"
                icon={<FileText className="w-4 h-4" />}
              />
              <ProcessStep
                time="20 min"
                task="Site capability matching"
                icon={<Users className="w-4 h-4" />}
              />
              <ProcessStep
                time="25 min"
                task="Form completion"
                icon={<ClipboardCheck className="w-4 h-4" />}
              />
              <div className="pt-3 border-t">
                <span className="text-lg font-bold text-red-600">Total: 60 minutes</span>
              </div>
            </div>
          </div>

          <div>
            <h3 className="font-semibold text-black mb-3">SiteSync Process</h3>
            <div className="space-y-3">
              <ProcessStep
                time="1 min"
                task="Upload protocol & survey"
                icon={<Upload className="w-4 h-4" />}
                automated
              />
              <ProcessStep
                time="2 min"
                task="AI extraction & scoring"
                icon={<Zap className="w-4 h-4" />}
                automated
              />
              <ProcessStep
                time="12 min"
                task="Review & complete subjective"
                icon={<Edit3 className="w-4 h-4" />}
              />
              <div className="pt-3 border-t">
                <span className="text-lg font-bold text-green-600">Total: 15 minutes</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-green-50 p-4 rounded">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-green-800">Time Savings</span>
            <span className="text-2xl font-bold text-green-600">75% Reduction</span>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-black">Recent Surveys</h2>
          <button
            onClick={onNavigateToInbox}
            className="text-green-600 hover:text-green-700 text-sm font-medium"
          >
            View All →
          </button>
        </div>

        <div className="space-y-3">
          {stats?.recentSurveys?.map((survey: any) => (
            <div key={survey.id} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded">
              <div className="flex-1">
                <p className="font-medium text-black">{survey.study_name}</p>
                <p className="text-sm text-black">{survey.sponsor_name}</p>
              </div>
              <div className="flex items-center space-x-4">
                {survey.feasibility_score && (
                  <span className="text-lg font-semibold text-green-600">
                    {survey.feasibility_score}/100
                  </span>
                )}
                <StatusBadge status={survey.status} />
              </div>
            </div>
          ))}

          {(!stats?.recentSurveys || stats.recentSurveys.length === 0) && (
            <p className="text-center text-black py-8">No surveys yet</p>
          )}
        </div>
      </div>

      {/* Value Proposition */}
      <div className="bg-gradient-to-br from-gray-50 to-gray-100 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Why SiteSync?</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <ValueProp
            icon={<Zap className="w-8 h-8 text-yellow-500" />}
            title="AI-Powered"
            description="GPT-4 extracts protocol requirements and auto-fills 70%+ of questions"
          />
          <ValueProp
            icon={<Shield className="w-8 h-8 text-blue-500" />}
            title="Accuracy"
            description="Confidence scoring and source attribution for every response"
          />
          <ValueProp
            icon={<Award className="w-8 h-8 text-green-500" />}
            title="Professional"
            description="PDF and Excel exports ready for sponsor submission"
          />
        </div>
      </div>
    </div>
  );
}

// Helper Components
function MetricCard({ icon, value, label, color, bgColor }: any) {
  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className={`inline-flex p-3 rounded-lg ${bgColor} ${color} mb-3`}>
        {icon}
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <p className="text-sm text-black mt-1">{label}</p>
    </div>
  );
}

function ProcessStep({ time, task, icon, automated = false }: any) {
  return (
    <div className="flex items-center space-x-3">
      <div className={`p-2 rounded ${automated ? 'bg-green-100' : 'bg-gray-100'}`}>
        {icon}
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium text-black">{task}</p>
        {automated && <span className="text-xs text-green-600">Automated</span>}
      </div>
      <span className="text-sm text-black">{time}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { bg: string; text: string }> = {
    submitted: { bg: 'bg-green-100', text: 'text-green-800' },
    autofilled: { bg: 'bg-blue-100', text: 'text-blue-800' },
    processing: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
    pending: { bg: 'bg-gray-100', text: 'text-gray-800' }
  };
  const config = statusConfig[status] || { bg: 'bg-gray-100', text: 'text-gray-800' };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      {status}
    </span>
  );
}

function ValueProp({ icon, title, description }: any) {
  return (
    <div className="text-center">
      <div className="inline-flex p-4 rounded-full bg-white shadow-md mb-3">
        {icon}
      </div>
      <h3 className="font-semibold mb-1">{title}</h3>
      <p className="text-sm text-black">{description}</p>
    </div>
  );
}

// Site Profile View Component
function SiteProfileView({ profile, onUpdate, onBack }: any) {
  if (!profile) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        <span className="ml-2 text-black">Loading site profile...</span>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBack}
            className="p-2 text-black hover:text-black rounded-lg hover:bg-gray-100"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-black">{profile.name}</h1>
            <p className="text-black">Comprehensive Clinical Research Center Profile</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-green-600">{profile.metadata?.profile_completeness || 100}%</div>
          <p className="text-sm text-black">Profile Complete</p>
        </div>
      </div>

      <div className="grid gap-6">
        {/* Population Capabilities */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center text-blue-600">
            <Users className="w-6 h-6 mr-3" />
            Population Capabilities
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-blue-50 p-4 rounded-lg">
              <h3 className="font-semibold text-blue-800 mb-2">Annual Patient Volume</h3>
              <p className="text-2xl font-bold text-blue-600">
                {profile.population_capabilities?.annual_patient_volume?.toLocaleString() || '15,000'}
              </p>
              <p className="text-sm text-blue-700">patients per year</p>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <h3 className="font-semibold text-green-800 mb-2">Age Groups</h3>
              <div className="flex flex-wrap gap-1">
                {(profile.population_capabilities?.age_groups_treated || ['Pediatric', 'Adult', 'Geriatric']).map((group: string, idx: number) => (
                  <span key={idx} className="px-2 py-1 bg-green-200 text-green-800 rounded text-xs">
                    {group}
                  </span>
                ))}
              </div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg">
              <h3 className="font-semibold text-purple-800 mb-2">Therapeutic Areas</h3>
              <div className="space-y-1">
                {(profile.population_capabilities?.therapeutic_areas || profile.population_capabilities?.common_health_conditions || ['Gastroenterology (Hepatology)', 'Endocrinology', 'Cardiology']).slice(0, 3).map((area: string, idx: number) => (
                  <p key={idx} className="text-sm text-purple-700">• {area}</p>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 p-3 bg-gray-50 rounded">
            <p className="text-sm text-black">
              <strong>Special Populations:</strong> {profile.population_capabilities?.special_populations || 'Diverse urban population; ~30% elderly, 20% pediatric patients'}
            </p>
          </div>
        </div>

        {/* Staff & Experience */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center text-green-600">
            <Users className="w-6 h-6 mr-3" />
            Staff & Experience
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-green-50 p-4 rounded-lg">
              <h3 className="font-semibold text-green-800 mb-2">Principal Investigators</h3>
              <p className="text-2xl font-bold text-green-600">
                {(() => {
                  const pi = profile.staff_and_experience?.principal_investigator ? 1 : 0;
                  const subs = profile.staff_and_experience?.sub_investigators?.length || 0;
                  const oldCount = profile.staff_and_experience?.investigators?.count || 3;
                  return pi + subs || oldCount;
                })()}
              </p>
              <p className="text-sm text-green-700">
                {profile.staff_and_experience?.principal_investigator?.name ? (
                  <>PI: {profile.staff_and_experience.principal_investigator.name} ({profile.staff_and_experience.principal_investigator.specialty})</>
                ) : (
                  <>Avg {profile.staff_and_experience?.investigators?.average_years_experience || 12} years experience</>
                )}
              </p>
              <div className="mt-2">
                {(profile.staff_and_experience?.principal_investigator?.specialty
                  ? [profile.staff_and_experience.principal_investigator.specialty].concat(
                      (profile.staff_and_experience?.sub_investigators || []).map((s: any) => s.specialty)
                    )
                  : profile.staff_and_experience?.investigators?.specialties || ['Cardiology', 'Oncology']
                ).slice(0, 3).map((specialty: string, idx: number) => (
                  <span key={idx} className="inline-block px-2 py-1 bg-green-200 text-green-800 rounded text-xs mr-1 mb-1">
                    {specialty}
                  </span>
                ))}
              </div>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg">
              <h3 className="font-semibold text-blue-800 mb-2">Study Coordinators</h3>
              <p className="text-2xl font-bold text-blue-600">
                {profile.staff_and_experience?.study_coordinators?.count || profile.staff_and_experience?.coordinators?.count || 4}
              </p>
              <p className="text-sm text-blue-700">
                {profile.staff_and_experience?.study_coordinators?.experience || profile.staff_and_experience?.coordinators?.experience || `Avg ${profile.staff_and_experience?.coordinators?.average_years_experience || 6} years experience`}
              </p>
              <div className="mt-2">
                {(profile.staff_and_experience?.study_coordinators?.certifications || profile.staff_and_experience?.coordinators?.certifications || ['ACRP-CCRC', 'SOCRA-CCRP']).map((cert: string, idx: number) => (
                  <p key={idx} className="text-xs text-blue-700">• {cert}</p>
                ))}
              </div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg">
              <h3 className="font-semibold text-purple-800 mb-2">Other Research Staff</h3>
              <div className="space-y-1">
                <p className="text-sm text-purple-700">• {profile.staff_and_experience?.research_nurses?.count || profile.staff_and_experience?.other_staff?.research_nurses || 2} Research Nurses</p>
                <p className="text-sm text-purple-700">• {profile.staff_and_experience?.pharmacist?.available ? '1' : profile.staff_and_experience?.other_staff?.pharmacist || 1} Pharmacist</p>
                <p className="text-sm text-purple-700">• {profile.staff_and_experience?.lab_technician?.available ? '1' : profile.staff_and_experience?.other_staff?.lab_technician || 1} Lab Technician</p>
                <p className="text-sm text-purple-700">• {profile.staff_and_experience?.regulatory_specialist?.available ? '1' : profile.staff_and_experience?.other_staff?.regulatory_specialist || 1} Regulatory Specialist</p>
              </div>
            </div>
          </div>
        </div>

        {/* Equipment & Facilities */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center text-purple-600">
            <Sliders className="w-6 h-6 mr-3" />
            Equipment & Facilities
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Imaging Equipment</h3>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(profile.facilities_and_equipment?.imaging || {})
                  .filter(([key, value]) => value === true && key !== 'notes')
                  .map(([equipment], idx) => (
                    <div key={idx} className="flex items-center p-2 bg-purple-50 rounded">
                      <CheckCircle className="w-4 h-4 text-purple-600 mr-2" />
                      <span className="text-sm text-purple-800">{equipment}</span>
                    </div>
                  ))}
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Laboratory Capabilities</h3>
              <div className="space-y-2">
                {profile.facilities_and_equipment?.laboratory?.on_site_lab && (
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                    <span className="text-sm text-gray-800">On-site Clinical Lab (CLIA Certified)</span>
                  </div>
                )}
                {profile.facilities_and_equipment?.pharmacy?.investigational_drug_storage?.freezer_minus80C && (
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                    <span className="text-sm text-gray-800">-80°C Freezer Available</span>
                  </div>
                )}
                {profile.facilities_and_equipment?.pharmacy?.temperature_monitoring && (
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                    <span className="text-sm text-gray-800">Temperature Monitoring & Backup Power</span>
                  </div>
                )}
                {profile.facilities_and_equipment?.laboratory?.sample_processing && (
                  <div className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                    <span className="text-sm text-gray-800">Sample Processing Available</span>
                  </div>
                )}
                {/* Show capabilities array if available */}
                {Array.isArray(profile.facilities_and_equipment?.laboratory?.capabilities) &&
                  profile.facilities_and_equipment.laboratory.capabilities.slice(0, 4).map((cap: string, idx: number) => (
                    <div key={idx} className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                      <span className="text-sm text-gray-800 capitalize">{cap}</span>
                    </div>
                  ))
                }
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div className="text-center p-2 bg-blue-50 rounded">
                  <p className="text-lg font-bold text-blue-600">
                    {typeof profile.facilities_and_equipment?.procedure_rooms === 'object'
                      ? profile.facilities_and_equipment?.procedure_rooms?.count
                      : profile.facilities_and_equipment?.procedure_rooms || 4}
                  </p>
                  <p className="text-xs text-blue-700">Procedure Rooms</p>
                </div>
                <div className="text-center p-2 bg-green-50 rounded">
                  <p className="text-lg font-bold text-green-600">
                    {typeof profile.facilities_and_equipment?.infusion === 'object'
                      ? profile.facilities_and_equipment?.infusion?.infusion_chairs
                      : profile.facilities_and_equipment?.infusion_chairs || 4}
                  </p>
                  <p className="text-xs text-green-700">Infusion Chairs</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center text-orange-600">
            <BarChart3 className="w-6 h-6 mr-3" />
            Performance Metrics
          </h2>
          <div className="grid md:grid-cols-4 gap-6">
            <div className="text-center bg-orange-50 p-4 rounded-lg">
              <p className="text-2xl font-bold text-orange-600">
                {profile.historical_performance?.studies_completed_last_5_years || 45}
              </p>
              <p className="text-sm text-orange-700">Studies (5 years)</p>
            </div>
            <div className="text-center bg-green-50 p-4 rounded-lg">
              <p className="text-2xl font-bold text-green-600">
                {profile.historical_performance?.enrollment_success_rate || '85%'}
              </p>
              <p className="text-sm text-green-700">Enrollment Success</p>
            </div>
            <div className="text-center bg-blue-50 p-4 rounded-lg">
              <p className="text-2xl font-bold text-blue-600">
                {profile.historical_performance?.retention_rate || '95%'}
              </p>
              <p className="text-sm text-blue-700">Retention Rate</p>
            </div>
            <div className="text-center bg-purple-50 p-4 rounded-lg">
              <p className="text-2xl font-bold text-purple-600">
                {profile.historical_performance?.current_active_studies || 6}
              </p>
              <p className="text-sm text-purple-700">Active Studies</p>
            </div>
          </div>
          <div className="mt-4 grid md:grid-cols-3 gap-4">
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">Studies by Phase</h4>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-800">Phase I:</span>
                  <span className="text-sm text-gray-800 font-medium">{profile.historical_performance?.studies_by_phase?.['Phase I'] || 2}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-800">Phase II:</span>
                  <span className="text-sm text-gray-800 font-medium">{profile.historical_performance?.studies_by_phase?.['Phase II'] || 10}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-800">Phase III:</span>
                  <span className="text-sm text-gray-800 font-medium">{profile.historical_performance?.studies_by_phase?.['Phase III'] || 20}</span>
                </div>
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">Therapeutic Experience</h4>
              <div className="space-y-1">
                {(Array.isArray(profile.historical_performance?.therapeutic_experience)
                  ? profile.historical_performance.therapeutic_experience
                  : ['NASH', 'Type 2 Diabetes', 'Obesity', 'Cardiovascular outcomes', 'Oncology (solid tumors)', 'Infectious Disease (HCV/HIV)']
                ).slice(0, 6).map((area: string, idx: number) => (
                  <div key={idx} className="flex items-center">
                    <CheckCircle className="w-3 h-3 text-blue-600 mr-2" />
                    <span className="text-sm text-gray-800">{area}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">Quality Metrics</h4>
              <div className="space-y-1">
                <p className="text-sm text-gray-800">Protocol Deviations: <span className="font-medium">{profile.historical_performance?.protocol_deviation_rate || '<2%'}</span></p>
                <p className="text-sm text-gray-800">Query Resolution: <span className="font-medium">{profile.historical_performance?.average_query_resolution_time || '3 days'}</span></p>
              </div>
            </div>
          </div>
        </div>

        {/* Sponsor Experience */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center text-teal-600">
            <Award className="w-6 h-6 mr-3" />
            Sponsor Experience
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Sponsor Types</h3>
              <div className="space-y-2">
                {(profile.historical_performance?.sponsor_types_experience || ['Industry (Pharma/CRO)', 'NIH-funded', 'Investigator-Initiated']).map((type: string, idx: number) => (
                  <div key={idx} className="flex items-center">
                    <CheckCircle className="w-4 h-4 text-teal-600 mr-2" />
                    <span className="text-sm text-gray-800">{type}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Operational Capabilities</h3>
              <div className="space-y-2">
                <p className="text-sm text-gray-800"><strong>Data Systems:</strong> {profile.operational_capabilities?.data_systems || profile.operational_capabilities?.emr_system || 'CTMS (OnCore), EHR (Epic), EDC experience'}</p>
                <p className="text-sm text-gray-800"><strong>Pharmacy:</strong> {profile.operational_capabilities?.pharmacy || 'On-site investigational pharmacy'}</p>
                <p className="text-sm text-gray-800"><strong>Inpatient Support:</strong> {profile.operational_capabilities?.inpatient_capability ? 'Available' : 'Not Available'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Compliance & Training */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center text-red-600">
            <Shield className="w-6 h-6 mr-3" />
            Compliance & Training
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-red-50 p-4 rounded-lg">
              <h3 className="font-semibold text-red-800 mb-2">IRB & Ethics</h3>
              <p className="text-sm text-red-700">{profile.compliance_and_training?.IRB_review || 'Local Institutional IRB; can use central IRB (avg 4 weeks)'}</p>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <h3 className="font-semibold text-green-800 mb-2">Training & Certification</h3>
              <div className="space-y-1">
                <div className="flex items-center">
                  <CheckCircle className="w-4 h-4 text-green-600 mr-1" />
                  <span className="text-xs text-green-700">GCP Certified</span>
                </div>
                <div className="flex items-center">
                  <CheckCircle className="w-4 h-4 text-green-600 mr-1" />
                  <span className="text-xs text-green-700">HSP Training</span>
                </div>
                <div className="flex items-center">
                  <CheckCircle className="w-4 h-4 text-green-600 mr-1" />
                  <span className="text-xs text-green-700">IATA Certified</span>
                </div>
              </div>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg">
              <h3 className="font-semibold text-blue-800 mb-2">Audit History</h3>
              <p className="text-sm text-blue-700">{profile.compliance_and_training?.audit_history || 'FDA inspection (2019) no Form 483s; 5 sponsor audits no critical findings'}</p>
            </div>
          </div>
        </div>

        {/* Summary Card */}
        <div className="bg-gradient-to-r from-green-500 to-blue-600 text-white rounded-xl shadow-lg p-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold mb-2">Ready for Clinical Research Excellence</h2>
            <p className="text-green-100 mb-4">
              With {profile.population_capabilities?.annual_patient_volume?.toLocaleString() || '50,000'} patients annually,
              {profile.staff_and_experience?.study_coordinators?.count || profile.staff_and_experience?.coordinators?.count || 4} experienced coordinators, and
              {profile.historical_performance?.studies_completed_last_5_years || 45} studies completed over 5 years,
              this site delivers exceptional feasibility and enrollment performance.
            </p>
            <div className="flex justify-center space-x-8">
              <div className="text-center">
                <p className="text-2xl font-bold">{profile.metadata?.profile_completeness || 100}%</p>
                <p className="text-sm text-green-100">Profile Complete</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold">{profile.historical_performance?.enrollment_success_rate || '85%'}</p>
                <p className="text-sm text-green-100">Success Rate</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold">{profile.historical_performance?.retention_rate || '95%'}</p>
                <p className="text-sm text-green-100">Retention</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}