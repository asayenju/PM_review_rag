'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Alert, Box, Button, CircularProgress, IconButton, InputAdornment, Paper, Stack, TextField, Typography } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';

export default function AuthCard({
  title,
  subtitle,
  buttonLabel,
  footerText,
  footerHref,
  footerLinkLabel,
  form,
  onChange,
  onSubmit,
  loading,
  error,
  success,
  includeName = false,
  includeConfirmPassword = false
}) {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  return (
    <Paper elevation={0} sx={{ width: '100%', maxWidth: 460, p: { xs: 3, md: 4 }, borderRadius: 6, backdropFilter: 'blur(16px)', background: 'rgba(10, 15, 35, 0.6)', border: '1px solid rgba(255,255,255,0.14)' }}>
      <Stack spacing={2.5}>
        <Stack direction="row" spacing={1.2} alignItems="center">
          <AutoAwesomeRoundedIcon sx={{ color: '#7dd3fc' }} />
          <Typography variant="overline" sx={{ letterSpacing: 1.5, color: '#a5b4fc' }}>PM RAG STUDIO</Typography>
        </Stack>

        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>{title}</Typography>
          <Typography variant="body2" sx={{ color: 'rgba(240,244,255,0.72)', mt: 0.5 }}>{subtitle}</Typography>
        </Box>

        {error ? <Alert severity="error">{error}</Alert> : null}
        {success ? <Alert severity="success">{success}</Alert> : null}

        <Stack component="form" onSubmit={onSubmit} spacing={1.6}>
          {includeName ? (
            <TextField
              label="Full Name"
              type="text"
              name="display_name"
              value={form.display_name || ''}
              onChange={onChange}
              required
              fullWidth
            />
          ) : null}
          <TextField
            label="Work Email"
            type="email"
            name="email"
            value={form.email}
            onChange={onChange}
            required
            fullWidth
          />
          <TextField
            label="Password"
            type={showPassword ? 'text' : 'password'}
            name="password"
            value={form.password}
            onChange={onChange}
            required
            fullWidth
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    edge="end"
                    aria-label="toggle password visibility"
                    onClick={() => setShowPassword((prev) => !prev)}
                  >
                    {showPassword ? <VisibilityOffRoundedIcon /> : <VisibilityRoundedIcon />}
                  </IconButton>
                </InputAdornment>
              )
            }}
          />
          {includeConfirmPassword ? (
            <TextField
              label="Confirm Password"
              type={showConfirmPassword ? 'text' : 'password'}
              name="confirm_password"
              value={form.confirm_password || ''}
              onChange={onChange}
              required
              fullWidth
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      edge="end"
                      aria-label="toggle confirm password visibility"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                    >
                      {showConfirmPassword ? <VisibilityOffRoundedIcon /> : <VisibilityRoundedIcon />}
                    </IconButton>
                  </InputAdornment>
                )
              }}
            />
          ) : null}

          <Button type="submit" variant="contained" size="large" disabled={loading} sx={{ mt: 1, py: 1.2, borderRadius: 3 }}>
            {loading ? <CircularProgress size={20} color="inherit" /> : buttonLabel}
          </Button>
        </Stack>

        <Typography variant="body2" sx={{ color: 'rgba(240,244,255,0.75)' }}>
          {footerText}{' '}
          <Link href={footerHref} style={{ color: '#7dd3fc', textDecoration: 'none', fontWeight: 600 }}>
            {footerLinkLabel}
          </Link>
        </Typography>
      </Stack>
    </Paper>
  );
}
