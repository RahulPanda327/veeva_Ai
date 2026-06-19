import { BarChart2, BookOpen, Map, Users } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import clsx from 'clsx'

const navItems = [
  { to: '/insights', icon: BarChart2, label: 'My Insights' },
  { to: '/territory', icon: Map, label: 'Territory Prioritization' },
  { to: '/new-writers', icon: Users, label: 'New Writer ID' },
  { to: '/objections', icon: BookOpen, label: 'Objection Handler' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-navy-800 text-slate-300 flex flex-col py-4 gap-1 shrink-0">
      {navItems.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-r-full mr-3 transition-colors',
              isActive
                ? 'bg-blue-600 text-white'
                : 'hover:bg-navy-700 hover:text-white',
            )
          }
        >
          <Icon className="w-4 h-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </aside>
  )
}
