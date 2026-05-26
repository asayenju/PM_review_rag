'use client';

import { createTheme, CssBaseline, ThemeProvider } from '@mui/material';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#60a5fa' },
    secondary: { main: '#f59e0b' },
    background: { default: '#030712', paper: 'rgba(17, 24, 39, 0.7)' },
    text: { primary: '#eef2ff', secondary: '#cbd5e1' }
  },
  typography: {
    fontFamily: '"Space Grotesk", "IBM Plex Sans", sans-serif',
    h4: { letterSpacing: '-0.02em' }
  },
  shape: { borderRadius: 14 },
  components: {
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 12,
            background: 'rgba(15, 23, 42, 0.55)'
          }
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 700
        }
      }
    }
  }
});

export default function AppThemeProvider({ children }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
