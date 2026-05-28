import './globals.css';
import AppThemeProvider from '../components/AppThemeProvider';
import BackendHealthPing from '../components/BackendHealthPing';

export const metadata = {
  title: 'PM RAG Studio',
  description: 'Product intelligence workspace'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AppThemeProvider>
          <BackendHealthPing />
          {children}
        </AppThemeProvider>
      </body>
    </html>
  );
}
