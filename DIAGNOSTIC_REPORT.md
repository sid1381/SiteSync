# 🔍 DIAGNOSTIC INVESTIGATION REPORT
## GPT-4o "Unable to Determine" Analysis

**Date**: October 14, 2025
**Investigation**: Why GPT-4o returns "unable to determine" for 15 questions

---

## ═══════════════════════════════════════════════════════════
## QUESTION 1: PROTOCOL DATA COMPLETENESS ✅
## ═══════════════════════════════════════════════════════════

### Site Summary Being Sent to GPT-4o (1895 characters):

```
============================================================
PROTOCOL REQUIREMENTS (What the study needs)
============================================================
📋 Phase: Phase II
📋 Therapeutic Area: Non-Alcoholic Steatohepatitis (NASH)
📋 Sponsor: ACME Pharmaceuticals, Inc.
📋 Study Duration: 72 weeks (18.0 months)
📋 Enrollment Target: 200 patients
📋 Visit Frequency: Baseline, Week 2, 4, 8, 12, 24, 36, 48, 52, 60, 72
📋 Required Population: Non-Alcoholic Steatohepatitis (NASH) with fibrosis
📋 Required Age Range: 18-75 years
📋 Required Equipment: FibroScan, MRI with PDFF capability, -80°C freezer, Centrifuge
📋 Required Staff: PI (hepatology experience), Nurse (Research nurse for procedures)
📋 Required Procedures: Liver biopsy, MRI-PDFF, FibroScan, Laboratory tests (ALT, AST, GGT, bilirubin)
📋 Drug Administration: oral

============================================================
SITE CAPABILITIES (What the site has)
============================================================
🏥 Site: City Hospital Clinical Research Unit
🏥 Annual Patient Volume: 50,000
🏥 Type 2 Diabetes: 5,000 patients/year
🏥 Obesity (BMI > 30): 8,000 patients/year
🏥 Chronic Hepatitis C: 300 patients/year
🏥 Therapeutic Experience: Gastroenterology (Hepatology), Endocrinology, Cardiology, Oncology, Infectious Disease
🏥 Age Groups Treated: Pediatric (12+), Adult, Geriatric
🏥 Principal Investigator: Dr. Jane Doe (Hepatology, 20 years experience)
🏥 Sub-Investigators: 2 (Endocrinology, Radiology)
🏥 Study Coordinators: 4 (avg N/A years experience)
🏥 Imaging Equipment: CT, DXA, MRI, FibroScan, Ultrasound
🏥 Laboratory: hematology, chemistry, coagulation, PK processing
🏥 Storage: -80°C freezer available
🏥 Procedure Rooms: 2
🏥 Studies Completed (5yr): 45
============================================================

💡 COMPARE the protocol requirements (📋) with site capabilities (🏥) to perform gap analysis.
```

### ✅ VERDICT: Protocol Data is COMPLETE

**All 8 categories present**:
1. ✅ Study Identification (Phase, Sponsor, Therapeutic Area)
2. ✅ Study Timeline (Duration: 72 weeks, Visit Frequency, Enrollment: 200)
3. ✅ Patient Population (NASH with fibrosis, Age: 18-75)
4. ✅ Staff Requirements (PI with hepatology, Research nurse)
5. ✅ Equipment (FibroScan, MRI-PDFF, -80°C freezer, Centrifuge)
6. ✅ Procedures (Liver biopsy, MRI-PDFF, FibroScan, Labs)
7. ✅ Drug/Treatment (oral administration)
8. ✅ Visit Schedule (11 visits over 72 weeks)

**Site data is ALSO complete** with detailed capabilities for gap analysis.

---

## ═══════════════════════════════════════════════════════════
## QUESTION 2: PROMPT QUALITY CHECK ❌ CRITICAL ISSUE FOUND
## ═══════════════════════════════════════════════════════════

### Current Prompt Analysis

**Location**: `ai_question_mapper.py` lines 237-316

**PROBLEM IDENTIFIED**: ❌ **Prompt is TOO CAUTIOUS**

### Evidence of Over-Cautiousness:

**Line 284-285**:
```python
4. If DATA UNCLEAR → Answer with best estimate + low confidence (30-50)
   Example: Protocol unclear on visit schedule → "Unable to determine without protocol visit schedule" (confidence: 35)
```

**❌ THIS IS THE SMOKING GUN!**

The prompt **EXPLICITLY TEACHES GPT-4o TO SAY "Unable to determine"** as an example!

### What the Prompt Says:

✅ **Good parts**:
- "Extract the VALUE from protocol"
- "Perform gap analysis"
- "ALWAYS read BOTH before answering"

❌ **Bad parts**:
- **Rule #4 explicitly gives "Unable to determine" as an EXAMPLE**
- Says "If DATA UNCLEAR" without defining what "unclear" means
- Doesn't encourage inference from available data
- Doesn't tell GPT-4o to make reasonable assumptions

### What's Missing from the Prompt:

1. ❌ No instruction to "make reasonable inferences"
2. ❌ No instruction to "assume standard practice when not specified"
3. ❌ No instruction to "prefer definitive answers over 'unable to determine'"
4. ❌ Example literally shows using "Unable to determine" - **this primes GPT-4o to use that phrase!**

### Confidence Scoring Section:

```
- 85-95: Data clearly stated in protocol/site
- 70-84: Data present but requires inference  ✅ GOOD
- 50-69: Partial data, making educated guess  ✅ GOOD
- 30-49: Very limited data, low confidence estimate
- 0-29: Data missing or question too ambiguous
```

**Problem**: Doesn't say "use 30-49 for reasonable assumptions" - it says "very limited data"
**This makes GPT-4o think**: "If I don't see explicit data, I should say 'unable to determine'"

---

## ═══════════════════════════════════════════════════════════
## QUESTION 3: SPECIFIC FAILED QUESTIONS ❌
## ═══════════════════════════════════════════════════════════

### Questions That Got "Unable to Determine" (50% confidence):

Based on logs, here are examples:

**1. Question 8**: "Are the inclusion/exclusion criteria restrictive?"
   - **GPT-4o Answer**: "Unable to determine"
   - **Reasoning**: "The protocol's inclusion/exclusion criteria are not detailed in the provided data"
   - **Protocol Data Available**: Required population: "NASH with fibrosis", Age: "18-75 years"
   - **Human Assessment**: ✅ A human would say "Moderately restrictive - requires NASH diagnosis with fibrosis, age 18-75"

**2. Question 10**: "Will the inclusion/exclusion criteria present difficulties?"
   - **GPT-4o Answer**: "Unable to determine"
   - **Reasoning**: "The protocol's inclusion/exclusion criteria are not detailed in the provided data"
   - **Protocol Data Available**: Same as above
   - **Human Assessment**: ✅ A human would say "No major difficulties expected for NASH population"

**Pattern Identified**: 🚨 **GPT-4o is being TOO LITERAL**

- It wants to see **explicit inclusion/exclusion criteria list**
- When it doesn't see that, it says "unable to determine"
- **But the protocol DOES have data**: diagnosis (NASH), severity (fibrosis), age range (18-75)
- A human expert would infer from this that criteria are **moderately restrictive** and **typical for NASH studies**

### Other Examples (from filtering logs):

- ~15 questions filtered with "unable to determine" (50% confidence)
- Most likely related to:
  - Inclusion/exclusion criteria details
  - Visit complexity/time requirements
  - Specific hour estimations
  - Budget/cost details

**All of these COULD be answered with reasonable assumptions**, but GPT-4o is saying "I don't see explicit data, so unable to determine"

---

## ═══════════════════════════════════════════════════════════
## QUESTION 4: COMPARISON WITH FIRST RUN ✅
## ═══════════════════════════════════════════════════════════

### What Changed Between Runs?

**Checked**:
1. ✅ Classification logic changes (universal_survey_parser.py)
2. ✅ Filtering logic (ai_question_mapper.py)

**Analysis**:

**First Run** (before fixes):
- 33 objective / 19 subjective
- Some questions incorrectly marked objective
- GPT-4o answered those questions (even if wrong)

**Second Run** (after fixes):
- ~26 objective / 26 subjective (estimated)
- Stricter subjective classification
- **Many questions NOW marked subjective → sent to AI as subjective → AI says "unable to determine"**

**KEY INSIGHT**: 🔍 **The classification fixes are WORKING**, but now GPT-4o is receiving questions with "SUBJECTIVE" category and saying "unable to determine" instead of attempting an answer.

**Example**:
- Question: "Is enrollment realistic?"
- Before: Marked OBJECTIVE → GPT-4o answered "Yes (85%)"
- After: Marked SUBJECTIVE → GPT-4o says "Unable to determine (50%)"

**Problem**: The prompt doesn't tell GPT-4o how to handle SUBJECTIVE questions!

---

## ═══════════════════════════════════════════════════════════
## QUESTION 5: HARD-CODING CHECK ✅ NO BIAS FOUND
## ═══════════════════════════════════════════════════════════

### Search Results for "UAB":

**Files with "UAB" mentions**:
1. `/app/routes/feasibility.py` - Demo/preview endpoint (harmless)
2. `/app/services/universal_survey_parser.py` - Example in documentation comment
3. `/app/services/feasibility_processor.py` - Comment about UAB form
4. `/app/services/smart_question_mapper.py` - Comment about UAB patterns

**VERDICT**: ✅ **No hardcoded UAB-specific logic**

All mentions are:
- Documentation/comments
- Demo endpoints
- Examples in prompts ("Pfizer, Novartis, Merck, UAB, academic institutions...")

### Rule-Based Overrides (universal_survey_parser.py):

**Objective patterns** (lines 1238-1252):
```python
r'what\s+is\s+the\s+(protocol\s+)?phase',  # ✅ GENERAL
r'what\s+is\s+the\s+population\s+age',     # ✅ GENERAL
r'what\s+is\s+the\s+duration',             # ✅ GENERAL
r'what\s+equipment\s+is\s+required',       # ✅ GENERAL
...
```

**Subjective patterns** (lines 1261-1280):
```python
r'is.*realistic',                          # ✅ GENERAL
r'do.*we.*have.*access',                   # ✅ GENERAL
r'will.*budget.*cover',                    # ✅ GENERAL
...
```

**VERDICT**: ✅ **All patterns are GENERAL - no survey-specific bias**

---

## ═══════════════════════════════════════════════════════════
## ROOT CAUSE ANALYSIS 🎯
## ═══════════════════════════════════════════════════════════

### The Core Problem:

**❌ PROMPT INSTRUCTS GPT-4O TO BE TOO CAUTIOUS**

**Evidence**:
1. **Line 284-285 literally shows "Unable to determine" as an example**
2. **No instruction to make reasonable inferences**
3. **No guidance for SUBJECTIVE questions**
4. **Confidence scoring doesn't encourage estimation**

### The Mechanism:

```
User uploads survey with question: "Are inclusion/exclusion criteria restrictive?"
         ↓
Classification: SUBJECTIVE (correctly identified)
         ↓
Sent to GPT-4o with category: "SUBJECTIVE"
         ↓
GPT-4o sees:
  - Question is SUBJECTIVE
  - Prompt says "If DATA UNCLEAR → Unable to determine"
  - Protocol has some data (NASH + fibrosis + age) but not explicit I/E list
  - GPT-4o thinks: "Not explicit enough, better say unable to determine"
         ↓
Result: "Unable to determine (50% confidence)"
         ↓
Filter catches it: "unable to determine" + 50% → FILTERED OUT
         ↓
Final: Question remains blank (no auto-fill)
```

### Why This is Actually GOOD (but needs tweaking):

✅ **Classification is working correctly** - identifying subjective questions
✅ **Filtering is working correctly** - removing useless "unable to determine" answers
❌ **Prompt needs fixing** - should encourage reasonable inference

---

## ═══════════════════════════════════════════════════════════
## CRITICAL HYPOTHESIS CONFIRMED ✅
## ═══════════════════════════════════════════════════════════

**Your Hypothesis**: "The batch mapping prompt is telling GPT-4o to be TOO LITERAL"

**Status**: ✅ **CONFIRMED**

**Evidence**:
1. Line 284-285: **Explicitly gives "Unable to determine" as an example**
2. Says "If DATA UNCLEAR" without defining threshold
3. No instruction to "make reasonable inferences"
4. No instruction to "assume standard clinical practice"
5. Doesn't say "prefer definitive answers over unable to determine"

**Exact Wording Found**:
```python
4. If DATA UNCLEAR → Answer with best estimate + low confidence (30-50)
   Example: Protocol unclear on visit schedule → "Unable to determine without protocol visit schedule" (confidence: 35)
```

**This PRIMES GPT-4o to use the phrase "Unable to determine"!**

---

## ═══════════════════════════════════════════════════════════
## RECOMMENDATIONS 🎯
## ═══════════════════════════════════════════════════════════

### Fix #1: Remove "Unable to determine" example from prompt

**Change line 284-285 from**:
```python
4. If DATA UNCLEAR → Answer with best estimate + low confidence (30-50)
   Example: Protocol unclear on visit schedule → "Unable to determine without protocol visit schedule" (confidence: 35)
```

**To**:
```python
4. If DATA INCOMPLETE → Make reasonable inference based on available data + low-medium confidence (50-70)
   Example: Protocol says "oral dosing" but no details → "Likely simple dosing regimen (oral administration suggests standard BID or QD dosing)" (confidence: 60)
   NEVER say "Unable to determine" - always provide best estimate based on clinical knowledge and available data.
```

### Fix #2: Add explicit "MAKE INFERENCES" instruction

Add after line 252:
```python
=== CRITICAL: INFERENCE OVER UNCERTAINTY ===
When data is incomplete:
✅ DO: Make reasonable clinical inferences based on available data
✅ DO: Use domain knowledge (standard practices, typical protocols)
✅ DO: Provide best estimate with appropriate confidence (50-70%)
❌ DON'T: Say "unable to determine" or "not enough information"
❌ DON'T: Refuse to answer - always provide your best assessment

Example:
- Question: "Is dosing complex?"
- Protocol: "oral administration"
- ❌ Bad: "Unable to determine complexity without dosing schedule"
- ✅ Good: "Likely not complex - oral administration typically indicates simple QD or BID regimen" (confidence: 65%)
```

### Fix #3: Add SUBJECTIVE question handling

Add after line 306:
```python
**HANDLING SUBJECTIVE QUESTIONS**:
Even though these require site judgment, provide DATA-DRIVEN GUIDANCE:
- "Is enrollment realistic?" → Compare target vs site volume + provide assessment
- "Are criteria restrictive?" → Analyze requirements + assess difficulty level
- "Is training necessary?" → Compare protocol complexity vs site experience

Format: "[Assessment] based on [specific data comparison]"
Example: "Moderately restrictive - requires confirmed NASH diagnosis with F2-F3 fibrosis staging, which limits eligible population" (confidence: 70%)
```

### Fix #4: Update confidence scoring guidance

Change lines 296-301 to:
```python
**CONFIDENCE SCORING**:
- 85-95: Data explicitly stated in protocol/site
- 70-84: Data requires inference from available information (USE THIS OFTEN)
- 50-69: Educated guess based on clinical knowledge and partial data (DEFAULT when uncertain)
- 30-49: Very limited data, rough estimate (RARE)
- Below 30: NEVER USE - always possible to provide some assessment

Default to 60-70% confidence for reasonable clinical inferences.
```

---

## ═══════════════════════════════════════════════════════════
## SUMMARY FOR USER
## ═══════════════════════════════════════════════════════════

**DELIVERABLE 1: Site Summary** ✅
- Complete protocol data (1895 chars)
- All 8 categories present
- Sufficient detail for gap analysis

**DELIVERABLE 2: Batch Prompt** ✅
- Located in ai_question_mapper.py:237-316
- **CRITICAL FLAW FOUND**: Line 284-285 teaches GPT-4o to say "Unable to determine"

**DELIVERABLE 3: Failed Questions** ✅
- ~15 questions with "unable to determine" (50%)
- Examples: inclusion/exclusion criteria, visit complexity, hour estimates
- All COULD be answered with reasonable inference

**DELIVERABLE 4: Rule-Based Overrides** ✅
- All patterns are GENERAL (not UAB-specific)
- No hardcoded survey bias

**DELIVERABLE 5: Comparison Analysis** ✅
- Classification changes working correctly
- More questions now marked subjective
- GPT-4o struggling with subjective questions + incomplete data

**ROOT CAUSE**: ❌ **Prompt explicitly teaches "Unable to determine" as example + doesn't encourage inference**

**SOLUTION**: Update prompt to encourage inference, remove "unable to determine" example, add SUBJECTIVE handling guidance
