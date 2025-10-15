# 🧪 Testing Instructions for Truncation Debugging

**Date**: October 14, 2025
**Purpose**: Find where question text is being truncated

---

## ✅ Step 1: Restart Docker with Updated Code

The code now has debugging logs to track question text length at each stage.

```bash
docker compose down
export LLM_MODEL=gpt-4o && export LLM_FALLBACK_MODEL=gpt-4o
docker compose up
```

---

## ✅ Step 2: Upload the Same Survey

1. Go to http://localhost:3000
2. Upload the UAB survey PDF
3. Upload the protocol PDF
4. Wait for processing to complete

---

## ✅ Step 3: Check Logs for Truncation Patterns

```bash
docker logs sitesync_backend 2>&1 | grep "📏"
```

**Look for these log lines:**
```
📏 EXTRACTED LENGTH: 95 chars: Will coordination with other departments/services be required?
📏 AFTER CLEANING LENGTH: 62 chars: Will coordination with other departments/services be require
📏 CATEGORIZATION LENGTH: 62 chars
```

**This will tell us:**
1. **EXTRACTED LENGTH**: Length right after AI extraction (is AI returning full text?)
2. **AFTER CLEANING LENGTH**: Length after `_clean_question_text()` (is cleaning truncating?)
3. **CATEGORIZATION LENGTH**: Length when categorization happens (final length)

---

## ✅ Step 4: Share the Results

**Copy and paste this output:**

```bash
docker logs sitesync_backend 2>&1 | grep -E "(📏|🔍 Categorizing)" | head -100
```

**Look for questions that show decreasing lengths:**
- If EXTRACTED LENGTH is short → AI truncated it
- If AFTER CLEANING LENGTH is shorter → cleaning function truncated it
- If CATEGORIZATION LENGTH is shorter → something between processing and categorization

---

## 📊 Expected Patterns

### Pattern 1: AI Truncation
```
📏 EXTRACTED LENGTH: 62 chars: Will coordination with other departments/services be require
📏 AFTER CLEANING LENGTH: 62 chars: Will coordination with other departments/services be require
```
**Diagnosis**: GPT-4o is returning truncated text. Need to check `max_tokens` in AI extraction.

### Pattern 2: Cleaning Truncation
```
📏 EXTRACTED LENGTH: 95 chars: Will coordination with other departments/services be required?
📏 AFTER CLEANING LENGTH: 62 chars: Will coordination with other departments/services be require
```
**Diagnosis**: `_clean_question_text()` function is truncating. Need to check that function.

### Pattern 3: No Truncation (length consistent)
```
📏 EXTRACTED LENGTH: 95 chars: Will coordination with other departments/services be required?
📏 AFTER CLEANING LENGTH: 95 chars: Will coordination with other departments/services be required?
📏 CATEGORIZATION LENGTH: 95 chars
```
**Diagnosis**: No truncation in backend. Problem must be in frontend display or database storage.

---

## 🎯 What to Share

Please share:
1. **The grep output** showing all 📏 log lines
2. **Examples of truncated questions** with their lengths at each stage
3. **Any patterns you notice** (e.g., all questions truncated at 75 chars?)

This will immediately tell us where to fix the truncation!

---

## Next Steps After Diagnosis

Once we know where truncation happens:

- **If AI truncation**: Increase `max_tokens` in `_ai_extract_questions()`
- **If cleaning truncation**: Fix `_clean_question_text()` function
- **If database truncation**: Create migration to increase VARCHAR length
- **If frontend truncation**: Fix display component

---

**Status**: ✅ **Logging Added - Ready for Testing**
