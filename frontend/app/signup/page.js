'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import AuthCard from '../../components/AuthCard';
import { signup } from '../../lib/api';

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ display_name: '', email: '', password: '', confirm_password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const onChange = (event) => {
    setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);

    try {
      const data = await signup(form.display_name, form.email, form.password);
      setSuccess(`Account created for ${data.email || form.email}. You can now log in.`);
      setTimeout(() => {
        router.push('/login');
      }, 900);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-shell">
      <AuthCard
        title="Create account"
        subtitle="Set up access to your organization’s PM RAG environment."
        buttonLabel="Sign up"
        footerText="Already have an account?"
        footerHref="/login"
        footerLinkLabel="Log in"
        form={form}
        includeName
        includeConfirmPassword
        onChange={onChange}
        onSubmit={onSubmit}
        loading={loading}
        error={error}
        success={success}
      />
    </main>
  );
}
