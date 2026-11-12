import { useEffect, useState } from 'react'
import * as api from './api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const TABS = ['Overview','Model Center','Task Manager','Token Analytics','Recovery Center','Settings']

export default function App() {
  const [tab, setTab] = useState('Overview')
  const [overview, setOverview] = useState<any>(null)
  const [providers, setProviders] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [tasks, setTasks] = useState<any[]>([])
  const [usage, setUsage] = useState<any>(null)
  const [budget, setBudget] = useState<any>(null)
  const [approvals, setApprovals] = useState<any[]>([])

  const refresh = async () => {
    try {
      const [o, p, m, t, u, b, a] = await Promise.all([
        api.getOverview(), api.getProviders(), api.getModels(), api.getTasks(),
        api.getUsage(), api.getBudget(), api.getApprovals()
      ])
      setOverview(o); setProviders(p); setModels(m); setTasks(t); setUsage(u); setBudget(b); setApprovals(a)
    } catch (e) { console.error(e) }
  }
  useEffect(() => { refresh(); const i = setInterval(refresh, 8000); return () => clearInterval(i) }, [])

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 border-r border-gray-800 p-4 flex flex-col gap-2">
        <h1 className="text-xl font-bold text-cyan-400 mb-4">D-ORCHESTRATOR</h1>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`text-left px-3 py-2 rounded ${tab===t ? 'bg-cyan-600 text-white' : 'hover:bg-gray-800'}`}>{t}</button>
        ))}
        <div className="mt-auto text-xs text-gray-500">Local-first AI workforce manager</div>
      </aside>
      <main className="flex-1 p-6 overflow-auto">
        {tab === 'Overview' && <Overview overview={overview} providers={providers} models={models} tasks={tasks} />}
        {tab === 'Model Center' && <ModelCenter providers={providers} models={models} refresh={refresh} />}
        {tab === 'Task Manager' && <TaskManager tasks={tasks} refresh={refresh} />}
        {tab === 'Token Analytics' && <TokenAnalytics usage={usage} budget={budget} />}
        {tab === 'Recovery Center' && <RecoveryCenter tasks={tasks} approvals={approvals} refresh={refresh} />}
        {tab === 'Settings' && <Settings budget={budget} refresh={refresh} />}
      </main>
    </div>
  )
}

function Card({title, children}: any) {
  return <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
    <h3 className="text-sm font-semibold text-gray-300 mb-2">{title}</h3>
    {children}
  </div>
}

function Overview({overview, providers, tasks}: any) {
  if (!overview) return <div>Loading...</div>
  const t = overview.tasks
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Overview</h2>
      <div className="grid grid-cols-4 gap-4 mb-4">
        <Stat label="Total Tasks" value={t.total} />
        <Stat label="Completed" value={t.completed} />
        <Stat label="Failed" value={t.failed} />
        <Stat label="Available Models" value={overview.models.available} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card title="Providers">
          <table className="w-full text-sm">
            <thead><tr className="text-gray-400"><th className="text-left">Name</th><th>Kind</th><th>Health</th></tr></thead>
            <tbody>{providers.map((p:any)=>(
              <tr key={p.id} className="border-t border-gray-800"><td>{p.name}</td><td>{p.kind}</td><td className={p.health==='healthy'?'text-green-400':'text-red-400'}>{p.health}</td></tr>
            ))}</tbody>
          </table>
        </Card>
        <Card title="Recent Tasks">
          <table className="w-full text-sm">
            <thead><tr className="text-gray-400"><th className="text-left">Title</th><th>Status</th><th>Model</th></tr></thead>
            <tbody>{tasks.slice(0,8).map((t:any)=>(
              <tr key={t.id} className="border-t border-gray-800"><td className="truncate max-w-xs">{t.title}</td><td>{t.status}</td><td className="text-xs">{t.current_model}</td></tr>
            ))}</tbody>
          </table>
        </Card>
      </div>
      <Card title="Token Savings (estimated)">
        <div className="text-sm text-gray-300">Total input: {overview.usage.total_input_tokens} | output: {overview.usage.total_output_tokens} | cost: ${overview.usage.total_cost}</div>
      </Card>
    </div>
  )
}
function Stat({label, value}: any) {
  return <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
    <div className="text-2xl font-bold text-cyan-400">{value}</div>
    <div className="text-xs text-gray-400">{label}</div>
  </div>
}

function ModelCenter({providers, models, refresh}: any) {
  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold">Model Center</h2>
        <button onClick={async()=>{await api.refreshAll(); refresh()}} className="bg-cyan-600 px-3 py-1 rounded text-sm">Refresh All</button>
      </div>
      <Card title="Providers">
        <table className="w-full text-sm">
          <thead><tr className="text-gray-400"><th className="text-left">Provider</th><th>Kind</th><th>Health</th><th>Auth</th></tr></thead>
          <tbody>{providers.map((p:any)=>(
            <tr key={p.id} className="border-t border-gray-800"><td>{p.name}</td><td>{p.kind}</td><td className={p.health==='healthy'?'text-green-400':'text-red-400'}>{p.health}</td><td>{p.auth_type}</td></tr>
          ))}</tbody>
        </table>
      </Card>
      <Card title={`Models (${models.length})`}>
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-gray-400"><th className="text-left">Model</th><th>Provider</th><th>Cat</th><th>Ctx</th><th>Local</th><th>Cost in</th><th>Health</th><th>Avail</th></tr></thead>
            <tbody>{models.map((m:any)=>(
              <tr key={m.id} className="border-t border-gray-800">
                <td className="text-xs">{m.model_id}</td><td>{m.provider_name}</td><td>{m.category}</td><td>{m.context_window}</td>
                <td>{m.is_local?'Y':'N'}</td><td>{m.estimated_cost_input}</td>
                <td className={m.health==='healthy'?'text-green-400':'text-gray-400'}>{m.health}</td>
                <td>{m.available?'Y':'N'}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function TaskManager({tasks, refresh}: any) {
  const [title, setTitle] = useState('')
  const [objective, setObjective] = useState('')
  const [projectDir, setProjectDir] = useState('')
  const [mode, setMode] = useState('balanced')
  const [autoRoute, setAutoRoute] = useState(true)
  const [running, setRunning] = useState<string | null>(null)

  const create = async () => {
    if (!title || !objective) return
    await api.createTask({title, objective, project_dir: projectDir || null, optimization_mode: mode, auto_route: autoRoute})
    setTitle(''); setObjective(''); setProjectDir('')
    refresh()
  }
  const run = async (id: string, sync: boolean) => {
    setRunning(id)
    try {
      if (sync) await api.runTaskSync(id); else await api.runTask(id)
    } catch(e){ console.error(e) }
    setRunning(null)
    refresh()
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Task Manager</h2>
      <Card title="Create Task">
        <div className="grid gap-2">
          <input className="bg-gray-800 p-2 rounded" placeholder="Title" value={title} onChange={e=>setTitle(e.target.value)} />
          <textarea className="bg-gray-800 p-2 rounded" placeholder="Objective / natural language task" rows={4} value={objective} onChange={e=>setObjective(e.target.value)} />
          <input className="bg-gray-800 p-2 rounded" placeholder="Project directory (optional)" value={projectDir} onChange={e=>setProjectDir(e.target.value)} />
          <div className="flex gap-2 items-center">
            <select className="bg-gray-800 p-2 rounded" value={mode} onChange={e=>setMode(e.target.value)}>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
              <option value="high_quality">High Quality</option>
            </select>
            <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={autoRoute} onChange={e=>setAutoRoute(e.target.checked)} /> Auto route</label>
            <button onClick={create} className="bg-cyan-600 px-4 py-2 rounded">Create</button>
          </div>
        </div>
      </Card>
      <Card title="Tasks">
        <table className="w-full text-sm">
          <thead><tr className="text-gray-400"><th className="text-left">Title</th><th>Status</th><th>Model</th><th>Actions</th></tr></thead>
          <tbody>{tasks.map((t:any)=>(
            <tr key={t.id} className="border-t border-gray-800">
              <td>{t.title}</td><td>{t.status}</td><td className="text-xs">{t.current_model}</td>
              <td className="flex gap-1">
                <button disabled={running===t.id} onClick={()=>run(t.id,true)} className="bg-green-600 px-2 py-0.5 rounded text-xs">Run Sync</button>
                <button disabled={running===t.id} onClick={()=>run(t.id,false)} className="bg-blue-600 px-2 py-0.5 rounded text-xs">Run BG</button>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </Card>
    </div>
  )
}

function TokenAnalytics({usage, budget}: any) {
  if (!usage) return <div>Loading...</div>
  const data = usage.by_provider || []
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Token Analytics</h2>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <Stat label="Input Tokens" value={usage.total_input_tokens} />
        <Stat label="Output Tokens" value={usage.total_output_tokens} />
        <Stat label="Est. Cost $" value={usage.total_cost} />
      </div>
      <Card title="Usage by Provider">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data}>
            <XAxis dataKey="provider" stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" />
            <Tooltip />
            <Bar dataKey="input" fill="#22d3ee" />
            <Bar dataKey="output" fill="#a78bfa" />
          </BarChart>
        </ResponsiveContainer>
      </Card>
      <Card title="Budget">
        {budget && <div className="text-sm">
          <div>Daily: ${budget.daily_spent} / ${budget.daily_limit} (remaining ${budget.daily_remaining})</div>
          <div>Monthly: ${budget.monthly_spent} / ${budget.monthly_limit} (remaining ${budget.monthly_remaining})</div>
        </div>}
      </Card>
      <Card title="Usage by Model">
        <div className="max-h-64 overflow-auto text-xs">
          <table className="w-full">
            <thead><tr className="text-gray-400"><th className="text-left">Model</th><th>In</th><th>Out</th><th>Cost</th><th>Calls</th></tr></thead>
            <tbody>{(usage.by_model||[]).map((m:any,i:number)=>(
              <tr key={i} className="border-t border-gray-800"><td>{m.model}</td><td>{m.input}</td><td>{m.output}</td><td>{m.cost.toFixed(4)}</td><td>{m.calls}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function RecoveryCenter({tasks, approvals, refresh}: any) {
  const failed = tasks.filter((t:any)=> t.status==='failed' || t.status==='paused')
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Recovery Center</h2>
      <Card title="Failed / Paused Tasks">
        <table className="w-full text-sm">
          <thead><tr className="text-gray-400"><th className="text-left">Title</th><th>Status</th><th>Error</th><th>Actions</th></tr></thead>
          <tbody>{failed.map((t:any)=>(
            <tr key={t.id} className="border-t border-gray-800">
              <td>{t.title}</td><td>{t.status}</td><td className="text-xs text-red-400">{t.error}</td>
              <td><button onClick={async()=>{await api.runTaskSync(t.id); refresh()}} className="bg-yellow-600 px-2 py-0.5 rounded text-xs">Recover</button></td>
            </tr>
          ))}</tbody>
        </table>
        {failed.length===0 && <div className="text-gray-500 text-sm">No failed tasks.</div>}
      </Card>
      <Card title="Approvals">
        <table className="w-full text-sm">
          <thead><tr className="text-gray-400"><th className="text-left">Action</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>{approvals.map((a:any)=>(
            <tr key={a.id} className="border-t border-gray-800">
              <td>{a.action}</td><td>{a.status}</td>
              <td></td>
            </tr>
          ))}</tbody>
        </table>
      </Card>
    </div>
  )
}

function Settings({budget, refresh}: any) {
  const [daily, setDaily] = useState(budget?.daily_limit || 5)
  const [monthly, setMonthly] = useState(budget?.monthly_limit || 20)
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Settings</h2>
      <Card title="Budget Limits">
        <div className="flex gap-2 items-center">
          <label className="text-sm">Daily $</label>
          <input type="number" className="bg-gray-800 p-2 rounded w-24" value={daily} onChange={e=>setDaily(Number(e.target.value))} />
          <label className="text-sm">Monthly $</label>
          <input type="number" className="bg-gray-800 p-2 rounded w-24" value={monthly} onChange={e=>setMonthly(Number(e.target.value))} />
          <button onClick={async()=>{await (await import('axios')).default.put(`/api/settings/budget?daily=${daily}&monthly=${monthly}`); refresh()}} className="bg-cyan-600 px-3 py-1 rounded text-sm">Save</button>
        </div>
      </Card>
      <Card title="Provider Configuration">
        <div className="text-sm text-gray-400">
          Set API keys via environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY/GEMINI_API_KEY, OPENROUTER_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY, FIREWORKS_API_KEY, XAI_API_KEY.
          Restart backend to pick up new keys.
        </div>
      </Card>
    </div>
  )
}
