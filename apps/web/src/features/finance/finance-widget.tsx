import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useAuth } from '@/features/auth/auth-store'
import { financeApi } from './api'

export function FinanceWidget() {
  const {user}=useAuth()
  const allowed=!!user?.permissions.includes('vouchers.view_own')
  const summary=useQuery({queryKey:['voucher-summary'],queryFn:financeApi.summary,enabled:allowed})
  if(!allowed) return null
  const count=(status:string)=>summary.data?.groups.filter(g=>g.status===status).reduce((sum,g)=>sum+g.count,0)??0
  return <section className="rounded-2xl border border-border bg-card p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Expense requests</h2><Link to="/vouchers" className="text-sm text-primary">Open vouchers →</Link></div>{summary.isLoading?<p role="status" className="mt-3 text-sm">Loading requests…</p>:summary.error?<button className="mt-3 text-sm text-primary" onClick={()=>void summary.refetch()}>Requests unavailable · Retry</button>:<dl className="mt-4 grid grid-cols-3 gap-3 text-sm">{[['In review','submitted'],['Awaiting payment','approved'],['Partly paid','partially_disbursed']].map(([text,status])=><div key={status}><dt className="text-xs text-muted-foreground">{text}</dt><dd className="mt-1 text-xl font-semibold">{count(status!)}</dd></div>)}</dl>}</section>
}
