import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="text-xl font-bold text-slate-900">Tally Co-pilot</div>
        <div className="flex gap-3">
          <Link to="/login" className="rounded px-4 py-2 text-sm text-slate-600 hover:text-slate-900">Sign in</Link>
          <Link to="/signup" className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700">Get started free</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-6 py-20 text-center">
        <div className="mb-4 inline-block rounded-full bg-emerald-50 px-4 py-1 text-sm font-medium text-emerald-700">
          Built for Indian businesses on Tally
        </div>
        <h1 className="mb-6 text-5xl font-bold leading-tight text-slate-900">
          Send an invoice.<br />
          <span className="text-emerald-600">Tally does the rest.</span>
        </h1>
        <p className="mx-auto mb-8 max-w-2xl text-lg text-slate-500">
          Snap a photo of any GST invoice and WhatsApp it to us. Our AI extracts
          every field and posts it straight to your Tally — with confirmation on
          WhatsApp. No manual entry. No errors.
        </p>
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <Link to="/signup" className="rounded-lg bg-slate-900 px-6 py-3 text-base font-medium text-white hover:bg-slate-700">
            Start for free — no credit card
          </Link>
          <a href="#how" className="rounded-lg border px-6 py-3 text-base font-medium text-slate-600 hover:bg-slate-50">
            See how it works
          </a>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="bg-slate-50 py-20">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mb-12 text-center text-3xl font-bold text-slate-900">How it works</h2>
          <div className="grid gap-8 md:grid-cols-3">
            {[
              { step: '1', title: 'Send the invoice', body: 'WhatsApp any GST invoice — photo, scan, or PDF — to your dedicated number.' },
              { step: '2', title: 'AI extracts the data', body: 'Our AI reads supplier name, GSTIN, line items, HSN codes, and all tax amounts in seconds.' },
              { step: '3', title: 'Posted to Tally', body: 'A Purchase voucher appears in your Tally instantly. You get a WhatsApp confirmation with the voucher number.' },
            ].map(({ step, title, body }) => (
              <div key={step} className="rounded-xl bg-white p-6 shadow-sm">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-lg font-bold text-white">{step}</div>
                <h3 className="mb-2 text-lg font-semibold text-slate-900">{title}</h3>
                <p className="text-slate-500">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mb-12 text-center text-3xl font-bold text-slate-900">Everything you need</h2>
          <div className="grid gap-6 md:grid-cols-2">
            {[
              ['GST-aware extraction', 'Reads CGST, SGST, IGST, HSN/SAC codes, reverse charge — everything your accountant needs.'],
              ['Works with photos', 'Blurry phone photos, PDFs, scans — Gemini Vision handles them all.'],
              ['Dashboard & history', 'See every invoice ever processed, search by supplier, export to CSV.'],
              ['Manual review mode', 'Review AI extraction before it posts to Tally. Turn it off once you trust it.'],
              ['Infrastructure control', 'Swap LLM providers, configure email, connect real WhatsApp — all from a UI.'],
              ['Your data, your Tally', 'The connector runs on your machine. Invoice data never leaves your network after extraction.'],
            ].map(([title, body]) => (
              <div key={title} className="flex gap-4 rounded-lg border p-4">
                <span className="mt-0.5 text-emerald-500">✓</span>
                <div>
                  <div className="font-medium text-slate-900">{title}</div>
                  <div className="text-sm text-slate-500">{body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-slate-900 py-16 text-center text-white">
        <h2 className="mb-4 text-3xl font-bold">Stop typing invoices into Tally.</h2>
        <p className="mb-8 text-slate-400">Get started in 5 minutes. Free during early access.</p>
        <Link to="/signup" className="rounded-lg bg-white px-6 py-3 text-base font-semibold text-slate-900 hover:bg-slate-100">
          Create your account
        </Link>
      </section>

      {/* Footer */}
      <footer className="py-8 text-center text-sm text-slate-400">
        © {new Date().getFullYear()} Tally Co-pilot. Built for Indian businesses.
      </footer>
    </div>
  )
}
