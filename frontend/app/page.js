import Link from 'next/link';
import { Box, Button, Stack, Typography } from '@mui/material';

export default function HomePage() {
  return (
    <main className="auth-shell">
      <Box sx={{ textAlign: 'center', maxWidth: 680 }}>
        <Typography variant="overline" sx={{ letterSpacing: 2, color: '#93c5fd' }}>
          PM RAG STUDIO
        </Typography>
        <Typography variant="h2" sx={{ mt: 1, fontWeight: 700 }}>
          Feature-Scoped AI Answers for Product Teams
        </Typography>
        <Typography sx={{ mt: 2, color: 'rgba(226,232,240,0.82)' }}>
          Sign in to query only the features you own, with strict backend access controls.
        </Typography>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 4, justifyContent: 'center' }}>
          <Button component={Link} href="/login" variant="contained" size="large">
            Log in
          </Button>
          <Button component={Link} href="/signup" variant="outlined" size="large">
            Create account
          </Button>
        </Stack>
      </Box>
    </main>
  );
}
