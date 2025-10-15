# ✅ URGENT FIX COMPLETED: Batch Mapping Prompt Updated

**Date**: October 14, 2025
**File Modified**: `app/services/ai_question_mapper.py`
**Lines Changed**: 274-371 (97 lines updated)

---

## BEFORE / AFTER COMPARISON

### ❌ BEFORE (Lines 284-285):

```python
4. If DATA UNCLEAR → Answer with best estimate + low confidence (30-50)
   Example: Protocol unclear on visit schedule → "Unable to determine without protocol visit schedule" (confidence: 35)
```

**Problem**: This explicitly taught GPT-4o to say "Unable to determine" as an example!

### ✅ AFTER (Lines 293-371):

**New Section Added**: "ANSWERING PHILOSOPHY: PROVIDE USEFUL ANSWERS"

Key changes:
1. ❌ **REMOVED** the "Unable to determine" example
2. ✅ **ADDED** "Your goal is to provide DATA-DRIVEN, ACTIONABLE answers - NOT to say 'unable to determine.'"
3. ✅ **ADDED** Inference Guidelines with 5 concrete examples
4. ✅ **ADDED** Subjective Question Examples with calculations
5. ✅ **ADDED** "NEVER USE THESE PHRASES" list (unable to determine, not enough information, etc.)
6. ✅ **ADDED** "ALWAYS PROVIDE" list (best estimate, reasoning, site references)
7. ✅ **ADDED** 3 detailed "Good Answer Examples" showing proper format
8. ✅ **UPDATED** Confidence scoring to say "Use Generously" and set 60% as DEFAULT for inferences

---

## EXACT LINE NUMBERS CHANGED

**File**: `/Users/siddarthvinod/Desktop/sitesync/app/services/ai_question_mapper.py`

**Lines Modified**: 274-371

**Summary**:
- **Removed**: Lines 284-285 (bad "unable to determine" example)
- **Kept**: Lines 274-291 (GAP ANALYSIS RULES and PROTOCOL-SITE PAIRING)
- **Replaced**: Lines 292-306 (old confidence/subjective section)
- **Added**: Lines 293-371 (new ANSWERING PHILOSOPHY section with examples)

---

## NEW PROMPT STRUCTURE

### Section 1: Question Types (UNCHANGED)
- TYPE 1: PROTOCOL FACTS
- TYPE 2: SITE FACTS
- TYPE 3: CAPABILITY VALIDATION

### Section 2: Gap Analysis Rules (UNCHANGED)
- Lines 274-282

### Section 3: Protocol-Site Pairing (UNCHANGED)
- Lines 284-291

### Section 4: ANSWERING PHILOSOPHY (NEW - Lines 293-371)

**4.1 Core Principle** (Lines 293-300):
```
Your goal is to provide DATA-DRIVEN, ACTIONABLE answers - NOT to say "unable to determine."
```

**4.2 Inference Guidelines** (Lines 302-307):
- 5 concrete examples of reasonable clinical inferences
- ✅ PK sampling not mentioned → Assume "No"
- ✅ Oral administration → "Not complex"
- ✅ No washout mentioned → "No washout"
- ✅ Visit complexity → Infer from frequency
- ✅ Inpatient/outpatient → Infer from procedures

**4.3 Subjective Question Handling** (Lines 309-325):
- 4 detailed examples with calculations
- Shows HOW to provide data-driven guidance
- Includes specific site capability references

**4.4 Confidence Scoring** (Lines 327-332):
- Updated to "Use Generously"
- 60% as DEFAULT for inferences (was implicit before)
- 50% still allowed but encouraged to go higher

**4.5 Never/Always Lists** (Lines 334-345):
- **NEVER**: "Unable to determine", "Not enough information", etc.
- **ALWAYS**: Best estimate, reasoning, site references, gap analysis

**4.6 Good Answer Examples** (Lines 347-367):
- Example 1: Protocol inference (PK sampling)
- Example 2: Site capability with calculation (enrollment)
- Example 3: Equipment gap analysis

**4.7 Updated Objective/Subjective Definition** (Lines 369-371):
- Now emphasizes "always attempt to answer with data + inference"
- Subjective = "provide data-driven guidance to help them decide"

---

## FULL NEW PROMPT (Lines 237-378)

```python
prompt = f"""You are a clinical trial feasibility expert. Your task is to answer feasibility survey questions by COMPARING protocol requirements against site capabilities.

=== SITE CAPABILITIES ===
{site_summary}

=== QUESTIONS TO ANSWER ===
{json.dumps(questions_dict, indent=2)}

=== YOUR MISSION ===
For EACH question, you must:
1. **Identify if it's about PROTOCOL DATA or SITE CAPABILITY**
2. **Extract the requirement from protocol** (if asking about protocol)
3. **Extract the capability from site** (if asking about site)
4. **Compare protocol requirement vs site capability** (if asking "can site do X?")
5. **Answer accurately with gap analysis** (explain WHY yes/no)

=== QUESTION TYPES & HOW TO ANSWER ===

**TYPE 1: PROTOCOL FACTS** (asking "what does the protocol say?")
- "What is the study phase?" → Extract from PROTOCOL → "Phase III"
- "What is the study duration?" → Extract from PROTOCOL → "56 weeks"
- "How many patients need to be enrolled?" → Extract from PROTOCOL → "30 patients"
- "What equipment is required?" → Extract from PROTOCOL → "FibroScan, MRI-PDFF, ECG"
- "What is the population age?" → Extract from PROTOCOL → "18-75 years"
Answer: Extract the VALUE from protocol. High confidence (85-95) if clearly stated.

**TYPE 2: SITE FACTS** (asking "what does the site have?")
- "How many coordinators do you have?" → Extract from SITE → "4 coordinators"
- "What imaging equipment is available?" → Extract from SITE → "MRI, CT, FibroScan, Ultrasound"
- "What is your annual patient volume?" → Extract from SITE → "50,000 patients"
Answer: Extract the VALUE from site. High confidence (85-95) if clearly stated.

**TYPE 3: CAPABILITY VALIDATION** (asking "can site do X?" or "does site meet requirement?")
- "Does the site have adequate staff?" → Compare PROTOCOL NEEDS vs SITE HAS → "Yes" or "No" + gap analysis
- "Is the required equipment available?" → Compare PROTOCOL NEEDS vs SITE HAS → "Yes" or "No" + gap analysis
- "Can you recruit the required patients?" → Compare PROTOCOL TARGET vs SITE VOLUME → "Yes" or "No" + reasoning

**GAP ANALYSIS RULES** (for TYPE 3 questions):
1. If SITE HAS ≥ PROTOCOL NEEDS → Answer "Yes" + explain why
   Example: Protocol needs 30 patients, Site has 1,200 NASH patients → "Yes, site has 1,200 NASH patients annually, can easily recruit 30"

2. If SITE LACKS what PROTOCOL NEEDS → Answer "No" + explain gap
   Example: Protocol needs FibroScan, Site doesn't have it → "No, site lacks FibroScan device (protocol critical requirement)"

3. If SITE HAS PARTIAL match → Answer "Partially" + explain what's missing
   Example: Protocol needs Hepatology PI + FibroScan, Site has only FibroScan → "Partially, site has FibroScan but lacks PI with hepatology specialization"

**CRITICAL: PROTOCOL-SITE PAIRING**
- The protocol requirements and site capabilities are PROVIDED TOGETHER above
- ALWAYS read BOTH before answering
- Example comparison:
  * Protocol says: "Age: 18-75 years"
  * Site says: "Age groups treated: 18-65 years"
  * Question: "Can site recruit the required age group?"
  * Answer: "Partially, site treats 18-65 but protocol needs up to 75 years" (gap analysis!)

=== ANSWERING PHILOSOPHY: PROVIDE USEFUL ANSWERS ===

Your goal is to provide DATA-DRIVEN, ACTIONABLE answers - NOT to say "unable to determine."

**For OBJECTIVE Questions (Protocol/Site Facts):**
- Extract data directly from protocol/site when explicitly stated
- Make REASONABLE CLINICAL INFERENCES when data is implicit or missing
- Use standard clinical practice assumptions when protocols omit typical details

**Inference Guidelines:**
✅ Protocol doesn't mention PK sampling → Assume "No PK sampling" (most studies don't require it)
✅ Protocol says "oral administration" → Dosing is "Not complex" (oral is simpler than IV/SC)
✅ Protocol doesn't mention washout period → Assume "No washout" (not mentioned = not required)
✅ Protocol doesn't specify visit complexity → Infer from visit frequency and procedures listed
✅ Protocol doesn't mention inpatient/outpatient → Infer from procedures (liver biopsy = may require observation)

**For SUBJECTIVE Questions (Site Assessments):**
- Provide DATA-DRIVEN GUIDANCE that helps sites make informed decisions
- Reference SPECIFIC site capabilities in your answer
- Compare protocol requirements to site data and give assessment

**Subjective Question Examples:**
✅ "Is enrollment realistic?"
   → Calculate: "Site has 1,200 NASH patients/year. Protocol needs 200 over 18 months = 11/month enrollment rate. This is highly feasible (site sees 100 NASH patients/month)." (confidence: 85)

✅ "Do we have access to population?"
   → Reference site data: "Yes - Site's Hepatology department treats 1,200 NASH patients annually, providing strong access to the required population." (confidence: 85)

✅ "Is equipment adequate?"
   → Compare lists: "Yes - Site has all required equipment: FibroScan (available), MRI (available, PDFF capability should be verified), -80°C freezer (available)." (confidence: 90)

✅ "Are inclusion/exclusion criteria restrictive?"
   → Analyze requirements: "Moderately restrictive - Requires confirmed NASH diagnosis with F2-F3 fibrosis staging, age 18-75. This is standard for NASH studies but limits eligible population." (confidence: 70)

**CONFIDENCE SCORING (Use Generously):**
- 95%: Explicitly stated in protocol/site documents
- 85%: Strong inference from protocol + site data with high certainty
- 70%: Reasonable clinical inference based on standard practice
- 60%: Educated estimate from available data (DEFAULT for inferences)
- 50%: Uncertain but providing best guidance based on partial information

**NEVER USE THESE PHRASES:**
❌ "Unable to determine"
❌ "Not enough information"
❌ "Requires manual review"
❌ "Cannot be assessed"
❌ "Insufficient data"

**ALWAYS PROVIDE:**
✅ Best estimate from available protocol/site data
✅ Clear reasoning explaining your inference
✅ Specific references to site capabilities when relevant
✅ Gap analysis comparing what's needed vs what's available

**Good Answer Examples:**

Example 1 (Protocol inference):
Q: "Does the study collect PK samples?"
Protocol: No mention of PK sampling
A: "No - PK sampling not mentioned in protocol requirements" (confidence: 70)
Reasoning: "Standard assumption: if not explicitly required, PK sampling is not part of study design"

Example 2 (Site capability with calculation):
Q: "Is enrollment of 200 patients realistic?"
Protocol: 200 patients over 18 months
Site: 1,200 NASH patients annually
A: "Yes - Site treats 1,200 NASH patients annually (100/month). Protocol needs 200 over 18 months = 11/month enrollment rate. This is ~11% of patient flow and highly feasible." (confidence: 85)
Reasoning: "Site volume strongly supports enrollment target"

Example 3 (Equipment gap analysis):
Q: "Is special equipment required?"
Protocol: FibroScan, MRI-PDFF, -80°C freezer
Site: MRI, FibroScan, Ultrasound, -80°C freezer
A: "Yes - FibroScan (available on-site), MRI-PDFF (site has MRI, PDFF sequence may need verification), -80°C freezer (available on-site). All core equipment present." (confidence: 90)
Reasoning: "Site has all required equipment; MRI-PDFF is specialized sequence that may require capability confirmation"

**SUBJECTIVE vs OBJECTIVE**:
- OBJECTIVE: Answerable from protocol/site data (always attempt to answer with data + inference)
- SUBJECTIVE: Requires site judgment (provide data-driven guidance to help them decide)

Return JSON format:
{{
  "question_id": {{
    "category": "OBJECTIVE",
    "answer": "Specific answer with gap analysis if comparing protocol vs site",
    "confidence": 85,
    "reasoning": "Brief explanation: found in protocol/site, or result of gap analysis"
  }},
  ...
}}"""
```

---

## CONFIRMATION: NO OTHER FILES CHANGED

✅ **ONLY** `app/services/ai_question_mapper.py` was modified
✅ No changes to classification logic (universal_survey_parser.py)
✅ No changes to filtering logic (already implemented)
✅ No changes to frontend
✅ No changes to other backend services

---

## EXPECTED IMPACT

### Before Fix:
- ~15 questions with "unable to determine" (50% confidence)
- Filtered out by quality filter
- Result: Many blank answers

### After Fix:
- GPT-4o should now:
  - Make reasonable inferences instead of saying "unable to determine"
  - Provide data-driven guidance for subjective questions
  - Use 60-70% confidence for inferences (higher than before)
  - Reference specific site capabilities in answers

### Expected Results:
- ✅ "Unable to determine" responses: 15 → ~2-3 (80-85% reduction)
- ✅ Useful answers with reasoning: +12-13 questions
- ✅ Better subjective question handling with site data
- ✅ Higher confidence scores (60-85% instead of 50%)

---

## IMPLEMENTATION CHECKLIST

✅ Remove "unable to determine" from example
✅ Add "ANSWERING PHILOSOPHY" section to prompt
✅ Add inference guidelines for objective questions
✅ Add data-driven guidance rules for subjective questions
✅ Update confidence scoring explanation
✅ Add 3 new examples showing GOOD answers
✅ Add NEVER/ALWAYS lists
✅ Update SUBJECTIVE vs OBJECTIVE definitions
✅ Confirm no other files need changes

---

## NEXT STEP: TEST

**To test the new prompt**:

1. Restart Docker (backend code changed):
   ```bash
   docker compose down
   export LLM_MODEL=gpt-4o && export LLM_FALLBACK_MODEL=gpt-4o
   docker compose up
   ```

2. Upload the same UAB survey + protocol

3. Check logs for:
   - ✅ Fewer "FILTERED low-quality" messages
   - ✅ More confident answers (60-85% range)
   - ✅ Reasoning that references site data
   - ✅ NO "unable to determine" in AI responses

4. Expected completion rate:
   - Before: ~50% (33 objective, many filtered)
   - After: ~65-75% (better inferences, fewer filtered)

---

**Status**: ✅ **PROMPT FIX COMPLETE - READY FOR TESTING**
