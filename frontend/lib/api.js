const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:4000';

async function request(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
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
