import './globals.css';
import AppThemeProvider from '../components/AppThemeProvider';

export const metadata = {
  title: 'PM RAG Studio',
  description: 'Product intelligence workspace'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AppThemeProvider>{children}</AppThemeProvider>
      </body>
    </html>
  );
}
