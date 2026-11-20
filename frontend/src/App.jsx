import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './Layout.jsx'
import { request, postJson, patchJson } from './api.js'
import { demoCollaborations, demoGuidance, demoPosts, demoUsers } from './demoData.js'
import { AdminPage, CollaborationPage, CreatePostPage, DirectoryPage, FeedPage, FacultyPage, LoginPage, NotificationsPage, ProfilePage, RequestsPage, SavedPage, SchedulePage, SettingsPage } from './pages.jsx'

const Context = createContext(null)
export const useCampusBridge = () => useContext(Context)
const restore = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) || fallback } catch { return fallback } }

function Protected({ children, allow, requireVerified = false }) {
  const { user } = useCampusBridge()
  if (!user) return <Navigate to="/login" replace />
  if (allow && !allow.includes(user.role)) return <Navigate to="/" replace />
  if (requireVerified && user.role === 'faculty' && !user.verified) return <Navigate to="/schedule" replace />
  return children || <Layout />
}

export default function App() {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('cb.token'))
  const [posts, setPosts] = useState(() => restore('cb.demo.posts', demoPosts))
  const [users, setUsers] = useState(() => restore('cb.demo.users', demoUsers))
  const [guidance, setGuidance] = useState(() => restore('cb.demo.guidance', demoGuidance))
  const [collaborations, setCollaborations] = useState(() => restore('cb.demo.collaborations', demoCollaborations))
  const [toast, setToast] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const isLive = Boolean(token && token !== 'demo')

  const notify = (message, kind = 'success') => {
    setToast({ message, kind })
    window.clearTimeout(window.__cbToastTimer)
    window.__cbToastTimer = window.setTimeout(() => setToast(null), 3800)
  }

  useEffect(() => {
    const storedUser = localStorage.getItem('cb.user')
    if (!token && storedUser) setUser(JSON.parse(storedUser))
    if (token && token !== 'demo') {
      request('/auth/me', {}, token).then(setUser).catch(() => { localStorage.removeItem('cb.token'); localStorage.removeItem('cb.user'); setToken(null); setUser(null) })
    }
  }, [])

  useEffect(() => {
    if (!user || !isLive) return
    const load = async () => {
      const tasks = [request('/posts', {}, token), request('/users?role=faculty', {}, token)]
      if (user.role === 'faculty') tasks.push(request('/guidance-requests', {}, token), request('/collaborations', {}, token))
      if (user.role === 'student' || user.role === 'alumni') tasks.push(request('/guidance-requests', {}, token))
      const results = await Promise.allSettled(tasks)
      if (results[0].status === 'fulfilled') setPosts(results[0].value)
      if (results[1].status === 'fulfilled') setUsers([user, ...results[1].value.filter(item => item.id !== user.id)])
      if (results[2]?.status === 'fulfilled') setGuidance(results[2].value)
      if (user.role === 'faculty' && results[3]?.status === 'fulfilled') setCollaborations(results[3].value)
    }
    load()
  }, [user, token])

  useEffect(() => {
    if (isLive) return
    localStorage.setItem('cb.demo.posts', JSON.stringify(posts))
    localStorage.setItem('cb.demo.users', JSON.stringify(users))
    localStorage.setItem('cb.demo.guidance', JSON.stringify(guidance))
    localStorage.setItem('cb.demo.collaborations', JSON.stringify(collaborations))
  }, [isLive, posts, users, guidance, collaborations])

  const login = (nextUser, nextToken = null) => {
    setUser(nextUser)
    setToken(nextToken || 'demo')
    if (nextToken) localStorage.setItem('cb.token', nextToken)
    else localStorage.removeItem('cb.token')
    localStorage.setItem('cb.user', JSON.stringify(nextUser))
  }

  const logout = () => {
    setUser(null); setToken(null)
    localStorage.removeItem('cb.token'); localStorage.removeItem('cb.user')
  }

  const createPost = async payload => {
    if (isLive) {
      try { const created = await postJson('/posts', payload, token); setPosts(items => [created, ...items]); notify('Your post is now live.'); return created }
      catch (error) { notify(error.message, 'error'); throw error }
    }
    const created = { ...payload, id: Date.now(), campus: payload.campus || user.campus, author: user, created_at: new Date().toISOString(), like_count: 0, comment_count: 0, liked: false, saved: false, comments: [] }
    setPosts(items => [created, ...items]); notify('Your post is now live.'); return created
  }

  const toggleLike = async postId => {
    const before = posts.find(item => item.id === postId)
    if (isLive) {
      try { const result = await postJson(`/posts/${postId}/like`, {}, token); setPosts(items => items.map(item => item.id === postId ? { ...item, liked: result.liked, like_count: result.like_count } : item)); return }
      catch (error) { notify(error.message, 'error'); return }
    }
    setPosts(items => items.map(item => item.id === postId ? { ...item, liked: !item.liked, like_count: Math.max(0, item.like_count + (item.liked ? -1 : 1)) } : item))
  }

  const toggleSave = async postId => {
    if (isLive) {
      try { const result = await postJson(`/posts/${postId}/save`, {}, token); setPosts(items => items.map(item => item.id === postId ? { ...item, saved: result.saved } : item)); notify(result.saved ? 'Saved to your discussions.' : 'Removed from saved discussions.'); return }
      catch (error) { notify(error.message, 'error'); return }
    }
    setPosts(items => items.map(item => item.id === postId ? { ...item, saved: !item.saved } : item))
  }

  const addComment = async (postId, content) => {
    if (isLive) {
      try { const updated = await postJson(`/posts/${postId}/comments`, { content }, token); setPosts(items => items.map(item => item.id === postId ? updated : item)); return }
      catch (error) { notify(error.message, 'error'); return }
    }
    const comment = { id: Date.now(), content, created_at: new Date().toISOString(), author: user }
    setPosts(items => items.map(item => item.id === postId ? { ...item, comments: [...(item.comments || []), comment], comment_count: item.comment_count + 1 } : item))
  }

  const createGuidance = async payload => {
    if (isLive) {
      try { const item = await postJson('/guidance-requests', payload, token); setGuidance(items => [item, ...items]); notify('Your consultation request was sent.'); return item }
      catch (error) { notify(error.message, 'error'); throw error }
    }
    const item = { ...payload, id: Date.now(), topic: payload.topic, message: payload.message, status: 'pending', created_at: new Date().toISOString(), requester: user, faculty: users.find(person => person.id === payload.faculty_id) || users[1] }
    setGuidance(items => [item, ...items]); notify('Your consultation request was sent.'); return item
  }

  const updateGuidance = async (id, nextStatus) => {
    if (isLive) {
      try { const updated = await patchJson(`/guidance-requests/${id}`, { status: nextStatus }, token); setGuidance(items => items.map(item => item.id === id ? updated : item)); notify(`Request ${nextStatus}.`); return }
      catch (error) { notify(error.message, 'error'); return }
    }
    setGuidance(items => items.map(item => item.id === id ? { ...item, status: nextStatus } : item)); notify(`Request ${nextStatus}.`)
  }

  const createCollaboration = async payload => {
    if (isLive) {
      try { const item = await postJson('/collaborations', payload, token); setCollaborations(items => [item, ...items]); notify('Collaboration request published.'); return }
      catch (error) { notify(error.message, 'error'); throw error }
    }
    const item = { ...payload, id: Date.now(), author: user, status: 'active', interested_count: 0, accepted: false, created_at: new Date().toISOString() }
    setCollaborations(items => [item, ...items]); notify('Collaboration request published.')
  }

  const respondCollaboration = async id => {
    if (isLive) {
      try { const updated = await postJson(`/collaborations/${id}/respond`, {}, token); setCollaborations(items => items.map(item => item.id === id ? updated : item)); notify('You are connected to this opportunity.'); return }
      catch (error) { notify(error.message, 'error'); return }
    }
    setCollaborations(items => items.map(item => item.id === id ? { ...item, accepted: true, interested_count: item.interested_count + 1 } : item)); notify('You are connected to this opportunity.')
  }

  const updateProfile = async changes => {
    let updated = { ...user, ...changes }
    if (isLive) {
      try { updated = await patchJson('/auth/me', changes, token) }
      catch (error) { notify(error.message, 'error'); throw error }
    }
    setUser(updated); localStorage.setItem('cb.user', JSON.stringify(updated)); setUsers(items => items.map(item => item.id === updated.id ? updated : item)); notify('Profile updated.')
    return updated
  }

  const value = useMemo(() => ({ user, token, isLive, posts, setPosts, users, guidance, collaborations, toast, clearToast: () => setToast(null), notify, searchQuery, setSearchQuery, login, logout, createPost, toggleLike, toggleSave, addComment, createGuidance, updateGuidance, createCollaboration, respondCollaboration, updateProfile }), [user, token, isLive, posts, users, guidance, collaborations, toast, searchQuery])

  return <Context.Provider value={value}>
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route index element={<FeedPage />} />
        <Route path="directory" element={<DirectoryPage />} />
        <Route path="create" element={<CreatePostPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="faculty/:id" element={<FacultyPage />} />
        <Route path="requests" element={<RequestsPage />} />
        <Route path="saved" element={<SavedPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="schedule" element={<Protected allow={['faculty']}><SchedulePage /></Protected>} />
        <Route path="collaborations" element={<Protected allow={['faculty']} requireVerified><CollaborationPage /></Protected>} />
        <Route path="admin" element={<Protected allow={['admin', 'system_admin']}><AdminPage /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  </Context.Provider>
}
