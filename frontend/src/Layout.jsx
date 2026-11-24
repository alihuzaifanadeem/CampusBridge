import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Bell, Bookmark, BriefcaseBusiness, ChevronDown, CircleHelp, FilePlus2, GraduationCap, Home, LogOut, Menu, MessageCircle, Search, Settings, UsersRound, X } from 'lucide-react'
import { Avatar, CampusMark, RoleBadge, Toast } from './components.jsx'
import { useCampusBridge } from './App.jsx'

export default function Layout() {
  const { user, logout, toast, clearToast, searchQuery, setSearchQuery, refreshFeed } = useCampusBridge()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [accountMenu, setAccountMenu] = useState(false)
  const navigate = useNavigate()
  const links = [
    { to: '/', label: 'Home feed', icon: Home },
    { to: '/directory', label: 'Faculty directory', icon: UsersRound },
    { to: '/create', label: 'Create post', icon: FilePlus2 },
    { to: '/requests', label: 'Assistance requests', icon: CircleHelp },
    { to: '/notifications', label: 'Notifications', icon: Bell },
    ...(user?.role === 'faculty' ? [{ to: '/schedule', label: 'Availability & schedule', icon: GraduationCap }, ...(user.verified ? [{ to: '/collaborations', label: 'Faculty collaboration', icon: BriefcaseBusiness }] : [])] : []),
    { to: '/profile', label: 'My profile', icon: UsersRound },
    { to: '/saved', label: 'Saved discussions', icon: Bookmark },
    { to: '/settings', label: 'Settings', icon: Settings },
    ...(user?.role === 'admin' || user?.role === 'system_admin' ? [{ to: '/admin', label: 'Admin console', icon: Settings }] : []),
  ]
  return <div className="app-frame">
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand-row"><CampusMark /><span>Campus<span className="brand-light">Bridge</span></span><button className="icon-button sidebar-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18} /></button></div>
      <nav className="main-nav" aria-label="Main navigation">
        <p className="nav-label">Workspace</p>
        {links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} title={to === '/' ? 'Double-click to refresh the latest feed posts' : undefined} onClick={() => setMobileOpen(false)} onDoubleClick={to === '/' ? () => { void refreshFeed() } : undefined} className={({ isActive }) => `nav-item ${isActive ? 'nav-active' : ''}`}><Icon size={18} /><span>{label}</span>{label === 'Assistance requests' && <span className="nav-dot" />}</NavLink>)}
      </nav>
      <div className="sidebar-note"><div className="note-icon"><GraduationCap size={17} /></div><strong>Academic community</strong><p>Connect, learn, and collaborate across your campuses.</p></div>
      {accountMenu && <div className="account-menu"><button onClick={() => { navigate('/settings'); setAccountMenu(false) }}><Settings size={15} />Profile settings</button><button onClick={() => { logout(); setAccountMenu(false) }}><LogOut size={15} />Sign out</button></div>}
      <button className="account-button" onClick={() => setAccountMenu(!accountMenu)}><Avatar user={user} size="sm" /><span className="account-copy"><strong>{user?.full_name}</strong><small><RoleBadge user={user} /></small></span><ChevronDown size={15} /></button>
    </aside>
    {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
    <main className="main-shell">
      <header className="topbar">
        <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu size={19} /></button>
        <label className="global-search"><Search size={17} /><input value={searchQuery} onChange={event => setSearchQuery(event.target.value)} placeholder="Search discussions, faculty, research topics..." /><kbd>⌘ K</kbd></label>
        <div className="top-actions"><button className="icon-button notification-button" onClick={() => navigate('/notifications')} aria-label="Notifications"><Bell size={19} /><i /></button><button className="icon-button message-button" onClick={() => navigate('/requests')} aria-label="Assistance requests"><MessageCircle size={19} /></button><button className="button button-primary top-create" onClick={() => navigate('/create')}><FilePlus2 size={16} /><span>New post</span></button><button className="top-avatar" onClick={() => navigate('/profile')}><Avatar user={user} size="sm" /></button></div>
      </header>
      <div className="page-region"><Outlet /></div>
    </main>
    <Toast toast={toast} onClose={clearToast} />
  </div>
}
