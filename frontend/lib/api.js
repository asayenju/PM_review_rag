const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:4000';

export function getAuthToken() {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem('pmrag_access_token');
}

export function saveAuthSession(data) {
  window.localStorage.setItem('pmrag_access_token', data.access_token);
  if (data.refresh_token) {
    window.localStorage.setItem('pmrag_refresh_token', data.refresh_token);
  }
  if (data.user_id) {
    window.localStorage.setItem('pmrag_user_id', data.user_id);
  }
  if (data.email) {
    window.localStorage.setItem('pmrag_email', data.email);
  }
}

export function clearAuthSession() {
  window.localStorage.removeItem('pmrag_access_token');
  window.localStorage.removeItem('pmrag_refresh_token');
  window.localStorage.removeItem('pmrag_user_id');
  window.localStorage.removeItem('pmrag_email');
}

async function request(path, payload, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (options.auth) {
    const token = getAuthToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method || 'POST',
    headers,
    body: payload === undefined ? undefined : JSON.stringify(payload)
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed. Please try again.');
  }

  return data;
}

export async function login(email, password) {
  return request('/api/auth/login', { email, password });
}

export async function signup(display_name, email, password) {
  return request('/api/auth/signup', { display_name, email, password });
}

export async function publicQuery(question) {
  return request('/api/public/query', { question });
}

export async function getAssignedFeatures() {
  return request('/api/me/features', undefined, { method: 'GET', auth: true });
}

export async function getConversations() {
  return request('/api/conversations', undefined, { method: 'GET', auth: true });
}

export async function createConversation(org_id, feature_id, title) {
  return request('/api/conversations', { org_id, feature_id, title }, { auth: true });
}

export async function getConversationMessages(conversationId) {
  return request(`/api/conversations/${conversationId}/messages`, undefined, { method: 'GET', auth: true });
}

export async function sendConversationMessage(conversationId, content) {
  return request(`/api/conversations/${conversationId}/messages`, { content }, { auth: true });
}
