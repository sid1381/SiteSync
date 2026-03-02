# SiteSync Screener Frontend — Complete Build Specification
## For Claude Code Implementation

## OVERVIEW

Create `frontend/app/screener/page.tsx` — a single-file React application for the
SiteSync Screener tool. This is a SEPARATE page from the Core product (which lives
at frontend/app/page.tsx). Users access it at http://localhost:3000/screener.

The Screener is sponsor/consultant-facing. The people using this are strategic
consultants at firms like Arthur D. Little, or clinical operations teams at
pharma sponsors. The UI should feel like a professional intelligence tool —
clean, data-dense, confident. Think Bloomberg Terminal meets modern SaaS.

## TECH STACK (match existing patterns)

- Next.js 14+ with App Router (same as existing frontend)
- TypeScript
- Tailwind CSS (already configured)
- Lucide React icons (already installed)
- No additional dependencies needed

## API BASE URL

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
```

## FOUR VIEWS

The page manages state with useState to switch between views:

```typescript
type ScreenerView = 'dashboard' | 'protocol_review' | 'country_ranking' | 'site_ranking' | 'site_detail';
const [currentView, setCurrentView] = useState<ScreenerView>('dashboard');
```

---

## VIEW 1: DASHBOARD (Project List)

**What the user sees:**
- Page header: "SiteSync Screener" with subtitle "AI-Powered Site Selection Intelligence"
- "New Project" button (prominent, top right)
- Table/card list of existing projects showing:
  - Project name
  - Status (draft / analyzing / countries_ready / sites_ready / complete)
  - Indication (from protocol extraction)
  - Date created
  - Number of countries analyzed
  - Number of shortlisted sites
  - Click to open → goes to appropriate view based on status

**API calls:**
```typescript
// On mount
GET /screener/projects → { projects: ScreenerProjectResponse[] }

// Create new project
POST /screener/projects
  body: { name: string }
  → ScreenerProjectResponse
```

**New Project flow:**
1. User clicks "New Project"
2. Modal or inline form asks for project name
3. POST creates project with status "draft"
4. Navigate to protocol upload view

---

## VIEW 2: PROTOCOL REVIEW

**Two sub-states:** upload (before protocol) and review (after extraction)

### Sub-state: Upload
- Project name displayed at top
- Large drag-and-drop zone for PDF upload (same pattern as Core)
- "Upload Protocol" button
- Brief instructions: "Upload the study protocol PDF. Our AI will extract key
  requirements to search for qualified sites worldwide."

**API call:**
```typescript
POST /screener/projects/{id}/upload-protocol
  body: FormData with 'file' field
  → ProtocolUploadResponse {
      project_id, status,
      extracted_criteria: {
        indication, therapeutic_area, phase, sponsor,
        enrollment_target, patients_per_site, duration,
        inclusion_criteria[], exclusion_criteria[],
        required_equipment[], required_staff[], procedures[],
        study_title
      }
    }
```

### Sub-state: Review
After upload, show extracted criteria for user review:

**Layout — two columns:**

Left column (60%): Extracted protocol details in organized sections
- Study Info: title, phase, sponsor, therapeutic area
- Population: indication, enrollment target, age range
- Criteria: inclusion list, exclusion list
- Requirements: equipment, staff qualifications
- Procedures: list of required procedures
- Timeline: duration, visit count

Right column (40%):
- Confidence indicator (overall extraction quality)
- Edit capability — user can click any field to modify
- "Confirm & Analyze" button (large, prominent)

**On confirm:**
```typescript
POST /screener/projects/{id}/confirm-protocol
  body: { criteria: { ...edited_criteria } }
  → triggers country analysis
  → navigate to country_ranking view
```

**Loading state between confirm and country ranking:**
Show animated progress: "Searching ClinicalTrials.gov..." → "Analyzing 65 countries..."
→ "Scoring feasibility..." → "Generating regulatory summaries..."

---

## VIEW 3: COUNTRY RANKING

This is the core intelligence view. Dense data, well organized.

**Header section:**
- Project name + indication + phase as breadcrumb
- "Back to Projects" link
- Summary stats bar: "X countries analyzed • Y total trials found • Z competing trials"

**Controls row:**
- Weight adjustment panel (collapsible):
  - 5 sliders for country weights (trial experience, site density, competition,
    regulatory, prevalence) — each 0-100, must sum concept (show percentages)
  - "Recalculate" button when weights change
  - "Reset to Default" link
- Filter controls: region/continent dropdown, minimum score threshold

**Main content: Country ranking table**

Columns:
| Rank | Country | Score | Trials | Sites | Competing | Trial Exp | Site Density | Competition | Regulatory | Prevalence |
|------|---------|-------|--------|-------|-----------|-----------|-------------|-------------|------------|------------|

- Rank: numbered 1, 2, 3...
- Country: country name with flag emoji (optional)
- Score: composite_score displayed as /100 with color coding:
  - 70+: green
  - 50-69: amber/yellow
  - <50: red
- Trials: indication_trials count
- Sites: site_count
- Competing: actively_recruiting (competing trials — higher = worse, show in orange/red)
- Sub-scores: show as small bars or numbers

**Row interaction:**
- Hover highlights row
- Click row → navigate to site_ranking view for that country
- Expandable row detail (optional): shows regulatory_summary and prevalence_estimate

**API call:**
```typescript
GET /screener/projects/{id}/countries
  → CountryRankingResponse {
      project_id, total_countries,
      countries: CountryScore[]
    }

// When weights change:
POST /screener/projects/{id}/countries/refresh
  body: { weights: { trial_experience, site_density, competition, regulatory, prevalence } }
  → CountryRankingResponse (recalculated)
```

---

## VIEW 4: SITE RANKING (within a country)

**Header:**
- Breadcrumb: Projects > [Project Name] > [Country Name]
- Country summary card: total sites, total trials, competing trials, country score
- "Back to Countries" link

**Controls:**
- Weight adjustment panel for SITE weights (5 sliders):
  experience, pi_strength, capacity, compliance, protocol_match
- Filter: minimum score, minimum trial count
- Search box to filter by site name

**Main content: Site ranking table**

Columns:
| Rank | Site Name | City | PI | Trials | Indication | Score | Flags |
|------|-----------|------|----|--------|------------|-------|-------|

- Rank: numbered
- Site Name: facility name
- City: city, state (if US)
- PI: primary investigator name (may be "Unknown" — that's fine)
- Trials: total trial_count
- Indication: indication_trial_count (trials matching the protocol's indication)
- Score: final_score as /100 with color coding
- Flags:
  - Red flags shown as red dots/badges
  - Yellow flags as amber
  - Strengths as green checkmarks
  - Shortlist star icon (toggle)

**Row interaction:**
- Click row → navigate to site_detail view
- Star icon → toggle shortlist (POST /screener/projects/{id}/shortlist)

**Shortlist panel (collapsible sidebar or tab):**
- Shows shortlisted sites across all countries
- Quick count: "X sites shortlisted"
- Can remove from shortlist

**API calls:**
```typescript
GET /screener/projects/{id}/countries/{code}/sites
  → SiteRankingResponse {
      project_id, country_code, country_name,
      total_sites,
      sites: SiteScore[]
    }

POST /screener/projects/{id}/shortlist
  body: { site_id: string, action: "add" | "remove" }
  → ShortlistResponse

GET /screener/projects/{id}/shortlist
  → ShortlistSummary { total: int, sites: SiteScore[] }
```

---

## VIEW 5: SITE DETAIL (optional — stretch goal)

A detail card/modal for a single site. Shows:
- Full site info (name, city, country)
- Investigator details
- Trial history breakdown
- Score breakdown with visual bars
- Red flags, yellow flags, strengths as lists
- Gap analysis text (AI-generated)
- "Add to Shortlist" / "Remove from Shortlist" button

```typescript
GET /screener/projects/{id}/sites/{site_id}
  → SiteDetailResponse (full site data)
```

---

## DESIGN GUIDELINES

### Color System
```
Primary:      #1e40af (deep blue — professional, trustworthy)
Primary Light: #3b82f6
Accent:       #059669 (emerald green — for positive scores/strengths)
Warning:      #d97706 (amber — for medium scores/yellow flags)
Danger:       #dc2626 (red — for low scores/red flags)
Background:   #f8fafc (slate-50)
Surface:      #ffffff
Text Primary: #1e293b (slate-800)
Text Secondary: #64748b (slate-500)
Border:       #e2e8f0 (slate-200)
```

### Typography
- Headers: font-bold, text-slate-900
- Body: text-slate-700 (NEVER light grey — must be readable)
- Data values: font-semibold, monospace for numbers
- Small labels: text-xs text-slate-500 uppercase tracking-wider

### Score Visualization
For composite scores (0-100), use a colored badge:
```typescript
function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? 'bg-emerald-100 text-emerald-800'
    : score >= 50 ? 'bg-amber-100 text-amber-800'
    : 'bg-red-100 text-red-800';
  return <span className={`px-2 py-1 rounded-full text-sm font-bold ${color}`}>{score}</span>;
}
```

### Component Patterns
- Tables: clean borders, hover states, sortable columns (click header to sort)
- Cards: white bg, subtle shadow, rounded-lg
- Buttons: primary (blue), secondary (outline), danger (red)
- Loading: skeleton loaders, not spinners
- Empty states: clear messaging with call-to-action

### Layout
- Max width: max-w-7xl mx-auto (consistent with typical dashboard)
- Navigation: minimal top bar with SiteSync logo, "Core" and "Screener" tabs
- The page should feel distinct from Core but clearly part of the same product family

---

## STATE MANAGEMENT

```typescript
// Core state
const [currentView, setCurrentView] = useState<ScreenerView>('dashboard');
const [projects, setProjects] = useState<Project[]>([]);
const [activeProject, setActiveProject] = useState<Project | null>(null);
const [protocolCriteria, setProtocolCriteria] = useState<ProtocolCriteria | null>(null);
const [countries, setCountries] = useState<CountryScore[]>([]);
const [sites, setSites] = useState<SiteScore[]>([]);
const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
const [shortlist, setShortlist] = useState<SiteScore[]>([]);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);

// Weight state
const [countryWeights, setCountryWeights] = useState({
  trial_experience: 0.30,
  site_density: 0.25,
  competition: 0.20,
  regulatory: 0.15,
  prevalence: 0.10
});
const [siteWeights, setSiteWeights] = useState({
  experience: 0.35,
  pi_strength: 0.20,
  capacity: 0.20,
  compliance: 0.15,
  protocol_match: 0.10
});
```

---

## API CLIENT

```typescript
const screenerApi = {
  // Projects
  async getProjects() {
    const res = await fetch(`${API_URL}/screener/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  async createProject(name: string) {
    const res = await fetch(`${API_URL}/screener/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  },

  async getProject(id: number) {
    const res = await fetch(`${API_URL}/screener/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  // Protocol
  async uploadProtocol(projectId: number, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/upload-protocol`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Failed to upload protocol');
    return res.json();
  },

  async confirmProtocol(projectId: number, criteria: any) {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/confirm-protocol`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ criteria })
    });
    if (!res.ok) throw new Error('Failed to confirm protocol');
    return res.json();
  },

  // Countries
  async getCountries(projectId: number) {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/countries`);
    if (!res.ok) throw new Error('Failed to fetch countries');
    return res.json();
  },

  async refreshCountries(projectId: number, weights: any) {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/countries/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weights })
    });
    if (!res.ok) throw new Error('Failed to refresh countries');
    return res.json();
  },

  // Sites
  async getSitesInCountry(projectId: number, countryCode: string) {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/countries/${countryCode}/sites`);
    if (!res.ok) throw new Error('Failed to fetch sites');
    return res.json();
  },

  async getSiteDetail(projectId: number, siteId: string) {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/sites/${siteId}`);
    if (!res.ok) throw new Error('Failed to fetch site detail');
    return res.json();
  },

  // Shortlist
  async toggleShortlist(projectId: number, siteId: string, action: 'add' | 'remove') {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/shortlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site_id: siteId, action })
    });
    if (!res.ok) throw new Error('Failed to update shortlist');
    return res.json();
  },

  async getShortlist(projectId: number) {
    const res = await fetch(`${API_URL}/screener/projects/${projectId}/shortlist`);
    if (!res.ok) throw new Error('Failed to fetch shortlist');
    return res.json();
  }
};
```

---

## CRITICAL IMPLEMENTATION NOTES

1. ALL text must be high contrast — never use text-gray-300 or text-gray-400 for
   content text. Minimum is text-gray-600 for secondary, text-gray-800 for primary.

2. The country ranking table is the HERO view — spend extra time making it feel
   professional. Sortable columns, clean alignment, clear score visualization.

3. Handle loading states gracefully. ClinicalTrials.gov queries may take 5-15 seconds.
   Show a meaningful loading state with progress messages, not just a spinner.

4. Handle empty states: new project with no protocol, country with no sites found, etc.

5. The "Back" navigation should always work. Breadcrumbs at the top of each view.

6. Error handling: if an API call fails, show a toast/banner with the error message
   and a retry button. Don't crash the app.

7. The page should be self-contained in a single file (page.tsx) following the
   same pattern as the existing frontend/app/page.tsx and frontend/app/sponsor/page.tsx.

8. Add 'use client' directive at top of file since this uses useState/useEffect.

9. Make sure the overall navigation allows switching between Core (/),
   Sponsor (/sponsor), and Screener (/screener) — a simple top nav bar.
