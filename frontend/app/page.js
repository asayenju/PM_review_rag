import Link from 'next/link';
import {
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Grid,
  Paper,
  Stack,
  Typography
} from '@mui/material';
import BoltRoundedIcon from '@mui/icons-material/BoltRounded';
import HubRoundedIcon from '@mui/icons-material/HubRounded';
import PlayCircleRoundedIcon from '@mui/icons-material/PlayCircleRounded';
import QueryStatsRoundedIcon from '@mui/icons-material/QueryStatsRounded';
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import SummarizeRoundedIcon from '@mui/icons-material/SummarizeRounded';

const highlights = [
  {
    title: 'Feature-gated RAG',
    description: 'Retrieval is constrained by org, role, and feature membership.',
    icon: <SecurityRoundedIcon sx={{ color: '#7dd3fc' }} />
  },
  {
    title: 'CRM to Context',
    description: 'Salesforce and HubSpot events are normalized into the RAG pipeline.',
    icon: <HubRoundedIcon sx={{ color: '#fbbf24' }} />
  },
  {
    title: 'Fast Product Decisions',
    description: 'PMs get answers tied to the exact feature they own.',
    icon: <BoltRoundedIcon sx={{ color: '#34d399' }} />
  }
];

const steps = [
  {
    step: '01',
    title: 'Connect data sources',
    description: 'CRM webhooks and ingestion jobs land in the backend pipeline.'
  },
  {
    step: '02',
    title: 'Attach features',
    description: 'Every document and chunk inherits organization and feature ownership.'
  },
  {
    step: '03',
    title: 'Query safely',
    description: 'PMs only retrieve answers from the features assigned to them.'
  }
];

const metrics = [
  { label: 'Tenant-safe retrieval', value: '100%' },
  { label: 'Feature ownership', value: 'Strict' },
  { label: 'Ingestion paths', value: 'CRM + Kafka' }
];

export default function HomePage() {
  return (
    <Box sx={{ minHeight: '100dvh', overflow: 'hidden', position: 'relative' }}>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(56rem 36rem at 10% 0%, rgba(56, 189, 248, 0.18), transparent 58%), radial-gradient(50rem 32rem at 92% 8%, rgba(245, 158, 11, 0.12), transparent 55%), radial-gradient(45rem 32rem at 50% 100%, rgba(99, 102, 241, 0.16), transparent 55%)'
        }}
      />

      <Container
        maxWidth={false}
        sx={{
          position: 'relative',
          mx: 'auto',
          maxWidth: '1520px',
          px: { xs: 2, sm: 3, md: 5, xl: 8 },
          py: { xs: 3, md: 5, xl: 7 }
        }}
      >
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{
            mb: { xs: 5, md: 8 },
            px: { xs: 0, md: 0.5 }
          }}
        >
          <Stack direction="row" spacing={1.2} alignItems="center">
            <Box
              sx={{
                width: 12,
                height: 12,
                borderRadius: 999,
                bgcolor: '#60a5fa',
                boxShadow: '0 0 24px rgba(96,165,250,0.7)'
              }}
            />
            <Typography sx={{ fontWeight: 800, letterSpacing: 1.2, color: '#93c5fd' }}>
              PM RAG STUDIO
            </Typography>
          </Stack>

          <Stack direction="row" spacing={1.2}>
            <Button component={Link} href="/login" variant="text">
              Log in
            </Button>
            <Button component={Link} href="/signup" variant="contained">
              Get Started
            </Button>
          </Stack>
        </Stack>

        <Grid container spacing={{ xs: 4, md: 6 }} alignItems="stretch">
          <Grid item xs={12} lg={7}>
            <Stack spacing={3} sx={{ pt: { xs: 0, lg: 4 } }}>
              <Chip
                label="Built for product organizations"
                sx={{
                  width: 'fit-content',
                  bgcolor: 'rgba(125,211,252,0.14)',
                  color: '#bae6fd',
                  fontWeight: 600
                }}
              />

              <Typography
                variant="h1"
                sx={{
                  fontSize: { xs: '2.5rem', sm: '3.5rem', md: '4.8rem' },
                  lineHeight: 0.98,
                  fontWeight: 800,
                  maxWidth: 900
                }}
              >
                AI Answers Grounded In
                <Box component="span" sx={{ color: '#7dd3fc' }}>
                  {' '}
                  Your Features
                </Box>
              </Typography>

              <Typography
                sx={{
                  maxWidth: 760,
                  color: 'rgba(226,232,240,0.82)',
                  fontSize: { xs: '1rem', md: '1.1rem' },
                  lineHeight: 1.8
                }}
              >
                Give each PM a dedicated intelligence layer. Retrieve only what they are authorized
                to access, with tenant-safe boundaries, live CRM ingestion, and product context that
                stays attached to the exact feature they own.
              </Typography>

              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.6}>
                <Button component={Link} href="/signup" variant="contained" size="large">
                  Create Workspace
                </Button>
                <Button component={Link} href="/login" variant="outlined" size="large">
                  Log in
                </Button>
              </Stack>

              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1.4}
                sx={{ pt: 1.5, flexWrap: 'wrap' }}
              >
                {metrics.map((metric) => (
                  <Paper
                    key={metric.label}
                    sx={{
                      px: 2,
                      py: 1.5,
                      minWidth: 180,
                      borderRadius: 3,
                      background: 'rgba(10,15,35,0.5)',
                      border: '1px solid rgba(148,163,184,0.16)'
                    }}
                  >
                    <Typography variant="caption" sx={{ color: 'rgba(203,213,225,0.72)' }}>
                      {metric.label}
                    </Typography>
                    <Typography sx={{ fontWeight: 700, mt: 0.5 }}>{metric.value}</Typography>
                  </Paper>
                ))}
              </Stack>
            </Stack>
          </Grid>

          <Grid item xs={12} lg={5}>
            <Stack spacing={2.5}>
              <Paper
                sx={{
                  p: { xs: 2.5, md: 3 },
                  borderRadius: 4,
                  background: 'linear-gradient(160deg, rgba(30,41,59,0.9), rgba(17,24,39,0.72))',
                  border: '1px solid rgba(148,163,184,0.22)',
                  minHeight: 240
                }}
              >
                <Stack spacing={2}>
                  <Stack direction="row" spacing={1.2} alignItems="center">
                    <QueryStatsRoundedIcon sx={{ color: '#a5b4fc' }} />
                    <Typography sx={{ fontWeight: 700 }}>Retrieval Signal Quality</Typography>
                  </Stack>
                  <Box sx={{ height: 12, bgcolor: 'rgba(148,163,184,0.25)', borderRadius: 999, overflow: 'hidden' }}>
                    <Box sx={{ width: '86%', height: '100%', bgcolor: '#60a5fa' }} />
                  </Box>
                  <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.82)', lineHeight: 1.8 }}>
                    Internal evaluation shows high-confidence answers when the PM only sees the
                    feature-scoped retrieval window.
                  </Typography>
                  <Divider sx={{ borderColor: 'rgba(148,163,184,0.16)' }} />
                  <Stack direction="row" spacing={2} justifyContent="space-between">
                    <Stack>
                      <Typography variant="caption" sx={{ color: 'rgba(203,213,225,0.72)' }}>
                        Feature scope
                      </Typography>
                      <Typography sx={{ fontWeight: 700 }}>Assigned only</Typography>
                    </Stack>
                    <Stack>
                      <Typography variant="caption" sx={{ color: 'rgba(203,213,225,0.72)' }}>
                        Data model
                      </Typography>
                      <Typography sx={{ fontWeight: 700 }}>Supabase + VectorDB</Typography>
                    </Stack>
                  </Stack>
                </Stack>
              </Paper>

              <Paper
                sx={{
                  p: { xs: 2.5, md: 3 },
                  borderRadius: 4,
                  background: 'linear-gradient(160deg, rgba(17,24,39,0.86), rgba(2,6,23,0.7))',
                  border: '1px solid rgba(125,211,252,0.2)'
                }}
              >
                <Stack spacing={2}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <PlayCircleRoundedIcon sx={{ color: '#7dd3fc' }} />
                    <Typography sx={{ fontWeight: 800 }}>Try the demo</Typography>
                  </Stack>
                  <Typography variant="body2" sx={{ color: 'rgba(203,213,225,0.86)', lineHeight: 1.8 }}>
                    A live demo page will later show how feature-scoped answers behave for PMs across
                    orgs and feature sets.
                  </Typography>
                  <Button component={Link} href="/demo" variant="contained" fullWidth>
                    Try Demo
                  </Button>
                </Stack>
              </Paper>
            </Stack>
          </Grid>
        </Grid>

        <Grid container spacing={2.5} sx={{ mt: { xs: 6, md: 9 } }}>
          {highlights.map((card) => (
            <Grid item xs={12} md={4} key={card.title}>
              <Paper
                sx={{
                  p: 3,
                  borderRadius: 3,
                  height: '100%',
                  background: 'rgba(10,15,35,0.42)',
                  border: '1px solid rgba(148,163,184,0.16)'
                }}
              >
                <Stack spacing={1.4}>
                  {card.icon}
                  <Typography sx={{ fontWeight: 700 }}>{card.title}</Typography>
                  <Typography variant="body2" sx={{ color: 'rgba(203,213,225,0.86)', lineHeight: 1.8 }}>
                    {card.description}
                  </Typography>
                </Stack>
              </Paper>
            </Grid>
          ))}
        </Grid>

        <Paper
          sx={{
            mt: { xs: 6, md: 9 },
            p: { xs: 3, md: 4 },
            borderRadius: 4,
            background: 'rgba(2, 6, 23, 0.6)',
            border: '1px solid rgba(125,211,252,0.2)'
          }}
        >
          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={7}>
              <Typography variant="h4" sx={{ fontWeight: 800 }}>
                PM workflow that scales with the org
              </Typography>
              <Typography sx={{ mt: 1.5, color: 'rgba(226,232,240,0.82)', lineHeight: 1.8 }}>
                Start with authentication, attach features to PMs, and let every answer inherit the
                right tenant boundaries automatically.
              </Typography>
            </Grid>
            <Grid item xs={12} md={5}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="flex-end">
                <Button component={Link} href="/signup" size="large" variant="contained">
                  Start Free
                </Button>
                <Button component={Link} href="/login" size="large" variant="outlined">
                  Go to Login
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </Paper>

        <Grid container spacing={2.5} sx={{ mt: { xs: 6, md: 8 } }}>
          {steps.map((step) => (
            <Grid item xs={12} md={4} key={step.step}>
              <Paper
                sx={{
                  p: 3,
                  borderRadius: 3,
                  background: 'rgba(10,15,35,0.38)',
                  border: '1px solid rgba(148,163,184,0.14)',
                  minHeight: 180
                }}
              >
                <Stack spacing={1.5}>
                  <Typography sx={{ color: '#7dd3fc', fontWeight: 800 }}>{step.step}</Typography>
                  <Typography sx={{ fontWeight: 700 }}>{step.title}</Typography>
                  <Typography variant="body2" sx={{ color: 'rgba(203,213,225,0.86)', lineHeight: 1.8 }}>
                    {step.description}
                  </Typography>
                </Stack>
              </Paper>
            </Grid>
          ))}
        </Grid>

        <Box sx={{ height: { xs: 40, md: 80 } }} />
      </Container>
    </Box>
  );
}
