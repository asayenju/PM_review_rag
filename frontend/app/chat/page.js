'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import {
  clearAuthSession,
  createConversation,
  getAssignedFeatures,
  getAuthToken,
  getConversationMessages,
  getConversations,
  sendConversationMessage
} from '../../lib/api';

export default function ChatPage() {
  const router = useRouter();
  const messagesEndRef = useRef(null);
  const [features, setFeatures] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [featurePickerOpen, setFeaturePickerOpen] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getAuthToken()) {
      router.replace('/login');
      return;
    }
    loadInitialData();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  async function loadInitialData() {
    setLoading(true);
    setError('');
    try {
      const [featureData, conversationData] = await Promise.all([
        getAssignedFeatures(),
        getConversations()
      ]);
      setFeatures(featureData);
      setConversations(conversationData);
      if (conversationData.length > 0) {
        await openConversation(conversationData[0]);
      }
    } catch (err) {
      setError(err.message || 'Unable to load chat workspace.');
    } finally {
      setLoading(false);
    }
  }

  async function openConversation(conversation) {
    setActiveConversation(conversation);
    setError('');
    try {
      const data = await getConversationMessages(conversation.id);
      setMessages(data);
    } catch (err) {
      setError(err.message || 'Unable to load conversation messages.');
    }
  }

  async function startFeatureConversation(feature) {
    setError('');
    try {
      const conversation = await createConversation(
        feature.org_id,
        feature.feature_id,
        `${feature.name} chat`
      );
      const enrichedConversation = { ...conversation, feature_name: feature.name };
      setConversations((current) => [enrichedConversation, ...current]);
      setFeaturePickerOpen(false);
      await openConversation(enrichedConversation);
    } catch (err) {
      setError(err.message || 'Unable to create conversation.');
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const content = messageText.trim();
    if (!content || !activeConversation || sending) {
      return;
    }

    setMessageText('');
    setSending(true);
    setError('');
    const optimisticMessage = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString()
    };
    setMessages((current) => [...current, optimisticMessage]);

    try {
      const response = await sendConversationMessage(activeConversation.id, content);
      setMessages((current) => [
        ...current.filter((message) => message.id !== optimisticMessage.id),
        response.user_message,
        response.assistant_message
      ]);
      setConversations((current) => [
        activeConversation,
        ...current.filter((conversation) => conversation.id !== activeConversation.id)
      ]);
    } catch (err) {
      setError(err.message || 'Unable to send message.');
      setMessages((current) => current.filter((message) => message.id !== optimisticMessage.id));
      setMessageText(content);
    } finally {
      setSending(false);
    }
  }

  function logout() {
    clearAuthSession();
    router.replace('/login');
  }

  return (
    <Box sx={{ height: '100dvh', overflow: 'hidden', bgcolor: '#030712' }}>
      <Stack direction="row" sx={{ height: '100%' }}>
        <Paper
          sx={{
            width: { xs: 280, md: 340 },
            display: { xs: activeConversation ? 'none' : 'flex', md: 'flex' },
            flexDirection: 'column',
            borderRadius: 0,
            borderRight: '1px solid rgba(148,163,184,0.16)',
            background: 'rgba(10,15,35,0.78)'
          }}
        >
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ p: 2 }}>
            <Typography sx={{ fontWeight: 800 }}>PM RAG Studio</Typography>
            <Stack direction="row" spacing={0.5}>
              <Tooltip title="New feature chat">
                <IconButton onClick={() => setFeaturePickerOpen(true)}>
                  <AddRoundedIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Log out">
                <IconButton onClick={logout}>
                  <LogoutRoundedIcon />
                </IconButton>
              </Tooltip>
            </Stack>
          </Stack>
          <Divider sx={{ borderColor: 'rgba(148,163,184,0.14)' }} />
          <Box sx={{ overflowY: 'auto', flex: 1, p: 1 }}>
            {conversations.length === 0 ? (
              <Typography sx={{ color: 'rgba(226,232,240,0.7)', p: 2, lineHeight: 1.7 }}>
                Add an assigned feature to start a private PM conversation.
              </Typography>
            ) : (
              conversations.map((conversation) => (
                <ListItemButton
                  key={conversation.id}
                  selected={activeConversation?.id === conversation.id}
                  onClick={() => openConversation(conversation)}
                  sx={{ borderRadius: 2, mb: 0.6 }}
                >
                  <ListItemText
                    primary={conversation.title || 'Untitled chat'}
                    secondary={conversation.feature_name || 'Feature chat'}
                    primaryTypographyProps={{ fontWeight: 700, noWrap: true }}
                    secondaryTypographyProps={{ noWrap: true }}
                  />
                </ListItemButton>
              ))
            )}
          </Box>
        </Paper>

        <Box sx={{ flex: 1, minWidth: 0, display: 'grid', gridTemplateRows: 'auto 1fr auto' }}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            sx={{
              p: { xs: 2, md: 2.5 },
              borderBottom: '1px solid rgba(148,163,184,0.16)',
              background: 'rgba(10,15,35,0.9)'
            }}
          >
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 800 }}>
                {activeConversation?.title || 'Private PM Chat'}
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.72)' }}>
                {activeConversation?.feature_name || 'Choose an assigned feature to begin.'}
              </Typography>
            </Box>
            <Button startIcon={<AddRoundedIcon />} variant="contained" onClick={() => setFeaturePickerOpen(true)}>
              Add Feature
            </Button>
          </Stack>

          <Box sx={{ minHeight: 0, overflowY: 'auto', p: { xs: 2, md: 3 } }}>
            {loading ? (
              <Stack alignItems="center" justifyContent="center" sx={{ height: '100%' }}>
                <CircularProgress />
              </Stack>
            ) : (
              <Stack spacing={2}>
                {error && <Alert severity="error">{error}</Alert>}
                {!activeConversation && (
                  <Paper sx={{ p: 3, borderRadius: 3, background: 'rgba(15,23,42,0.72)' }}>
                    <Typography sx={{ fontWeight: 800, mb: 1 }}>Start with a feature</Typography>
                    <Typography sx={{ color: 'rgba(226,232,240,0.76)', lineHeight: 1.7 }}>
                      Use Add Feature to create a conversation scoped to one of your assigned features.
                    </Typography>
                  </Paper>
                )}
                {messages.map((message) => {
                  const isUser = message.role === 'user';
                  return (
                    <Box key={message.id} sx={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
                      <Paper
                        sx={{
                          maxWidth: { xs: '92%', md: '72%' },
                          px: 2,
                          py: 1.5,
                          borderRadius: 3,
                          background: isUser ? 'rgba(96,165,250,0.2)' : 'rgba(15,23,42,0.76)',
                          border: '1px solid rgba(148,163,184,0.16)'
                        }}
                      >
                        <Chip
                          size="small"
                          label={isUser ? 'You' : 'Assistant'}
                          sx={{ mb: 1, bgcolor: isUser ? 'rgba(96,165,250,0.18)' : 'rgba(245,158,11,0.16)' }}
                        />
                        <Typography sx={{ lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{message.content}</Typography>
                      </Paper>
                    </Box>
                  );
                })}
                {sending && <Typography sx={{ color: 'rgba(226,232,240,0.7)' }}>Assistant is reading reviews...</Typography>}
                <Box ref={messagesEndRef} />
              </Stack>
            )}
          </Box>

          <Box component="form" onSubmit={sendMessage} sx={{ p: 2, borderTop: '1px solid rgba(148,163,184,0.16)' }}>
            <Stack direction="row" spacing={1.2} alignItems="flex-end">
              <TextField
                fullWidth
                multiline
                maxRows={4}
                disabled={!activeConversation || sending}
                value={messageText}
                onChange={(event) => setMessageText(event.target.value)}
                placeholder={activeConversation ? 'Ask about this feature...' : 'Add a feature to start chatting'}
              />
              <IconButton
                type="submit"
                disabled={!messageText.trim() || !activeConversation || sending}
                sx={{
                  width: 52,
                  height: 52,
                  bgcolor: '#60a5fa',
                  color: '#020617',
                  '&:hover': { bgcolor: '#93c5fd' },
                  '&.Mui-disabled': { bgcolor: 'rgba(148,163,184,0.14)' }
                }}
              >
                <SendRoundedIcon />
              </IconButton>
            </Stack>
          </Box>
        </Box>
      </Stack>

      <Dialog open={featurePickerOpen} onClose={() => setFeaturePickerOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Choose an assigned feature</DialogTitle>
        <DialogContent>
          <List>
            {features.map((feature) => (
              <ListItemButton key={feature.feature_id} onClick={() => startFeatureConversation(feature)}>
                <ListItemText primary={feature.name} secondary={feature.slug || feature.feature_id} />
              </ListItemButton>
            ))}
            {features.length === 0 && (
              <Typography sx={{ color: 'rgba(226,232,240,0.72)', p: 2 }}>
                No assigned features were found for this PM.
              </Typography>
            )}
          </List>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
