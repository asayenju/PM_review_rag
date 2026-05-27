'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { publicQuery } from '../../lib/api';

const QUERY_LIMIT = 5;
const STORAGE_KEY = 'publicReviewQueryCount';

const examplePrompts = [
  'What are customers complaining about?',
  'What should we improve first?',
  'What do users like about checkout?',
  'Summarize the public reviews.'
];

const initialMessages = [
  {
    role: 'assistant',
    content:
      'Ask me about the public review set. I can summarize customer feedback, pain points, and improvement themes.'
  }
];

export default function DemoPage() {
  const [messages, setMessages] = useState(initialMessages);
  const [question, setQuestion] = useState('');
  const [queryCount, setQueryCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  const remainingQueries = Math.max(QUERY_LIMIT - queryCount, 0);
  const limitReached = remainingQueries === 0;
  const canSubmit = question.trim().length > 0 && !loading && !limitReached;

  const helperText = useMemo(() => {
    if (limitReached) {
      return 'You have used all 5 public demo questions in this browser.';
    }
    return `${remainingQueries} public ${remainingQueries === 1 ? 'question' : 'questions'} remaining`;
  }, [limitReached, remainingQueries]);

  useEffect(() => {
    const storedCount = Number(window.localStorage.getItem(STORAGE_KEY) || '0');
    if (Number.isFinite(storedCount)) {
      setQueryCount(Math.min(Math.max(storedCount, 0), QUERY_LIMIT));
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading]);

  async function sendQuestion(prompt) {
    const trimmedQuestion = (prompt ?? question).trim();
    if (!trimmedQuestion || loading || limitReached) {
      return;
    }

    setQuestion('');
    setError('');
    setLoading(true);
    setMessages((current) => [...current, { role: 'user', content: trimmedQuestion }]);

    try {
      const data = await publicQuery(trimmedQuestion);
      setMessages((current) => [...current, { role: 'assistant', content: data.answer }]);
      setQueryCount((current) => {
        const nextCount = Math.min(current + 1, QUERY_LIMIT);
        window.localStorage.setItem(STORAGE_KEY, String(nextCount));
        return nextCount;
      });
    } catch (err) {
      setError(err.message || 'The public review chat is unavailable right now.');
      setMessages((current) => current.slice(0, -1));
      setQuestion(trimmedQuestion);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendQuestion();
  }

  return (
    <Box sx={{ height: '100dvh', position: 'relative', overflow: 'hidden' }}>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(44rem 30rem at 12% 0%, rgba(96,165,250,0.2), transparent 58%), radial-gradient(38rem 28rem at 88% 8%, rgba(245,158,11,0.12), transparent 55%)'
        }}
      />

      <Container
        maxWidth={false}
        sx={{
          position: 'relative',
          maxWidth: '1180px',
          height: '100dvh',
          mx: 'auto',
          px: { xs: 2, md: 4 },
          py: { xs: 1.5, md: 3 },
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5, flexShrink: 0 }}>
          <Button component={Link} href="/" startIcon={<ArrowBackRoundedIcon />} variant="text">
            Home
          </Button>
          <Chip
            icon={<AutoAwesomeRoundedIcon />}
            label={helperText}
            sx={{
              bgcolor: limitReached ? 'rgba(248,113,113,0.16)' : 'rgba(96,165,250,0.16)',
              color: limitReached ? '#fecaca' : '#bfdbfe',
              fontWeight: 700
            }}
          />
        </Stack>

        <Paper
          sx={{
            flex: 1,
            minHeight: 0,
            display: 'grid',
            gridTemplateRows: 'auto 1fr auto',
            borderRadius: 4,
            overflow: 'hidden',
            background: 'rgba(10,15,35,0.72)',
            border: '1px solid rgba(148,163,184,0.18)'
          }}
        >
          <Box
            sx={{
              p: { xs: 2, md: 2.5 },
              borderBottom: '1px solid rgba(148,163,184,0.14)',
              bgcolor: 'rgba(10,15,35,0.9)',
              backdropFilter: 'blur(16px)',
              zIndex: 2
            }}
          >
            <Stack spacing={1}>
              <Typography variant="h4" sx={{ fontWeight: 800, fontSize: { xs: '1.5rem', md: '2rem' } }}>
                Public Review Chat
              </Typography>
              <Typography sx={{ color: 'rgba(226,232,240,0.78)', lineHeight: 1.7 }}>
                Ask questions about the public review dataset. This chat only searches reviews made
                available for everyone.
              </Typography>
            </Stack>
          </Box>

          <Box sx={{ minHeight: 0, overflowY: 'auto', p: { xs: 2, md: 3 } }}>
            <Stack spacing={2}>
              {messages.map((message, index) => {
                const isUser = message.role === 'user';
                return (
                  <Box
                    key={`${message.role}-${index}`}
                    sx={{
                      display: 'flex',
                      justifyContent: isUser ? 'flex-end' : 'flex-start'
                    }}
                  >
                    <Paper
                      sx={{
                        maxWidth: { xs: '92%', md: '74%' },
                        px: 2,
                        py: 1.5,
                        borderRadius: 3,
                        background: isUser ? 'rgba(96,165,250,0.2)' : 'rgba(15,23,42,0.74)',
                        border: isUser
                          ? '1px solid rgba(147,197,253,0.28)'
                          : '1px solid rgba(148,163,184,0.16)'
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{ color: isUser ? '#bfdbfe' : '#fcd34d', fontWeight: 800 }}
                      >
                        {isUser ? 'You' : 'Assistant'}
                      </Typography>
                      <Typography sx={{ mt: 0.6, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                        {message.content}
                      </Typography>
                    </Paper>
                  </Box>
                );
              })}

              {loading && (
                <Paper
                  sx={{
                    maxWidth: { xs: '92%', md: '50%' },
                    px: 2,
                    py: 1.5,
                    borderRadius: 3,
                    background: 'rgba(15,23,42,0.74)',
                    border: '1px solid rgba(148,163,184,0.16)'
                  }}
                >
                  <Typography variant="caption" sx={{ color: '#fcd34d', fontWeight: 800 }}>
                    Assistant
                  </Typography>
                  <Typography sx={{ mt: 0.6, color: 'rgba(226,232,240,0.78)' }}>
                    Reading public reviews...
                  </Typography>
                  <LinearProgress sx={{ mt: 1.5, borderRadius: 999 }} />
                </Paper>
              )}
              <Box ref={messagesEndRef} />
            </Stack>
          </Box>

          <Box
            sx={{
              p: { xs: 1.5, md: 2 },
              borderTop: '1px solid rgba(148,163,184,0.14)',
              bgcolor: 'rgba(10,15,35,0.92)',
              backdropFilter: 'blur(16px)',
              zIndex: 2
            }}
          >
            <Stack spacing={1.5}>
              {error && <Alert severity="error">{error}</Alert>}
              {limitReached && (
                <Alert severity="info">Public chat is limited to 5 questions in this browser.</Alert>
              )}

              <Stack
                direction="row"
                spacing={1}
                useFlexGap
                flexWrap="wrap"
                sx={{ display: { xs: messages.length > 1 ? 'none' : 'flex', md: 'flex' } }}
              >
                {examplePrompts.map((prompt) => (
                  <Button
                    key={prompt}
                    variant="outlined"
                    size="small"
                    disabled={loading || limitReached}
                    onClick={() => sendQuestion(prompt)}
                  >
                    {prompt}
                  </Button>
                ))}
              </Stack>

              <Box component="form" onSubmit={handleSubmit}>
                <Stack direction="row" spacing={1.2} alignItems="flex-end">
                  <TextField
                    fullWidth
                    multiline
                    maxRows={4}
                    value={question}
                    disabled={limitReached}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ask about public customer reviews..."
                    helperText={helperText}
                  />
                  <Tooltip title="Send question">
                    <span>
                      <IconButton
                        type="submit"
                        disabled={!canSubmit}
                        sx={{
                          width: 52,
                          height: 52,
                          bgcolor: '#60a5fa',
                          color: '#020617',
                          '&:hover': { bgcolor: '#93c5fd' },
                          '&.Mui-disabled': {
                            bgcolor: 'rgba(148,163,184,0.14)',
                            color: 'rgba(203,213,225,0.42)'
                          }
                        }}
                      >
                        <SendRoundedIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Stack>
              </Box>
            </Stack>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
