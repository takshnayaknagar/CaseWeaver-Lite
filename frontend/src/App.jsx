import { useState, useEffect, useMemo } from 'react';
import {
  getCase,
  getHealth,
  addStatement,
  resetCase,
  analyzeAll,
} from './api';
import './App.css';

export default function App() {
  // Navigation
  const [activeTab, setActiveTab] = useState('overview');

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
      setActionSuccess(`Statement '${newStmt.statement_id}' for '${newStmt.witness_name}' was successfully added.`);
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
      setActionSuccess('Case analysis completed successfully.');
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

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div className="brand-section">
          <h1>⚖️ CaseWeaver Lite</h1>
          <div className="tagline">Evidence & Timeline Assistant</div>
        </div>

        <div>
          <div className="sidebar-group-title">Active Case</div>
          <div className="case-card-compact">
            <div className="case-name">{caseData?.case_name || 'Loading Case...'}</div>
            <div className="case-meta">
              ID: {caseData?.case_id || 'CW-001'} &bull; {caseData?.incident_date || '2026-10-15'}
            </div>
            {caseData?.is_demo && (
              <div style={{ marginTop: '0.4rem' }}>
                <span className="badge badge-demo">FICTIONAL DEMO CASE</span>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="sidebar-group-title">Navigation</div>
          <nav className="nav-menu">
            <button
              className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <span>📊 Overview</span>
            </button>
            <button
              className={`nav-item ${activeTab === 'evidence' ? 'active' : ''}`}
              onClick={() => setActiveTab('evidence')}
            >
              <span>📁 Evidence</span>
              <span className="nav-count">{witnessCount}</span>
            </button>
            <button
              className={`nav-item ${activeTab === 'identities' ? 'active' : ''}`}
              onClick={() => setActiveTab('identities')}
            >
              <span>🔍 Identities</span>
              {extractedPeopleCount !== '--' && <span className="nav-count">{extractedPeopleCount}</span>}
            </button>
            <button
              className={`nav-item ${activeTab === 'contradictions' ? 'active' : ''}`}
              onClick={() => setActiveTab('contradictions')}
            >
              <span>⚖️ Contradictions</span>
              {inconsistenciesCount !== '--' && <span className="nav-count">{inconsistenciesCount}</span>}
            </button>
            <button
              className={`nav-item ${activeTab === 'timeline' ? 'active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              <span>⏱️ Timeline</span>
            </button>
          </nav>
        </div>

        <div style={{ marginTop: 'auto' }}>
          <div className="sidebar-group-title">Backend Integrations</div>
          <div className="module-status-list">
            <div className="module-status-item">
              <span>Identity Engine</span>
              <span className={`badge ${healthData?.modules?.identity?.available ? 'badge-available' : 'badge-unavailable'}`}>
                {healthData?.modules?.identity?.available ? 'Available' : 'Unavailable'}
              </span>
            </div>
            <div className="module-status-item">
              <span>Inconsistency Detector</span>
              <span className={`badge ${healthData?.modules?.inconsistency?.available ? 'badge-available' : 'badge-unavailable'}`}>
                {healthData?.modules?.inconsistency?.available ? 'Available' : 'Unavailable'}
              </span>
            </div>
            <div className="module-status-item">
              <span>Timeline Engine</span>
              <span className="badge badge-unavailable">Pending Teammate</span>
            </div>
            <div className="module-status-item">
              <span>Gemma AI Client</span>
              <span className="badge badge-unavailable">Pending Backend</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">
        {/* Mandatory Non-Guilt Disclaimer Banner */}
        <div className="cw-disclaimer-banner">
          <span style={{ fontSize: '1.1rem' }}>⚠️</span>
          <span>
            <strong>AI-assisted evidence organization.</strong> Findings require human verification and are not conclusions of guilt.
          </span>
        </div>

        {/* Header Bar */}
        <header className="main-header">
          <div className="header-left">
            <h2>
              {caseData?.case_name || 'Investigation Workspace'}
              {caseData?.is_demo && <span className="badge badge-demo">DEMO</span>}
            </h2>
            <div className="meta">
              Case ID: {caseData?.case_id || 'CW-001'} &bull; Incident: {caseData?.incident_date || '2026-10-15'} &bull; {witnessCount} Recorded Statements
            </div>
          </div>
          <div className="header-actions">
            <button className="btn btn-secondary" onClick={handleResetCase} disabled={loadingCase}>
              🔄 Reset Demo Case
            </button>
            <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing || loadingCase}>
              {analyzing ? (
                <>
                  <span className="spinner"></span> Analyzing...
                </>
              ) : (
                '🚀 Analyze Case'
              )}
            </button>
          </div>
        </header>

        {/* Global Notifications */}
        <div style={{ padding: '1rem 2rem 0' }}>
          {actionSuccess && <div className="alert alert-success">{actionSuccess}</div>}
          {actionError && <div className="alert alert-error">{actionError}</div>}
          {loadingCase && (
            <div className="alert alert-info">
              <span className="spinner"></span> Connecting to FastAPI backend at {import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}...
            </div>
          )}
        </div>

        {/* Tab View Container */}
        <div className="view-container">
          {/* 1. OVERVIEW TAB */}
          {activeTab === 'overview' && (
            <>
              {/* Metrics */}
              <div className="metrics-row">
                <div className="cw-card">
                  <div className="metric-title">Witness Statements Analysed</div>
                  <div className="metric-value">{witnessCount}</div>
                  <div className="metric-sub">Recorded in active case file</div>
                </div>
                <div className="cw-card">
                  <div className="metric-title">Extracted People / Entities</div>
                  <div className="metric-value">{extractedPeopleCount}</div>
                  <div className="metric-sub">
                    {extractedPeopleCount === '--' ? 'Run "Analyze Case" to compute' : 'Identified from witness evidence'}
                  </div>
                </div>
                <div className="cw-card">
                  <div className="metric-title">Active Contradictions</div>
                  <div className="metric-value">{inconsistenciesCount}</div>
                  <div className="metric-sub">Differences requiring human review</div>
                </div>
              </div>

              {/* Case Information */}
              <div className="cw-card">
                <h3 style={{ fontSize: '1.05rem', color: '#fff', marginBottom: '0.5rem' }}>
                  📋 Case File Summary
                </h3>
                <p style={{ color: '#cbd5e1', fontSize: '0.9rem', lineHeight: '1.6' }}>
                  {caseData?.summary || 'No summary recorded for this case.'}
                </p>
              </div>

              {/* Add Witness Statement Form */}
              <div className="form-card">
                <div className="form-header">
                  <h3>➕ Add Witness Statement</h3>
                  <p>Record a new testimony. Statements are preserved verbatim with strict non-guilt formatting.</p>
                </div>

                {formError && <div className="alert alert-error">{formError}</div>}

                <form onSubmit={handleAddStatement}>
                  <div className="form-grid">
                    <div className="form-group">
                      <label htmlFor="witness-name">Witness Name *</label>
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
                      <label htmlFor="interview-date">Interview Date/Time (Optional)</label>
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
                      <label htmlFor="verbatim-text">Verbatim Statement Text *</label>
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

                  <button type="submit" className="btn btn-primary" disabled={submittingStmt}>
                    {submittingStmt ? (
                      <>
                        <span className="spinner"></span> Saving Statement...
                      </>
                    ) : (
                      'Record Witness Statement'
                    )}
                  </button>
                </form>
              </div>
            </>
          )}

          {/* 2. EVIDENCE TAB */}
          {activeTab === 'evidence' && (
            <div>
              <div style={{ marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', color: '#fff' }}>📁 Evidence Workspace</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Traceable witness statements and source quotations with exact original phrasing.
                </p>
              </div>

              {/* Filters */}
              <div className="filter-bar">
                <div className="filter-search">
                  <input
                    className="form-input"
                    style={{ width: '100%' }}
                    placeholder="🔍 Search witness names, statement IDs, or quote content..."
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

              <div style={{ marginBottom: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                Showing <strong style={{ color: 'var(--accent-cyan)' }}>{filteredStatements.length}</strong> of{' '}
                <strong>{statements.length}</strong> recorded statement(s)
              </div>

              {/* Statements List */}
              {filteredStatements.length === 0 ? (
                <div className="cw-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
                  <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>🔍</div>
                  <h4 style={{ color: '#fff', marginBottom: '0.25rem' }}>No Statements Match Filter</h4>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    Try clearing or adjusting your search keywords.
                  </p>
                </div>
              ) : (
                <div className="evidence-list">
                  {filteredStatements.map((stmt) => (
                    <div key={stmt.statement_id} className="statement-card">
                      <div className="statement-header">
                        <div>
                          <div className="witness-title">{stmt.witness_name}</div>
                          <div className="statement-meta">
                            {stmt.role && <span>Role: {stmt.role}</span>}
                            {stmt.interview_date && <span>Interview: {stmt.interview_date}</span>}
                          </div>
                        </div>
                        <span className="badge badge-id">{stmt.statement_id}</span>
                      </div>

                      <div className="verbatim-block">
                        <span className="verbatim-label">Verbatim Witness Statement:</span>
                        <div className="verbatim-text">"{stmt.text}"</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 3. IDENTITIES TAB */}
          {activeTab === 'identities' && (
            <div>
              <div style={{ marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', color: '#fff' }}>🔍 Extracted Identities & Entities</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Extracted from witness statements via <code>modules/identity_engine.py</code>.
                </p>
              </div>

              {!analysisResults ? (
                <div className="cw-card" style={{ textAlign: 'center', padding: '3rem' }}>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
                    No identity analysis has been run for this case session yet.
                  </p>
                  <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing}>
                    {analyzing ? 'Analyzing...' : '🚀 Run Case Analysis'}
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  {/* Warnings */}
                  {analysisResults.identities?.warnings?.length > 0 && (
                    <div className="alert alert-warning">
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
                    <h4 style={{ color: '#fff', marginBottom: '1rem' }}>
                      Identified People ({analysisResults.identities?.people?.length || 0})
                    </h4>
                    {(!analysisResults.identities?.people || analysisResults.identities.people.length === 0) ? (
                      <p style={{ color: 'var(--text-muted)' }}>No people extracted from statements.</p>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                        {analysisResults.identities.people.map((person, idx) => (
                          <div
                            key={idx}
                            style={{
                              backgroundColor: 'var(--bg-card-subtle)',
                              padding: '1rem',
                              borderRadius: '6px',
                              border: '1px solid var(--border-color)',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: 'var(--accent-cyan)', fontSize: '1rem' }}>
                              {person.canonical_name}
                            </div>
                            {person.aliases?.length > 0 && (
                              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                                Aliases: {person.aliases.join(', ')}
                              </div>
                            )}
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                              Mentions: {person.mentions?.length || 0} statement(s)
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Relationships */}
                  {analysisResults.identities?.relationships?.length > 0 && (
                    <div className="cw-card">
                      <h4 style={{ color: '#fff', marginBottom: '1rem' }}>
                        Documented Relationships ({analysisResults.identities.relationships.length})
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {analysisResults.identities.relationships.map((rel, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: '0.75rem 1rem',
                              backgroundColor: 'var(--bg-card-subtle)',
                              borderRadius: '6px',
                              border: '1px solid var(--border-color)',
                            }}
                          >
                            <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{rel.from_name}</span>{' '}
                            <span className="badge badge-demo">{rel.type}</span>{' '}
                            <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{rel.to_name}</span>
                            {rel.quotation && (
                              <div style={{ fontSize: '0.85rem', fontStyle: 'italic', color: '#cbd5e1', marginTop: '0.35rem' }}>
                                "{rel.quotation}" &bull; <small style={{ color: 'var(--text-dim)' }}>Statement: {rel.statement_id}</small>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 4. CONTRADICTIONS TAB */}
          {activeTab === 'contradictions' && (
            <div>
              <div style={{ marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', color: '#fff' }}>⚖️ Contradiction Analysis</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Neutral discrepancy detection via <code>modules/inconsistency_detector.py</code>.
                </p>
              </div>

              {!analysisResults ? (
                <div className="cw-card" style={{ textAlign: 'center', padding: '3rem' }}>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
                    No inconsistency analysis has been run for this case session yet.
                  </p>
                  <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing}>
                    {analyzing ? 'Analyzing...' : '🚀 Run Case Analysis'}
                  </button>
                </div>
              ) : Array.isArray(analysisResults.inconsistencies) && analysisResults.inconsistencies.length === 0 ? (
                <div className="cw-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
                  <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>✅</div>
                  <h4 style={{ color: '#fff', marginBottom: '0.35rem' }}>No Active Discrepancies Detected</h4>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', maxWidth: '600px', margin: '0 auto' }}>
                    The backend inconsistency detector reported no direct statement contradictions (requires Google Gemma client to detect semantic conflicts).
                  </p>
                </div>
              ) : (
                <div>
                  {Array.isArray(analysisResults.inconsistencies) &&
                    analysisResults.inconsistencies.map((item, idx) => (
                      <div key={idx} className="contradiction-card">
                        <div className="contradiction-header">
                          <div>
                            <span className="badge badge-review">
                              ⚠️ Differences require human review
                            </span>
                            <span className="badge badge-demo" style={{ marginLeft: '0.5rem' }}>
                              {item.type}
                            </span>
                          </div>
                          {item.confidence !== undefined && (
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              Confidence: {Math.round(item.confidence * 100)}%
                            </span>
                          )}
                        </div>

                        <p style={{ color: '#f1f5f9', fontWeight: 500, fontSize: '0.95rem' }}>
                          {item.description}
                        </p>

                        {item.quotations?.length > 0 && (
                          <div className="quotes-comparison">
                            {item.quotations.map((q, qIdx) => (
                              <div key={qIdx} className="comparison-box">
                                <div className="box-witness">
                                  {q.witness || 'Witness'} <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>({q.statement_id})</span>
                                </div>
                                <div style={{ fontSize: '0.9rem', fontStyle: 'italic', color: '#e2e8f0' }}>
                                  "{q.quotation}"
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* 5. TIMELINE TAB */}
          {activeTab === 'timeline' && (
            <div>
              <div style={{ marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', color: '#fff' }}>⏱️ Evidence-Linked Timeline</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Chronological event reconstruction with verbatim citations.
                </p>
              </div>

              <div className="cw-card" style={{ borderLeft: '3px solid var(--accent-rose)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <span className="badge badge-unavailable">Module Unavailable</span>
                  <strong style={{ color: '#fff' }}>modules/timeline.py</strong>
                </div>
                <p style={{ color: '#cbd5e1', fontSize: '0.9rem', lineHeight: '1.6' }}>
                  The shared timeline extraction module has not yet been implemented by teammates. In accordance with project integrity standards, event timestamps and chronologies are never fabricated or guessed.
                </p>
                <div
                  style={{
                    backgroundColor: 'var(--bg-card-subtle)',
                    padding: '0.85rem',
                    borderRadius: '6px',
                    marginTop: '1rem',
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                  }}
                >
                  <strong>Expected Interface:</strong> <code>modules.timeline.extract_events(case_data: dict) -&gt; list[dict]</code>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
