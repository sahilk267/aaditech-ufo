# 🚀 QUICK CHEAT SHEET - IMPLEMENTATION FILES

**Print this or keep it open while coding!**

---

## 📖 THE 6 FILES YOU'LL USE MOST

```
┌─────────────────────────────────────────────────────────────┐
│ FILE                          │ USE              │ UPDATE    │
├─────────────────────────────────────────────────────────────┤
│ WEEK_BY_WEEK_CHECKLIST.md     │ Daily tasks      │ Weekly    │
│ PROGRESS_TRACKER.md           │ Track progress   │ 2-3x/day  │
│ UPDATED_ARCHITECTURE.md       │ System design    │ Rarely    │
│ README.md                     │ Specifications   │ Rarely    │
│ FEATURE_COVERAGE_MAP.md       │ Feature status   │ Weekly    │
│ MASTER_ROADMAP.md             │ Timeline         │ Weekly    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 WORKFLOW (Start Here!)

### MORNING (5 min)
```
1. Open IMPLEMENTATION_REFERENCE_GUIDE.md
2. Open WEEK_BY_WEEK_CHECKLIST.md → Find today's section
3. Open PROGRESS_TRACKER.md (in second window)

Ready to code! ✅
```

### DURING CODING (Repeat 3-4x per day)
```
Task 1: Create .env file
  ├─ Read:   WEEK_BY_WEEK_CHECKLIST.md (instructions)
  ├─ Refer:  README.md (feature details if needed)
  ├─ Review: UPDATED_ARCHITECTURE.md (if API needed)
  ├─ Code:   Edit .env file
  ├─ Test:   Follow testing steps from WEEK_BY_WEEK_CHECKLIST
  ├─ Update: PROGRESS_TRACKER.md (mark function done) ✅
  ├─ Commit: git commit [reference PROGRESS_TRACKER.md]
  └─ (Continue to Task 2...)
```

### WEEKLY (Friday/Sunday) 
```
1. Review:  PROGRESS_TRACKER.md (week total)
2. Update:  FEATURE_COVERAGE_MAP.md (weekly status)
3. Read:    Next week's WEEK_BY_WEEK_CHECKLIST.md
4. Check:   MASTER_ROADMAP.md (dependencies)
5. Plan:    What dependencies for next week?
```

---

## 🗾 DECISION FLOW

```
QUESTION                          → ANSWER IN FILE
────────────────────────────────────────────────────────
"What's my task today?"           → WEEK_BY_WEEK_CHECKLIST.md
"Am I done with Phase 0?"         → PROGRESS_TRACKER.md
"How should I design this?"       → UPDATED_ARCHITECTURE.md
"What should this feature do?"    → README.md
"Is feature X implemented?"       → FEATURE_COVERAGE_MAP.md
"When should feature X start?"    → MASTER_ROADMAP.md
"How do I set up the project?"    → IMPLEMENTATION_REFERENCE_GUIDE.md
```

---

## ✅ AFTER EACH TASK - UPDATE THESE

### Task Completed? Do this (2 min):

```
1️⃣ PROGRESS_TRACKER.md
   Find: Phase 0 > Feature 1 > Security Hardening
   Action: [x] Mark function checkbox
   Update: Progress counter (e.g., "3/20 tasks")

2️⃣ Git Commit
   Format: FEATURE: Brief description
   Body: Reference PROGRESS_TRACKER.md Phase 0 Feature 1
         Progress: 3/45 Phase 0 functions (6%)

3️⃣ FEATURE_COVERAGE_MAP.md (OPTIONAL - do weekly)
   Find: Feature you're working on
   Update: Status from ❌ NOT STARTED to 🟡 PARTIAL/✅ DONE
```

---

## 📁 CODE FILES TO MODIFY/CREATE

### Existing Files (Modify)
```
server/app.py              ← Main Flask app (add routes, security)
agent/agent.py             ← Windows monitoring (add collectors)
server/models.py           ← Database (add tables)
server/forms.py            ← Validation (add validators)
server/config.py           ← Config (add settings)
server/backup.py           ← Backup logic (refactor)
```

### New Files to Create
```
WEEK 1:
  └─ server/auth.py              (API key authentication)
  └─ server/schemas.py           (Input validation)

WEEK 3:
  └─ server/extensions.py        (Flask DB, Redis)
  └─ server/blueprints/
      ├─ __init__.py
      ├─ web.py                  (Web routes)
      └─ api.py                  (API routes)
  └─ server/services/
      ├─ __init__.py
      ├─ system_service.py       (System logic)
      └─ backup_service.py       (Backup logic)

WEEK 4:
  └─ migrations/                 (Database migrations)
  └─ server/tests/
      ├─ test_api.py
      ├─ test_auth.py
      └─ test_services.py

WEEK 9+:
  └─ server/services/
      ├─ alert_service.py        (Week 9: Alerts)
      ├─ automation_service.py    (Week 11: Automation)
      └─ windows_service.py       (Week 13: Windows monitoring)
```

---

## 🔄 GIT COMMIT FORMAT

### Every commit must reference PROGRESS_TRACKER.md:

```
Command:
git commit -m "FEATURE: Brief description

- Specific change 1
- Specific change 2

References: PROGRESS_TRACKER.md Phase 0 Feature X
Functions completed: function_name_1, function_name_2
Progress: N/total functions (%)%"
```

### Example:
```
git commit -m "SECURITY: Move secrets to .env

- Create .env with SECRET_KEY, AGENT_API_KEY
- Create .env.example template
- Update app.py to load from environment
- Update .gitignore

References: PROGRESS_TRACKER.md Phase 0 Feature 1: Security
Functions completed: env_config_setup, env_example_create
Progress: 2/45 Phase 0 functions (4%)"
```

---

## 📊 DAILY STANDUP TEMPLATE

Every morning/after work, update PROGRESS_TRACKER.md:

```markdown
## 📅 Week 1 - Day 1

### ✅ COMPLETED
- [x] Created .env file with secrets
- [x] Created .env.example template

### 🔴 BLOCKERS
- None

### 📋 IN PROGRESS
- Implementing API key authentication

### 🔜 NEXT STEPS
- Test API key protection (tomorrow)
- Add error handling
- Document in README

### PROGRESS
Phase 0 Functions: 2/45 (4%)
```

---

## 🎯 GOLDEN RULES

```
1. Read:   WEEK_BY_WEEK_CHECKLIST.md (daily tasks)
2. Code:   Implement in Python files
3. Update: PROGRESS_TRACKER.md (immediately after)
4. Commit: Reference PROGRESS_TRACKER.md (always)
5. Report: FEATURE_COVERAGE_MAP.md (weekly)

If any question:
→ Check IMPLEMENTATION_REFERENCE_GUIDE.md first!
```

---

## ⚡ SUPER QUICK (1-Page Summary)

```
┌─ START
│
├─ IMPLEMENT: Read WEEK_BY_WEEK_CHECKLIST.md
├─ CODE:      Edit Python files
├─ UPDATE:    Mark done in PROGRESS_TRACKER.md
├─ COMMIT:    Reference PROGRESS_TRACKER.md
├─ VERIFY:    Update FEATURE_COVERAGE_MAP.md (weekly)
│
└─ PROGRESS TRACKED! ✅
```

---

**Print this page or bookmark it! 🔖**

**For details → Read: IMPLEMENTATION_REFERENCE_GUIDE.md**

---

*Last Updated: March 16, 2026*  
*Commit: 219de61*  
*Files: WEEK_BY_WEEK_CHECKLIST.md, PROGRESS_TRACKER.md, UPDATED_ARCHITECTURE.md, README.md, FEATURE_COVERAGE_MAP.md, MASTER_ROADMAP.md*  
