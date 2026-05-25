export const metadata = {
  title: 'Startup Frontend',
  description: 'Next.js frontend'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'Arial, sans-serif' }}>{children}</body>
    </html>
  );
}
