import { Activity } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Navbar() {
  return (
    <header className="bg-navy-900 text-white h-14 flex items-center px-6 gap-4 z-10 shadow-lg">
      <Link to="/insights" className="flex items-center gap-2 font-bold text-lg tracking-tight">
        <Activity className="w-5 h-5 text-blue-400" />
        <span>Rep<span className="text-blue-400">Stream</span></span>
      </Link>

      <div className="flex-1" />

      <div className="flex items-center gap-3 text-sm text-slate-300">
        <span className="hidden md:block">TERR-001 · Boston North</span>
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold text-xs">
          RP
        </div>
      </div>
    </header>
  )
}
