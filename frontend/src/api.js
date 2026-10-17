/**
 * CaseWeaver Lite API Client
 * Wraps FastAPI endpoints with typed error handling and Vite env configuration.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // Non-JSON error body
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export async function getHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  return handleResponse(res);
}

export async function getCase() {
  const res = await fetch(`${API_BASE}/api/case`);
  return handleResponse(res);
}

export async function resetCase() {
  const res = await fetch(`${API_BASE}/api/case/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(res);
}

export async function addStatement(statement) {
  const res = await fetch(`${API_BASE}/api/case/statements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(statement),
  });
  return handleResponse(res);
}

export async function analyzeAll() {
  const res = await fetch(`${API_BASE}/api/analyze/all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(res);
}

export async function analyzeIdentities() {
  const res = await fetch(`${API_BASE}/api/analyze/identities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(res);
}

export async function analyzeInconsistencies() {
  const res = await fetch(`${API_BASE}/api/analyze/inconsistencies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(res);
}

export async function analyzeTimeline() {
  const res = await fetch(`${API_BASE}/api/analyze/timeline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return handleResponse(res);
}
