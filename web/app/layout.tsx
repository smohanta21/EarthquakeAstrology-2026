import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import Link from 'next/link'
import './globals.css'

const inter = Inter({ subsets: ['latin'], display: 'swap' })

export const metadata: Metadata = {
  title: 'Earthquake Astrology 2026',
  description: '2026 earthquake risk predictions based on astrological planetary patterns',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={inter.className}>
      <body>
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm text-amber-900">
          <strong>Disclaimer:</strong> This is an experimental astrological model. Earthquakes cannot be reliably predicted. This tool is for research purposes only and should not be used for safety decisions.
        </div>
        <nav className="flex items-center justify-between px-6 py-4 border-b">
          <Link href="/"><h1 className="font-semibold text-lg">Earthquake Astrology 2026</h1></Link>
          <Link href="/methodology" className="text-sm text-blue-600 hover:underline">Methodology</Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  )
}
