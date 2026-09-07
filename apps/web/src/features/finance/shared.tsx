import { useState, type ReactNode } from 'react'
import { Download, LoaderCircle } from 'lucide-react'
import { downloadFinance } from './api'
import './finance.css'

export const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, (v) => v.toUpperCase())
export function Status({ value }: { value: string }) { return <span className={`finance-status finance-status-${value}`}>{label(value)}</span> }
export function FinanceLayout({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return <div className="finance-page"><header className="finance-header"><div><p className="finance-eyebrow">WORKPLACE FINANCE</p><h1>{title}</h1>{subtitle && <p className="text-muted-foreground">{subtitle}</p>}</div><div className="finance-actions">{actions}</div></header>{children}</div>
}
export function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) { return <section className="finance-section"><header><h2>{title}</h2>{actions}</header>{children}</section> }
export function Field({ label: text, children }: { label: string; children: ReactNode }) { return <label className="finance-field"><span>{text}</span>{children}</label> }
export function Loading() { return <div role="status" className="finance-loading"><LoaderCircle className="animate-spin" /> Loading finance records…</div> }
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) { return <div role="alert" className="finance-error">{error instanceof Error ? error.message : 'Unable to load records.'}{retry && <button type="button" onClick={retry}>Retry</button>}</div> }
export function Pager({ page, totalPages, total, size, onPage, onSize }: { page: number; totalPages: number; total: number; size: number; onPage: (n: number) => void; onSize: (n: number) => void }) {
  return <nav aria-label="Results pages" className="finance-pager"><span>{total} records</span><label>Per page <select aria-label="Page size" value={size} onChange={(e) => onSize(Number(e.target.value))}>{[10,25,50,100].map((n) => <option key={n}>{n}</option>)}</select></label><div><button type="button" disabled={page <= 1} onClick={() => onPage(page-1)}>Previous</button><label className="sr-only" htmlFor="finance-page-number">Page</label><input id="finance-page-number" aria-label="Page" type="number" min={1} max={totalPages} value={page} onChange={(e) => { const n = Number(e.target.value); if(n >= 1 && n <= totalPages) onPage(n) }} /><span>of {totalPages}</span><button type="button" disabled={page >= totalPages} onClick={() => onPage(page+1)}>Next</button></div></nav>
}
export function ExportButton({ path, filename, children }: { path: string; filename: string; children: ReactNode }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState<Error>()
  return <div><button type="button" disabled={busy} onClick={async () => { setBusy(true); setError(undefined); try { await downloadFinance(path, filename) } catch(e) { setError(e instanceof Error ? e : new Error('Download failed')) } finally { setBusy(false) } }}><Download size={16} />{busy ? 'Preparing…' : children}</button>{error && <ErrorState error={error} />}</div>
}
