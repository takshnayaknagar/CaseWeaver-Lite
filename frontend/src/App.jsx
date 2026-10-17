import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence, MotionConfig } from 'motion/react';
import {
  Scale,
  Sun,
  Moon,
  Menu,
  X,
  LayoutDashboard,
  FileText,
  Users,
  GitCompare,
  Clock,
  Sparkles,
  RotateCcw,
  Search,
  PlusCircle,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Calendar,
  User,
  Quote,
  ShieldCheck,
  ArrowRight,
  ChevronRight,
  Filter,
} from 'lucide-react';
import {
  getCase,
  getHealth,
  addStatement,
  resetCase,
  analyzeAll,
} from './api';
import './App.css';

// Motion transition presets for consistent, subtle animations
const fadeInVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] },
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: 0.16, ease: [0.16, 1, 0.3, 1] },
  },
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.03,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.22, ease: [0.16, 1, 0.3, 1] },
  },
};

// Genuine scroll-reveal for long lists — items fade in once as they enter the viewport
const revealViewport = { once: true, margin: '-60px' };
const revealVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] },
  },
};

// Defensive field lookup for timeline events — renders only fields the backend actually provides,
// falling back to alternate spellings without inventing data
const pickField = (obj, keys) => {
  for (const key of keys) {
    if (obj && obj[key] !== undefined && obj[key] !== null && obj[key] !== '') return obj[key];
  }
  return null;
};

export default function App() {
  // Theme state: dark / light
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('cw_theme') || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('cw_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const goTab = (tab) => {
    setActiveTab(tab);
    setNavOpen(false); // closes the mobile menu; no-op on desktop
  };

  // Navigation
  const [activeTab, setActiveTab] = useState('overview');
  // Collapsible nav at all widths: open by default on desktop, collapsed on mobile
  const [navOpen, setNavOpen] = useState(() => window.matchMedia('(min-width: 961px)').matches);

  // Case & backend data
  const [caseData, setCaseData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [analysisResults, setAnalysisResults] = useState(null);

  // Loading & error states
  const [loadingCase, setLoadingCase] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Add statement form state
  const [witnessName, setWitnessName] = useState('');
  const [statementId, setStatementId] = useState('');
  const [statementText, setStatementText] = useState('');
  const [witnessRole, setWitnessRole] = useState('');
  const [interviewDate, setInterviewDate] = useState('');
  const [submittingStmt, setSubmittingStmt] = useState(false);
  const [formError, setFormError] = useState(null);

  // Evidence filtering
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedWitness, setSelectedWitness] = useState('ALL');

  // Initial data loading with cleanup
  useEffect(() => {
    let ignore = false;
    Promise.allSettled([getCase(), getHealth()])
      .then(([caseRes, healthRes]) => {
        if (ignore) return;
        if (caseRes.status === 'fulfilled') {
          setCaseData(caseRes.value);
        } else {
          setActionError(`Failed to fetch case data: ${caseRes.reason.message}`);
        }
        if (healthRes.status === 'fulfilled') {
          setHealthData(healthRes.value);
        }
        setLoadingCase(false);
      })
      .catch((err) => {
        if (ignore) return;
        setActionError(err.message || 'An unexpected error occurred.');
        setLoadingCase(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  // Handle statement submission
  async function handleAddStatement(e) {
    e.preventDefault();
    setFormError(null);
    setActionSuccess(null);

    const trimmedName = witnessName.trim();
    const trimmedText = statementText.trim();

    if (!trimmedName) {
      setFormError('Witness Name is required.');
      return;
    }
    if (!trimmedText) {
      setFormError('Verbatim Statement Text is required.');
      return;
    }

    setSubmittingStmt(true);
    try {
      const payload = {
        witness_name: trimmedName,
        text: trimmedText,
        statement_id: statementId.trim() || undefined,
        role: witnessRole.trim() || undefined,
        interview_date: interviewDate.trim() || undefined,
      };

      const newStmt = await addStatement(payload);

      // Update local state without losing user progress
      setCaseData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          statements: [...(prev.statements || []), newStmt],
        };
      });

      // Clear form inputs
      setWitnessName('');
      setStatementId('');
      setStatementText('');
      setWitnessRole('');
      setInterviewDate('');
      setActionSuccess(`Statement '${newStmt.statement_id}' for '${newStmt.witness_name}' was successfully recorded.`);
    } catch (err) {
      setFormError(err.message || 'Failed to add statement.');
    } finally {
      setSubmittingStmt(false);
    }
  }

  // Handle case reset
  async function handleResetCase() {
    if (!window.confirm('Reset to original sample case? Any newly added statements in this session will be cleared.')) {
      return;
    }
    setActionError(null);
    setActionSuccess(null);
    try {
      const reset = await resetCase();
      setCaseData(reset);
      setAnalysisResults(null);
      setActionSuccess('Case file reset to default sample data.');
    } catch (err) {
      setActionError(`Reset failed: ${err.message}`);
    }
  }

  // Handle analysis
  async function handleAnalyze() {
    setAnalyzing(true);
    setActionError(null);
    try {
      const results = await analyzeAll();
      setAnalysisResults(results);
      setActionSuccess('Case intelligence analysis completed.');
    } catch (err) {
      setActionError(`Analysis failed: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  }

  // Filtered statements calculation
  const statements = useMemo(() => caseData?.statements || [], [caseData?.statements]);
  const uniqueWitnesses = useMemo(() => {
    const set = new Set();
    statements.forEach((s) => {
      const name = s.witness_name || s.witness;
      if (name) set.add(name);
    });
    return Array.from(set).sort();
  }, [statements]);

  const filteredStatements = useMemo(() => {
    return statements.filter((s) => {
      const wName = (s.witness_name || s.witness || '').toLowerCase();
      const sId = (s.statement_id || s.id || '').toLowerCase();
      const text = (s.text || s.statement || '').toLowerCase();
      const query = searchQuery.trim().toLowerCase();

      const matchesWitness = selectedWitness === 'ALL' || (s.witness_name || s.witness) === selectedWitness;
      const matchesSearch = !query || wName.includes(query) || sId.includes(query) || text.includes(query);

      return matchesWitness && matchesSearch;
    });
  }, [statements, searchQuery, selectedWitness]);

  // Metric counts
  const witnessCount = statements.length;
  const extractedPeopleCount = analysisResults?.identities?.people?.length ?? '--';
  const inconsistenciesCount = Array.isArray(analysisResults?.inconsistencies)
    ? analysisResults.inconsistencies.length
    : '--';

  // Timeline results: backend returns an event list, or an object with an error field
  const timelineData = Array.isArray(analysisResults?.timeline) ? analysisResults.timeline : null;
  const timelineError = !timelineData && analysisResults?.timeline ? analysisResults.timeline.error : null;

  return (
    <MotionConfig reducedMotion="user">
    <div className="app-shell">
      {/* Top navbar with nav toggle — hamburger on the top left */}
      <div className="mobile-topbar">
        <motion.button
          whileTap={{ scale: 0.94 }}
          className="mobile-nav-btn"
          onClick={() => setNavOpen((open) => !open)}
          aria-expanded={navOpen}
          aria-label={navOpen ? 'Close navigation menu' : 'Open navigation menu'}
        >
          {navOpen ? <X size={16} /> : <Menu size={16} />}
        </motion.button>
        <div className="mobile-topbar-left">
          <div className="brand-icon-box">
            <Scale size={16} strokeWidth={2.2} />
          </div>
          <span className="mobile-topbar-title">CaseWeaver Lite</span>
          <span className="badge badge-id">{caseData?.case_id || 'CW-001'}</span>
        </div>
      </div>

      <div className="app-layout">

      {/* Sidebar */}
      <aside className={`app-sidebar${navOpen ? ' nav-open' : ''}`}>
        <div className="brand-section">
          <div className="brand-title-wrap">
            <div className="brand-icon-box">
              <Scale size={18} strokeWidth={2.2} />
            </div>
            <div className="brand-text">
              <h1>CaseWeaver</h1>
              <div className="tagline">Intelligence &bull; Lite</div>
            </div>
          </div>
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>

        <div>
          <div className="sidebar-group-title">
            <ShieldCheck size={13} />
            Active Case
          </div>
          <div className="case-card-compact">
            <div className="case-name">{caseData?.case_name || 'Loading Case...'}</div>
            <div className="case-meta">
              <span>{caseData?.case_id || 'CW-001'}</span>
              <span>&bull;</span>
              <Calendar size={12} />
              <span>{caseData?.incident_date || '2026-10-15'}</span>
            </div>
            {caseData?.is_demo && (
              <div style={{ marginTop: '0.45rem' }}>
                <span className="badge badge-demo">FICTIONAL DEMO CASE</span>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="sidebar-group-title">Workspace</div>
          <nav className="nav-menu">
            <motion.button
              whileTap={{ scale: 0.98 }}
              className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => goTab('overview')}
            >
              {activeTab === 'overview' && (
                <motion.span
                  layoutId="nav-active-pill"
                  className="nav-active-pill"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                />
              )}
              <LayoutDashboard size={16} />
              <span>Overview</span>
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.98 }}
              className={`nav-item ${activeTab === 'evidence' ? 'active' : ''}`}
              onClick={() => goTab('evidence')}
            >
              {activeTab === 'evidence' && (
                <motion.span
                  layoutId="nav-active-pill"
                  className="nav-active-pill"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                />
              )}
              <FileText size={16} />
              <span>Evidence</span>
              <span className="nav-count">{witnessCount}</span>
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.98 }}
              className={`nav-item ${activeTab === 'identities' ? 'active' : ''}`}
              onClick={() => goTab('identities')}
            >
              {activeTab === 'identities' && (
                <motion.span
                  layoutId="nav-active-pill"
                  className="nav-active-pill"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                />
              )}
              <Users size={16} />
              <span>Identities</span>
              {extractedPeopleCount !== '--' && <span className="nav-count">{extractedPeopleCount}</span>}
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.98 }}
              className={`nav-item ${activeTab === 'contradictions' ? 'active' : ''}`}
              onClick={() => goTab('contradictions')}
            >
              {activeTab === 'contradictions' && (
                <motion.span
                  layoutId="nav-active-pill"
                  className="nav-active-pill"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                />
              )}
              <GitCompare size={16} />
              <span>Contradictions</span>
              {inconsistenciesCount !== '--' && <span className="nav-count">{inconsistenciesCount}</span>}
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.98 }}
              className={`nav-item ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => goTab('timeline')}
            >
              {activeTab === 'timeline' && (
                <motion.span
                  layoutId="nav-active-pill"
                  className="nav-active-pill"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                />
              )}
              <Clock size={16} />
              <span>Timeline</span>
            </motion.button>
          </nav>
        </div>

        <div style={{ marginTop: 'auto' }}>
          <div className="sidebar-group-title">
            <Sparkles size={13} />
            Engine Modules
          </div>
          <div className="module-status-list">
            <div className="module-status-item">
              <span>Identity Engine</span>
              <span className={`badge ${healthData?.modules?.identity?.available ? 'badge-available' : 'badge-unavailable'}`}>
                {healthData?.modules?.identity?.available ? (
                  <>
                    <CheckCircle2 size={10} /> Available
                  </>
                ) : (
                  <>
                    <XCircle size={10} /> Offline
                  </>
                )}
              </span>
            </div>
            <div className="module-status-item">
              <span>Inconsistency Detector</span>
              <span className={`badge ${healthData?.modules?.inconsistency?.available ? 'badge-available' : 'badge-unavailable'}`}>
                {healthData?.modules?.inconsistency?.available ? (
                  <>
                    <CheckCircle2 size={10} /> Available
                  </>
                ) : (
                  <>
                    <XCircle size={10} /> Offline
                  </>
                )}
              </span>
            </div>
            <div className="module-status-item">
              <span>Timeline Engine</span>
              <span className={`badge ${healthData?.modules?.timeline?.available ? 'badge-available' : 'badge-unavailable'}`}>
                {healthData?.modules?.timeline?.available ? (
                  <>
                    <CheckCircle2 size={10} /> Available
                  </>
                ) : (
                  <>
                    <XCircle size={10} /> Offline
                  </>
                )}
              </span>
            </div>
            <div className="module-status-item">
              <span>Gemma AI Client</span>
              <span className={`badge ${healthData?.modules?.gemma?.available ? 'badge-available' : 'badge-unavailable'}`}>
                {healthData?.modules?.gemma?.available ? (
                  <>
                    <CheckCircle2 size={10} /> Available
                  </>
                ) : (
                  <>
                    <XCircle size={10} /> Offline
                  </>
                )}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">
        {/* Mandatory Non-Guilt Disclaimer Banner */}
        <div className="cw-disclaimer-banner">
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>
            <strong>AI-assisted evidence organization.</strong> Findings require human verification and are not conclusions of guilt.
          </span>
        </div>

        {/* Header Bar */}
        <header className="main-header">
          <div className="header-left">
            <h2>
              {caseData?.case_name || 'Investigation Workspace'}
              {caseData?.is_demo && <span className="badge badge-demo">DEMO CASE</span>}
            </h2>
            <div className="meta">
              <span>Case ID: {caseData?.case_id || 'CW-001'}</span>
              <span>&bull;</span>
              <span>Incident: {caseData?.incident_date || '2026-10-15'}</span>
              <span>&bull;</span>
              <span>{witnessCount} Recorded Witness Statements</span>
            </div>
          </div>
          <div className="header-actions">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="btn btn-secondary"
              onClick={handleResetCase}
              disabled={loadingCase}
            >
              <RotateCcw size={14} />
              Reset Demo
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={analyzing || loadingCase}
            >
              {analyzing ? (
                <>
                  <span className="spinner"></span> Analyzing Case...
                </>
              ) : (
                <>
                  <Sparkles size={14} /> Analyze Case
                </>
              )}
            </motion.button>
          </div>
        </header>

        {/* Global Notifications */}
        <div style={{ padding: '1rem 2rem 0' }}>
          <AnimatePresence>
            {actionSuccess && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="alert alert-success"
              >
                <CheckCircle2 size={16} />
                <span>{actionSuccess}</span>
              </motion.div>
            )}
            {actionError && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="alert alert-error"
              >
                <XCircle size={16} />
                <span>{actionError}</span>
              </motion.div>
            )}
            {loadingCase && (
              <div className="alert alert-info">
                <span className="spinner"></span> Connecting to backend at {import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}...
              </div>
            )}
          </AnimatePresence>
        </div>

        {/* Tab View Container */}
        <div className="view-container">
          <AnimatePresence mode="wait">
            {/* 1. OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <motion.div
                key="overview"
                variants={fadeInVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}
              >
                {/* Metrics */}
                <motion.div className="metrics-row" variants={staggerContainer} initial="hidden" animate="visible">
                  <motion.div className="cw-card" variants={itemVariants}>
                    <div className="metric-header">
                      <span className="metric-title">Witness Statements</span>
                      <FileText size={16} />
                    </div>
                    <div className="metric-value">{witnessCount}</div>
                    <div className="metric-sub">Recorded in active case file</div>
                  </motion.div>
                  <motion.div className="cw-card" variants={itemVariants}>
                    <div className="metric-header">
                      <span className="metric-title">Extracted People</span>
                      <Users size={16} />
                    </div>
                    <div className="metric-value">{extractedPeopleCount}</div>
                    <div className="metric-sub">
                      {extractedPeopleCount === '--' ? 'Run "Analyze Case" to compute' : 'Identified from witness evidence'}
                    </div>
                  </motion.div>
                  <motion.div className="cw-card" variants={itemVariants}>
                    <div className="metric-header">
                      <span className="metric-title">Active Contradictions</span>
                      <GitCompare size={16} />
                    </div>
                    <div className="metric-value">{inconsistenciesCount}</div>
                    <div className="metric-sub">Differences requiring human review</div>
                  </motion.div>
                </motion.div>

                {/* Case Information */}
                <div className="cw-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.45rem' }}>
                    <ShieldCheck size={16} style={{ color: 'var(--accent-blue)' }} />
                    <h3 style={{ fontSize: '1.05rem', color: 'var(--text-primary)' }}>Case File Summary</h3>
                  </div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.6' }}>
                    {caseData?.summary || 'No summary recorded for this case.'}
                  </p>
                </div>

                {/* Add Witness Statement Form */}
                <div className="form-card">
                  <div className="form-header">
                    <div className="form-header-icon">
                      <PlusCircle size={18} />
                    </div>
                    <div>
                      <h3>Add Witness Statement</h3>
                      <p>Record a new testimony. Statements are preserved verbatim with strict non-guilt formatting.</p>
                    </div>
                  </div>

                  {formError && (
                    <div className="alert alert-error">
                      <AlertTriangle size={15} />
                      <span>{formError}</span>
                    </div>
                  )}

                  <form onSubmit={handleAddStatement}>
                    <div className="form-grid">
                      <div className="form-group">
                        <label htmlFor="witness-name">
                          <User size={13} /> Witness Name *
                        </label>
                        <input
                          id="witness-name"
                          className="form-input"
                          placeholder="e.g. Jane Doe"
                          value={witnessName}
                          onChange={(e) => setWitnessName(e.target.value)}
                          disabled={submittingStmt}
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor="statement-id">Statement ID (Auto-generated if blank)</label>
                        <input
                          id="statement-id"
                          className="form-input"
                          placeholder="e.g. ST-005"
                          value={statementId}
                          onChange={(e) => setStatementId(e.target.value)}
                          disabled={submittingStmt}
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor="witness-role">Witness Role (Optional)</label>
                        <input
                          id="witness-role"
                          className="form-input"
                          placeholder="e.g. Bystander, Shopkeeper"
                          value={witnessRole}
                          onChange={(e) => setWitnessRole(e.target.value)}
                          disabled={submittingStmt}
                        />
                      </div>

                      <div className="form-group">
                        <label htmlFor="interview-date">
                          <Calendar size={13} /> Interview Date/Time (Optional)
                        </label>
                        <input
                          id="interview-date"
                          className="form-input"
                          placeholder="e.g. 2026-10-15 14:00"
                          value={interviewDate}
                          onChange={(e) => setInterviewDate(e.target.value)}
                          disabled={submittingStmt}
                        />
                      </div>

                      <div className="form-group full-width">
                        <label htmlFor="verbatim-text">
                          <Quote size={13} /> Verbatim Statement Text *
                        </label>
                        <textarea
                          id="verbatim-text"
                          className="form-textarea"
                          placeholder="Exact contiguous text as spoken by the witness..."
                          value={statementText}
                          onChange={(e) => setStatementText(e.target.value)}
                          disabled={submittingStmt}
                        />
                      </div>
                    </div>

                    <motion.button
                      whileHover={{ scale: 1.01 }}
                      whileTap={{ scale: 0.99 }}
                      type="submit"
                      className="btn btn-primary"
                      disabled={submittingStmt}
                    >
                      {submittingStmt ? (
                        <>
                          <span className="spinner"></span> Recording Statement...
                        </>
                      ) : (
                        <>
                          <PlusCircle size={15} /> Record Witness Statement
                        </>
                      )}
                    </motion.button>
                  </form>
                </div>
              </motion.div>
            )}

            {/* 2. EVIDENCE TAB */}
            {activeTab === 'evidence' && (
              <motion.div
                key="evidence"
                variants={fadeInVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
              >
                <div className="view-header">
                  <h3>
                    <FileText size={20} style={{ color: 'var(--accent-blue)' }} /> Evidence Workspace
                  </h3>
                  <p>Traceable witness statements and source quotations with exact original phrasing.</p>
                </div>

                {/* Filters */}
                <div className="filter-bar">
                  <div className="search-input-wrapper">
                    <Search size={15} className="search-icon-inside" />
                    <input
                      className="form-input"
                      placeholder="Search witness names, statement IDs, or quote content..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>
                  <div className="filter-select">
                    <select
                      className="form-select"
                      style={{ width: '100%' }}
                      value={selectedWitness}
                      onChange={(e) => setSelectedWitness(e.target.value)}
                    >
                      <option value="ALL">All Witnesses ({statements.length})</option>
                      {uniqueWitnesses.map((w) => (
                        <option key={w} value={w}>
                          {w}
                        </option>
                      ))}
                    </select>
                  </div>
                  {(searchQuery || selectedWitness !== 'ALL') && (
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedWitness('ALL');
                      }}
                    >
                      Clear Filters
                    </button>
                  )}
                </div>

                <div style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Showing <strong style={{ color: 'var(--accent-blue)' }}>{filteredStatements.length}</strong> of{' '}
                  <strong>{statements.length}</strong> recorded statement(s)
                </div>

                {/* Statements List */}
                {filteredStatements.length === 0 ? (
                  <motion.div variants={itemVariants} className="cw-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
                    <Filter size={28} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.5rem' }} />
                    <h4 style={{ color: 'var(--text-primary)', marginBottom: '0.25rem' }}>No Statements Match Filter</h4>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      Try clearing or adjusting your search keywords.
                    </p>
                  </motion.div>
                ) : (
                  <div className="evidence-list">
                    {filteredStatements.map((stmt) => (
                      <motion.div
                        key={stmt.statement_id}
                        className="statement-card"
                        variants={revealVariants}
                        initial="hidden"
                        whileInView="visible"
                        viewport={revealViewport}
                      >
                        <div className="statement-header">
                          <div>
                            <div className="witness-title">
                              <User size={15} style={{ color: 'var(--accent-blue)' }} />
                              {stmt.witness_name}
                            </div>
                            <div className="statement-meta">
                              {stmt.role && <span>Role: {stmt.role}</span>}
                              {stmt.interview_date && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                  <Calendar size={12} /> {stmt.interview_date}
                                </span>
                              )}
                            </div>
                          </div>
                          <span className="badge badge-id">{stmt.statement_id}</span>
                        </div>

                        <div className="verbatim-block">
                          <span className="verbatim-label">
                            <Quote size={11} /> Verbatim Witness Statement:
                          </span>
                          <div className="verbatim-text">"{stmt.text}"</div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {/* 3. IDENTITIES TAB */}
            {activeTab === 'identities' && (
              <motion.div
                key="identities"
                variants={fadeInVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
              >
                <div className="view-header">
                  <h3>
                    <Users size={20} style={{ color: 'var(--accent-blue)' }} /> Extracted Identities & Entities
                  </h3>
                  <p>
                    Extracted from witness statements via <code>modules/identity_engine.py</code>.
                  </p>
                </div>

                {!analysisResults ? (
                  <div className="cw-card" style={{ textAlign: 'center', padding: '3rem' }}>
                    <Users size={32} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.75rem' }} />
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                      No identity analysis has been run for this case session yet.
                    </p>
                    {analyzing ? (
                      <div className="skeleton-card">
                        <div className="skeleton-line" style={{ width: '55%' }} />
                        <div className="skeleton-line" style={{ width: '80%' }} />
                        <div className="skeleton-line" style={{ width: '65%' }} />
                      </div>
                    ) : (
                      <button className="btn btn-primary" onClick={handleAnalyze}>
                        Run Case Analysis
                      </button>
                    )}
                  </div>
                ) : (
                  <>
                    {analysisResults.identities?.error && (
                      <div className="alert alert-warning">
                        <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                        <span>
                          <strong>Identity engine notice:</strong> {analysisResults.identities.error}
                        </span>
                      </div>
                    )}
                  <motion.div variants={staggerContainer} initial="hidden" animate="visible" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {/* Warnings */}
                    {analysisResults.identities?.warnings?.length > 0 && (
                      <div className="alert alert-warning">
                        <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                        <div>
                          <strong>Engine Notice:</strong>
                          <ul style={{ marginLeft: '1.25rem', marginTop: '0.25rem' }}>
                            {analysisResults.identities.warnings.map((w, idx) => (
                              <li key={idx}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}

                    {/* People */}
                    <div className="cw-card">
                      <h4 style={{ color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <User size={16} /> Identified People ({analysisResults.identities?.people?.length || 0})
                      </h4>
                      {(!analysisResults.identities?.people || analysisResults.identities.people.length === 0) ? (
                        <p style={{ color: 'var(--text-secondary)' }}>No people extracted from statements.</p>
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                          {analysisResults.identities.people.map((person, idx) => (
                            <motion.div
                              key={idx}
                              variants={itemVariants}
                              style={{
                                backgroundColor: 'var(--bg-surface-inset)',
                                padding: '1rem',
                                borderRadius: 'var(--radius-sm)',
                                border: '1px solid var(--border-subtle)',
                              }}
                            >
                              <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.975rem' }}>
                                {person.canonical_name}
                              </div>
                              {person.aliases?.length > 0 && (
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                                  Aliases: {person.aliases.join(', ')}
                                </div>
                              )}
                              <div style={{ marginTop: '0.65rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                                Mentions: {person.mentions?.length || 0} statement citation(s)
                              </div>
                            </motion.div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Relationships */}
                    {analysisResults.identities?.relationships?.length > 0 && (
                      <div className="cw-card">
                        <h4 style={{ color: 'var(--text-primary)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <GitCompare size={16} /> Documented Relationships ({analysisResults.identities.relationships.length})
                        </h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                          {analysisResults.identities.relationships.map((rel, idx) => (
                            <div
                              key={idx}
                              style={{
                                padding: '0.75rem 1rem',
                                backgroundColor: 'var(--bg-surface-inset)',
                                borderRadius: 'var(--radius-sm)',
                                border: '1px solid var(--border-subtle)',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{rel.from_name}</span>
                                <span className="badge badge-demo">{rel.type}</span>
                                <ArrowRight size={13} style={{ color: 'var(--text-tertiary)' }} />
                                <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{rel.to_name}</span>
                              </div>
                              {rel.quotation && (
                                <div style={{ fontSize: '0.85rem', fontStyle: 'italic', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                                  "{rel.quotation}" &bull; <small style={{ color: 'var(--text-tertiary)' }}>Statement: {rel.statement_id}</small>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                  </>
                )}
              </motion.div>
            )}

            {/* 4. CONTRADICTIONS TAB */}
            {activeTab === 'contradictions' && (
              <motion.div
                key="contradictions"
                variants={fadeInVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
              >
                <div className="view-header">
                  <h3>
                    <GitCompare size={20} style={{ color: 'var(--accent-amber)' }} /> Contradiction Analysis
                  </h3>
                  <p>
                    Neutral discrepancy detection via <code>modules/inconsistency_detector.py</code>.
                  </p>
                </div>

                {analysisResults?.inconsistencies?.error && (
                  <div className="alert alert-warning">
                    <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                    <span>
                      <strong>Inconsistency detector notice:</strong> {analysisResults.inconsistencies.error}
                    </span>
                  </div>
                )}

                {!analysisResults ? (
                  <div className="cw-card" style={{ textAlign: 'center', padding: '3rem' }}>
                    <GitCompare size={32} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.75rem' }} />
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                      No inconsistency analysis has been run for this case session yet.
                    </p>
                    {analyzing ? (
                      <div className="skeleton-card">
                        <div className="skeleton-line" style={{ width: '55%' }} />
                        <div className="skeleton-line" style={{ width: '80%' }} />
                        <div className="skeleton-line" style={{ width: '65%' }} />
                      </div>
                    ) : (
                      <button className="btn btn-primary" onClick={handleAnalyze}>
                        Run Case Analysis
                      </button>
                    )}
                  </div>
                ) : Array.isArray(analysisResults.inconsistencies) && analysisResults.inconsistencies.length === 0 ? (
                  <div className="cw-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
                    <CheckCircle2 size={32} style={{ color: 'var(--accent-emerald)', margin: '0 auto 0.5rem' }} />
                    <h4 style={{ color: 'var(--text-primary)', marginBottom: '0.35rem' }}>No Active Discrepancies Detected</h4>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '600px', margin: '0 auto' }}>
                      The backend inconsistency detector reported no direct statement contradictions (requires Google Gemma client to detect semantic conflicts).
                    </p>
                  </div>
                ) : (
                  <div>
                    {Array.isArray(analysisResults.inconsistencies) &&
                      analysisResults.inconsistencies.map((item, idx) => (
                        <motion.div
                          key={idx}
                          className="contradiction-card"
                          variants={revealVariants}
                          initial="hidden"
                          whileInView="visible"
                          viewport={revealViewport}
                        >
                          <div className="contradiction-header">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span className="badge badge-review">
                                <AlertTriangle size={12} /> Differences require human review
                              </span>
                              <span className="badge badge-demo">{item.type}</span>
                            </div>
                            {item.confidence !== undefined && (
                              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                Confidence: {Math.round(item.confidence * 100)}%
                              </span>
                            )}
                          </div>

                          <p style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: '0.95rem' }}>
                            {item.description}
                          </p>

                          {item.quotations?.length > 0 && (
                            <div className="quotes-comparison">
                              {item.quotations.map((q, qIdx) => (
                                <div key={qIdx} className="comparison-box">
                                  <div className="box-witness">
                                    <span>{q.witness || 'Witness'}</span>
                                    <span className="badge badge-id">{q.statement_id}</span>
                                  </div>
                                  <div style={{ fontSize: '0.875rem', fontStyle: 'italic', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                    "{q.quotation}"
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </motion.div>
                      ))}
                  </div>
                )}
              </motion.div>
            )}

            {/* 5. TIMELINE TAB */}
            {activeTab === 'timeline' && (
              <motion.div
                key="timeline"
                variants={fadeInVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
              >
                <div className="view-header">
                  <h3>
                    <Clock size={20} style={{ color: 'var(--accent-blue)' }} /> Evidence-Linked Timeline
                  </h3>
                  <p>Chronological event reconstruction with verbatim citations.</p>
                </div>

                {!analysisResults ? (
                  <div className="cw-card" style={{ textAlign: 'center', padding: '3rem' }}>
                    <Clock size={32} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.75rem' }} />
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
                      No timeline analysis has been run for this case session yet.
                    </p>
                    {analyzing ? (
                      <div className="skeleton-card">
                        <div className="skeleton-line" style={{ width: '55%' }} />
                        <div className="skeleton-line" style={{ width: '80%' }} />
                        <div className="skeleton-line" style={{ width: '65%' }} />
                      </div>
                    ) : (
                      <button className="btn btn-primary" onClick={handleAnalyze}>
                        Run Case Analysis
                      </button>
                    )}
                  </div>
                ) : timelineError ? (
                  <div className="cw-card" style={{ borderLeft: '3px solid var(--accent-rose)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.75rem' }}>
                      <span className="badge badge-unavailable">
                        <XCircle size={12} /> Module Unavailable
                      </span>
                      <strong style={{ color: 'var(--text-primary)' }}>modules/timeline.py</strong>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.6' }}>
                      {timelineError === 'Module not yet created by team'
                        ? 'The shared timeline extraction module has not yet been implemented by teammates. In accordance with project integrity standards, event timestamps and chronologies are never fabricated or guessed.'
                        : `The timeline engine could not complete event extraction: ${timelineError}`}
                    </p>
                    <div
                      style={{
                        backgroundColor: 'var(--bg-surface-inset)',
                        padding: '0.85rem 1rem',
                        borderRadius: 'var(--radius-sm)',
                        marginTop: '1.15rem',
                        fontSize: '0.8rem',
                        color: 'var(--text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                      }}
                    >
                      <ChevronRight size={14} style={{ color: 'var(--text-tertiary)' }} />
                      <span>
                        <strong>Expected Interface:</strong>{' '}
                        <code>modules.timeline.extract_events(case_data: dict) -&gt; list[dict]</code>
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="timeline-list">
                    {timelineData.map((event, idx) => {
                      const when = pickField(event, ['time', 'time_hint', 'time_text', 'when', 'timestamp']);
                      const who = pickField(event, ['person', 'who', 'actor', 'subject']);
                      const where = pickField(event, ['location', 'where', 'place']);
                      const quote = pickField(event, ['quotation', 'quote', 'source_quotation']);
                      const sid = pickField(event, ['statement_id', 'source_statement_id', 'source_id']);
                      const desc = pickField(event, ['description', 'event', 'text', 'summary']);
                      return (
                        <motion.div
                          key={idx}
                          className="timeline-item"
                          variants={revealVariants}
                          initial="hidden"
                          whileInView="visible"
                          viewport={revealViewport}
                        >
                          <div className="timeline-card">
                            <div className="timeline-top">
                              {when && (
                                <span className="badge badge-id">
                                  <Clock size={11} /> {when}
                                </span>
                              )}
                              {who && (
                                <span className="timeline-who">
                                  <User size={13} /> {who}
                                </span>
                              )}
                              {where && <span className="timeline-where">{where}</span>}
                            </div>
                            {desc && <div className="timeline-desc">{desc}</div>}
                            {(quote || sid) && (
                              <div className="verbatim-block">
                                <span className="verbatim-label">
                                  <Quote size={11} /> Source Citation {sid ? `— ${sid}` : ''}
                                </span>
                                {quote && <div className="verbatim-text">"{quote}"</div>}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      );
                    })}
                    {timelineData.length === 0 && (
                      <div className="cw-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
                        <Calendar size={26} style={{ color: 'var(--text-tertiary)', margin: '0 auto 0.5rem' }} />
                        <h4 style={{ color: 'var(--text-primary)', marginBottom: '0.35rem' }}>No Datable Events Extracted</h4>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                          The timeline engine found no events with reliable time references. Unknown times are never guessed.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
    </div>
    </MotionConfig>
  );
}
