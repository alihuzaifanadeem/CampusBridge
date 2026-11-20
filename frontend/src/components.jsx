import { Bell, BookOpen, BriefcaseBusiness, CalendarDays, GraduationCap, UsersRound } from 'lucide-react'

const swatches = ['blue', 'violet', 'teal', 'amber', 'rose', 'indigo']

export function initials(name = 'Campus Bridge') {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase()
}

export function Avatar({ user, size = 'md', className = '' }) {
  const name = typeof user === 'string' ? user : user?.full_name || user?.name || 'Campus Bridge'
  const key = name.split('').reduce((value, char) => value + char.charCodeAt(0), 0) % swatches.length
  return <span className={`avatar avatar-${size} avatar-${swatches[key]} ${className}`} aria-label={name}>{initials(name)}</span>
}

export function RoleBadge({ user }) {
  if (!user) return null
  const role = user.role || 'student'
  const detail = role === 'student' ? user.semester || user.program : role === 'alumni' ? `Class of ${user.passing_year || '2024'}` : user.designation || (role === 'faculty' ? 'Faculty' : role.replace('_', ' '))
  return <span className={`role-badge role-${role}`}>{detail || role}</span>
}

export function CampusMark({ children = 'CB', small = false }) {
  return <span className={`campus-mark ${small ? 'campus-mark-small' : ''}`} aria-hidden="true"><GraduationCap size={small ? 16 : 19} />{children !== 'CB' && <span>{children}</span>}</span>
}

export function SectionTitle({ icon: Icon = BookOpen, title, aside }) {
  return <div className="section-title"><div className="section-title-name"><span className="section-icon"><Icon size={17} /></span><h2>{title}</h2></div>{aside}</div>
}

export function Metric({ icon: Icon = UsersRound, value, label, tone = 'blue' }) {
  return <div className={`metric metric-${tone}`}><span className="metric-icon"><Icon size={18} /></span><div><strong>{value}</strong><span>{label}</span></div></div>
}

export function StatusPill({ status }) {
  const label = status === 'available' ? 'Available now' : status === 'away' ? 'Away' : status === 'pending' ? 'Pending' : status === 'approved' ? 'Approved' : status === 'declined' ? 'Declined' : status === 'rescheduled' ? 'Rescheduled' : 'Busy / teaching'
  return <span className={`status-pill status-${status || 'busy'}`}><i />{label}</span>
}

export function Toast({ toast, onClose }) {
  if (!toast) return null
  return <div className={`toast toast-${toast.kind || 'success'}`} role="status"><Bell size={17} /><span>{toast.message}</span><button type="button" onClick={onClose} aria-label="Dismiss notification">×</button></div>
}

export function EventIcon() { return <CalendarDays size={15} /> }
export function FacultyIcon() { return <BriefcaseBusiness size={15} /> }
