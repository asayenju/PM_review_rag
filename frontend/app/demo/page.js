import Link from 'next/link';
import { Box, Button, Container, Paper, Stack, Typography } from '@mui/material';

export default function DemoPage() {
  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', px: 2 }}>
      <Container maxWidth="sm">
        <Paper
          sx={{
            p: { xs: 3, md: 4 },
            borderRadius: 4,
            background: 'rgba(10,15,35,0.72)',
            border: '1px solid rgba(148,163,184,0.16)'
          }}
        >
          <Stack spacing={2.2} alignItems="center" textAlign="center">
            <Typography variant="h4" sx={{ fontWeight: 800 }}>
              Demo Page
            </Typography>
            <Typography sx={{ color: 'rgba(226,232,240,0.82)', lineHeight: 1.8 }}>
              This is a placeholder for the future product demo experience.
            </Typography>
            <Button component={Link} href="/" variant="contained">
              Back to Home
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
