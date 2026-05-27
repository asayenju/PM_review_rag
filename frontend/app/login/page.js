'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import AuthCard from '../../components/AuthCard';
import { login, saveAuthSession } from '../../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const onChange = (event) => {
    setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const data = await login(form.email, form.password);
      saveAuthSession(data);
      setSuccess(`Welcome back ${data.email || 'user'}. Login successful.`);
      router.push('/chat');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-shell">
      <AuthCard
        title="Log in"
        subtitle="Continue to your feature-scoped PM intelligence workspace."
        buttonLabel="Log in"
        footerText="No account yet?"
        footerHref="/signup"
        footerLinkLabel="Create one"
        form={form}
        onChange={onChange}
        onSubmit={onSubmit}
        loading={loading}
        error={error}
        success={success}
      />
    </main>
  );
}
