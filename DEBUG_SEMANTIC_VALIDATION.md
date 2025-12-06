# Debug Semantic Validation - Tracing the Workload Bug

**Issue**: "Is the workload manageable?" returns "18-75 years" instead of Yes/No
**Status**: ⚠️ **DEBUGGING IN PROGRESS** - Comprehensive logging added
**Latest Commit**: cdf5c6d

---

## 🔍 What We Need to Find Out

The semantic validation code LOOKS correct, but the bug persists. We need to determine:

1. ✅ **Is validation being called?** - Need to see logs
2. ❓ **Is the question text correct?** - Could be truncated or modified
3. ❓ **Are keywords detected?** - 'manageable' and 'workload' should match
4. ❓ **Is the answer correct?** - Should be "18-75 years"
5. ❓ **Are age indicators detected?** - 'years' and '18-75' should match
6. ❓ **Why no correction?** - If all above pass, why isn't it corrected?

---

## 📊 Comprehensive Debug Logging Added

### **Location**: `app/services/ai_question_mapper.py`

### **1. Before Validation Call** (lines 581-585)
```python
logger.info("=" * 80)
logger.info(f"⚙️  CALLING VALIDATION for question: {q_text[:80]}")
logger.info(f"   Answer before validation: '{answer}'")
logger.info(f"   Confidence before validation: {confidence}")
logger.info("=" * 80)
```

**Purpose**: Confirm validation is being invoked for the question

---

### **2. Start of Validation** (lines 664-674)
```python
logger.info("=" * 80)
logger.info(f"🔍 VALIDATING QUESTION")
logger.info(f"   Question (full): '{question_text}'")
logger.info(f"   Answer (full): '{answer}'")
logger.info(f"   Confidence: {confidence}")

q_lower = question_text.lower()
answer_lower = answer.lower() if isinstance(answer, str) else str(answer).lower()

logger.info(f"   Question (lowercase): '{q_lower}'")
logger.info(f"   Answer (lowercase): '{answer_lower}'")
```

**Purpose**: See exact question and answer text, verify lowercase conversion

---

### **3. Feasibility Keyword Checking** (lines 684-690)
```python
feasibility_keywords = ['manageable', 'feasible', 'realistic', 'adequate', 'sufficient', 'enough', 'workload']

logger.info(f"🔎 CHECKING FEASIBILITY KEYWORDS:")
for keyword in feasibility_keywords:
    is_present = keyword in q_lower
    logger.info(f"   '{keyword}' in question? {is_present}")

matched_keywords = [k for k in feasibility_keywords if k in q_lower]
logger.info(f"   Total matched: {len(matched_keywords)}")
```

**Purpose**: Verify which keywords are detected in the question

---

### **4. Age Mismatch Indicator Checking** (lines 707-714)
```python
age_mismatch_indicators = ['years', 'age', '18-75', '18-65', 'age range', 'yrs']

logger.info(f"🔎 CHECKING AGE MISMATCH INDICATORS:")
for indicator in age_mismatch_indicators:
    is_present = indicator in answer_lower
    logger.info(f"   '{indicator}' in answer? {is_present}")

matched_indicators = [ind for ind in age_mismatch_indicators if ind in answer_lower]
logger.info(f"   Total age indicators matched: {len(matched_indicators)}")
logger.info(f"   Matched indicators: {matched_indicators}")
```

**Purpose**: Verify age indicators are detected in the answer

---

### **5. Mismatch Detection** (lines 716-721)
```python
if matched_indicators:
    logger.warning(f"❌ SEMANTIC MISMATCH DETECTED!")
    logger.warning(f"   Age indicators in answer: {matched_indicators}")
    logger.warning(f"   CORRECTING: '{answer}' → 'Yes - based on site resources and staffing'")
    logger.warning("=" * 80)
    return ("Yes - based on site resources and staffing", 75, "SEMANTIC MISMATCH: Workload question answered with age data - corrected")
```

**Purpose**: Confirm mismatch is detected and correction is returned

---

### **6. Default Case** (lines 830-833)
```python
logger.info(f"✅ DEFAULT: No pattern matched, accepting answer as-is")
logger.info(f"   Returning: ({answer}, {confidence}, 'Passed validation')")
logger.info("=" * 80)
return (answer, confidence, "Passed validation")
```

**Purpose**: See when validation falls through to default (no pattern matched)

---

## 🎯 Expected Log Output if Bug is Present

If the bug exists and validation IS working, we should see:

```
================================================================================
⚙️  CALLING VALIDATION for question: Is the workload manageable?
   Answer before validation: '18-75 years'
   Confidence before validation: 85
================================================================================

================================================================================
🔍 VALIDATING QUESTION
   Question (full): 'Is the workload manageable?'
   Answer (full): '18-75 years'
   Confidence: 85
   Question (lowercase): 'is the workload manageable?'
   Answer (lowercase): '18-75 years'

🔎 CHECKING FEASIBILITY KEYWORDS:
   'manageable' in question? True
   'feasible' in question? False
   'realistic' in question? False
   'adequate' in question? False
   'sufficient' in question? False
   'enough' in question? False
   'workload' in question? True
   Total matched: 2

================================================================================
🎯 FEASIBILITY PATTERN DETECTED: Is the workload manageable?
   Keywords matched: ['manageable', 'workload']
   Original answer: '18-75 years'

🔎 CHECKING AGE MISMATCH INDICATORS:
   'years' in answer? True
   'age' in answer? False
   '18-75' in answer? True
   '18-65' in answer? False
   'age range' in answer? False
   'yrs' in answer? False
   Total age indicators matched: 2
   Matched indicators: ['years', '18-75']

❌ SEMANTIC MISMATCH DETECTED!
   Age indicators in answer: ['years', '18-75']
   CORRECTING: '18-75 years' → 'Yes - based on site resources and staffing'
================================================================================

🔧 VALIDATION CORRECTION for: Is the workload manageable?
   Original answer: '18-75 years' (confidence: 85)
   Corrected answer: 'Yes - based on site resources and staffing' (confidence: 75)
   Reason: SEMANTIC MISMATCH: Workload question answered with age data - corrected
================================================================================
```

---

## 🚨 Possible Failure Scenarios

### **Scenario 1: Validation Not Called at All**
**Symptoms**:
- No logs starting with "⚙️  CALLING VALIDATION"
- No logs starting with "🔍 VALIDATING QUESTION"

**Cause**: Question not in batch AI response OR exception thrown

**Fix**: Check batch AI response parsing, ensure all questions included

---

### **Scenario 2: Question Text Modified**
**Symptoms**:
- Log shows: `Question (full): 'Is the workload...'` (truncated)
- OR: `Question (full): 'manageable workload'` (reworded)

**Cause**: Question text modified before validation

**Fix**: Trace where question text is modified

---

### **Scenario 3: Keywords Not Detected**
**Symptoms**:
- `'manageable' in question? False`
- `'workload' in question? False`

**Cause**:
- Question text doesn't contain these words
- OR case sensitivity issue (should be lowercased)

**Fix**: Verify question text and lowercase conversion

---

### **Scenario 4: Age Indicators Not Detected**
**Symptoms**:
- All age indicators show `False`
- `Total age indicators matched: 0`

**Cause**:
- Answer is not "18-75 years" (different format)
- OR case sensitivity issue

**Fix**: Check actual answer format

---

### **Scenario 5: Correction Not Applied**
**Symptoms**:
- Mismatch detected: "❌ SEMANTIC MISMATCH DETECTED!"
- But final response still shows "18-75 years"

**Cause**:
- Validated answer not being used (line 618)
- OR answer overwritten after validation

**Fix**: Check lines 618-622 where validated answer is assigned

---

## 📝 Next Steps

### **1. Run Survey with Workload Question**
Upload a survey with "Is the workload manageable?" and check backend logs.

### **2. Search Logs for Keywords**
```bash
# In Docker container
docker logs sitesync_backend 2>&1 | grep "CALLING VALIDATION"
docker logs sitesync_backend 2>&1 | grep "VALIDATING QUESTION"
docker logs sitesync_backend 2>&1 | grep "FEASIBILITY PATTERN"
docker logs sitesync_backend 2>&1 | grep "SEMANTIC MISMATCH"
```

### **3. Analyze Log Output**
Compare actual logs to expected output above to identify failure point.

### **4. Fix Root Cause**
Based on which scenario matches the logs, apply appropriate fix.

---

## 🔧 How to Test

### **Method 1: Docker Logs (Real-time)**
```bash
# Start containers
docker-compose up

# In another terminal, tail logs
docker logs -f sitesync_backend | grep -E "(VALIDATING|FEASIBILITY|SEMANTIC)"

# Upload survey with "Is the workload manageable?"
# Watch logs for validation output
```

### **Method 2: Backend Logs (File)**
```bash
# After processing survey
docker exec sitesync_backend cat /var/log/backend.log | grep "workload"
```

### **Method 3: Database Check**
```sql
-- After survey processing
SELECT
    question_text,
    response_value,
    confidence_score,
    response_source
FROM survey_responses
WHERE question_text LIKE '%workload%'
   OR question_text LIKE '%manageable%';
```

Should show:
- `response_value`: "Yes - based on site resources and staffing"
- NOT: "18-75 years"

---

## ✅ Success Criteria

Validation is working if logs show:
1. ✅ "⚙️  CALLING VALIDATION" for workload question
2. ✅ "🎯 FEASIBILITY PATTERN DETECTED"
3. ✅ Keywords matched: `['manageable', 'workload']`
4. ✅ Age indicators matched: `['years', '18-75']`
5. ✅ "❌ SEMANTIC MISMATCH DETECTED!"
6. ✅ "🔧 VALIDATION CORRECTION" applied
7. ✅ Final answer: "Yes - based on site resources and staffing"

---

**Status**: Ready for testing
**Next Action**: Run survey processing and collect logs
**Expected Result**: Logs will reveal exactly why validation isn't working

---

**Last Updated**: December 6, 2025
**Commit**: cdf5c6d - Add comprehensive debug logging to trace semantic validation bug
