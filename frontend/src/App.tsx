import { FormEvent, useEffect, useState } from 'react';
import CoordinationMap from './components/maps/CoordinationMap';

type Role = 'requester' | 'donor' | 'coordinator' | 'volunteer';
type PublicRole = 'requester' | 'donor';

type AppUser = {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  role: Role;
  active: boolean;
  college_org?: string | null;
  nss_unit?: string | null;
};

type DonorProfile = {
  id: number;
  user_id: number;
  blood_group: string;
  city: string;
  area?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  available: boolean;
  last_donation_date?: string | null;
  verified: boolean;
};

type RequestItem = {
  id: number;
  request_code?: string;
  patient_reference?: string;
  blood_group?: string;
  status?: string;
  city?: string;
  latitude?: number | null;
  longitude?: number | null;
  urgency?: string;
  created_at?: string;
  hospital_name?: string;
  hospital_address?: string;
  units_required?: number;
  required_at?: string;
  request_latitude?: number | null;
  request_longitude?: number | null;
  contact_name?: string;
  contact_phone?: string;
  notes?: string;
};

type DonorMatchItem = {
  match_id: number;
  request_id: number;
  request_code: string;
  blood_group_required: string;
  units_required: number;
  hospital_name: string;
  city: string;
  urgency: string;
  required_at?: string;
  request_status: string;
  distance_km?: number | null;
  match_score?: number;
  donor_response_status: 'pending' | 'accepted' | 'declined';
  response_timestamp?: string | null;
};

type DonorHistoryItem = {
  request_id: number;
  request_code: string;
  blood_group: string;
  hospital_name: string;
  city: string;
  urgency: string;
  response: 'accepted' | 'declined';
  response_timestamp?: string;
  request_status: string;
};

type MatchSummary = {
  total_matches: number;
  pending_responses: number;
  accepted_count: number;
  declined_count: number;
  matches: Array<{
    match_id: number;
    donor_name: string;
    blood_group: string;
    city?: string;
    area?: string | null;
    distance_km?: number | null;
    match_score?: number;
    response_status: string;
  }>;
};

type CoordinationMapData = {
  request: { latitude?: number | null; longitude?: number | null; hospital_name: string; hospital_address?: string; city: string };
  matched_donors: Array<{
    donor_id: number;
    safe_display_name: string;
    blood_group: string;
    area?: string | null;
    city?: string;
    latitude: number;
    longitude: number;
    distance_km?: number | null;
    match_score?: number;
    response_status: string;
  }>;
};

type ManagedDonor = {
  donor_id: number;
  name: string;
  blood_group: string;
  city: string;
  area?: string | null;
  available: boolean;
  verified: boolean;
  updated_at?: string;
};

type ManagedVolunteer = {
  volunteer_id: number;
  name: string;
  active: boolean;
  city?: string | null;
  area?: string | null;
};

type VolunteerAssignment = {
  id: number;
  request_id: number;
  request_code?: string;
  patient_reference?: string;
  blood_group?: string;
  units_required?: number;
  hospital_name?: string;
  hospital_address?: string;
  city?: string;
  required_at?: string;
  urgency?: string;
  request_status?: string;
  volunteer_id: number;
  volunteer_name?: string;
  status: 'assigned' | 'accepted' | 'in_progress' | 'completed' | 'cancelled';
  notes?: string | null;
  assigned_at?: string;
  accepted_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
};

type CampaignItem = {
  id: number;
  title: string;
  description?: string | null;
  location: string;
  campaign_date: string;
  organizer_id?: number;
  status: string;
  participant_count: number;
  registered_donors: number;
  units_recorded: number;
};

type DonorProfileForm = {
  blood_group: string;
  city: string;
  area: string;
  last_donation_date: string;
};

type NotificationItem = {
  id: number;
  title: string;
  message: string;
  type?: string;
  is_read: boolean;
  created_at?: string;
  related_entity_id?: number | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'nss-bloodconnect-token';
const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

const roleDashboardPath: Record<Role, string> = {
  requester: '/dashboard/requester',
  donor: '/dashboard/donor',
  coordinator: '/dashboard/coordinator',
  volunteer: '/dashboard/volunteer',
};

const requesterNav = [
  { label: 'Dashboard', path: '/dashboard/requester' },
  { label: 'Request Blood', path: '/requests/create' },
  { label: 'My Requests', path: '/requests/my' },
  { label: 'Notifications', path: '/notifications' },
  { label: 'Profile', path: '/profile' },
  { label: 'AI Assistant', path: '/ai-assistant' },
];

const donorNav = [
  { label: 'Dashboard', path: '/dashboard/donor' },
  { label: 'Blood Requests', path: '/donor/requests' },
  { label: 'Accepted Requests', path: '/donor/accepted' },
  { label: 'History', path: '/donor/history' },
  { label: 'Notifications', path: '/notifications' },
  { label: 'Profile', path: '/profile' },
  { label: 'AI Assistant', path: '/ai-assistant' },
];

const volunteerNav = [
  { label: 'Dashboard', path: '/dashboard/volunteer' },
  { label: 'Assigned Requests', path: '/volunteer/assigned' },
  { label: 'Active Requests', path: '/volunteer/requests' },
  { label: 'Notifications', path: '/notifications' },
  { label: 'Profile', path: '/profile' },
  { label: 'AI Assistant', path: '/ai-assistant' },
];

const coordinatorNav = [
  { label: 'Dashboard', path: '/dashboard/coordinator' },
  { label: 'Pending Verification', path: '/coordinator/verification' },
  { label: 'Active Requests', path: '/coordinator/requests' },
  { label: 'Donors', path: '/coordinator/donors' },
  { label: 'Volunteers', path: '/coordinator/volunteers' },
  { label: 'Campaigns', path: '/coordinator/campaigns' },
  { label: 'Analytics', path: '/coordinator/analytics' },
  { label: 'Reports', path: '/coordinator/reports' },
  { label: 'Audit Logs', path: '/coordinator/audit' },
  { label: 'Notifications', path: '/notifications' },
  { label: 'Profile', path: '/profile' },
  { label: 'AI Assistant', path: '/ai-assistant' },
];

function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

async function fetchProfile(token: string): Promise<AppUser> {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error('Unable to load account');
  }
  return response.json();
}

function navigateTo(path: string) {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function App() {
  const [route, setRoute] = useState(window.location.pathname);
  const [authUser, setAuthUser] = useState<AppUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    const onRouteChange = () => setRoute(window.location.pathname);
    window.addEventListener('popstate', onRouteChange);
    return () => window.removeEventListener('popstate', onRouteChange);
  }, []);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setAuthUser(null);
      setAuthLoading(false);
      return;
    }

    fetchProfile(token)
      .then((user) => setAuthUser(user))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setAuthUser(null);
      })
      .finally(() => setAuthLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading) return;

    if (route === '/unauthorized' && authUser) return;

    if (route.startsWith('/dashboard') && !authUser) {
      navigateTo('/login');
      return;
    }

    if (route === '/' && authUser) {
      navigateTo(roleDashboardPath[authUser.role]);
      return;
    }

    if ((route === '/login' || route === '/register') && authUser) {
      navigateTo(roleDashboardPath[authUser.role]);
      return;
    }

    if (route.startsWith('/dashboard') && authUser) {
      const expected = roleDashboardPath[authUser.role];
      const isBaseDashboard = route === expected;
      const isRoleNestedPath = route.startsWith(`${expected}/`);
      if (!isBaseDashboard && !isRoleNestedPath) {
        navigateTo(expected);
      }
    }
  }, [authLoading, authUser, route]);

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setAuthUser(null);
    navigateTo('/');
  };

  if (authLoading) {
    return <PageShell><LoadingState message="Loading NSS BloodConnect..." /></PageShell>;
  }

  const renderCurrentPage = () => {
    if (route === '/') return <LandingPage />;
    if (route === '/login') return authUser ? <DashboardRenderer user={authUser} onLogout={logout} /> : <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
    if (route === '/register') return authUser ? <DashboardRenderer user={authUser} onLogout={logout} /> : <RegisterPage />;
    if (route === '/about') return <AboutPage />;
    if (route === '/awareness') return <AwarenessPage />;
    if (route === '/campaigns') return <PublicCampaignsPage />;
    if (route.startsWith('/campaigns/')) {
      const match = route.match(/^\/campaigns\/(\d+)$/);
      if (match) return <PublicCampaignDetailPage campaignId={Number(match[1])} />;
    }
    if (route === '/unauthorized') return <UnauthorizedPage />;
    if (route === '/notifications') return authUser ? <NotificationsPage user={authUser} /> : <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
    if (route === '/profile') return authUser ? <ProfilePage user={authUser} /> : <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
    if (route === '/ai-assistant') return authUser ? <AiAssistantPage user={authUser} /> : <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;

    if (route.startsWith('/requests')) {
      if (!authUser) return <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
      if (authUser.role !== 'requester' && authUser.role !== 'coordinator') return <UnauthorizedPage />;
      if (route === '/requests/create') return <RequestCreatePage user={authUser} />;
      if (route === '/requests/my') return <RequestsListPage user={authUser} />;
      if (route.startsWith('/requests/')) {
        const match = route.match(/^\/requests\/(\d+)$/);
        if (match) return <RequestDetailPage user={authUser} requestId={Number(match[1])} />;
      }
    }

    if (route.startsWith('/donor')) {
      if (!authUser) return <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
      if (authUser.role !== 'donor' && authUser.role !== 'coordinator') return <UnauthorizedPage />;
      if (route === '/donor/requests') return <DonorRequestsPage user={authUser} />;
      if (route.startsWith('/donor/requests/')) {
        const match = route.match(/^\/donor\/requests\/(\d+)$/);
        if (match) return <DonorRequestDetailPage user={authUser} requestId={Number(match[1])} />;
      }
      if (route === '/donor/accepted') return <DonorAcceptedPage user={authUser} />;
      if (route === '/donor/history') return <DonorHistoryPage user={authUser} />;
      if (route === '/donor/profile') return <DonorProfilePage user={authUser} onLogout={logout} />;
    }

    if (route.startsWith('/volunteer')) {
      if (!authUser) return <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
      if (authUser.role !== 'volunteer' && authUser.role !== 'coordinator') return <UnauthorizedPage />;
      if (route === '/volunteer/dashboard') return <VolunteerDashboard user={authUser} onLogout={logout} />;
      if (route === '/volunteer/assigned') return <VolunteerAssignedPage user={authUser} />;
      if (route === '/volunteer/requests') return <VolunteerRequestsPage user={authUser} />;
      if (route.startsWith('/volunteer/requests/')) {
        const match = route.match(/^\/volunteer\/requests\/(\d+)$/);
        if (match) return <VolunteerRequestDetailPage user={authUser} requestId={Number(match[1])} />;
      }
    }

    if (route.startsWith('/coordinator')) {
      if (!authUser) return <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
      if (authUser.role !== 'coordinator') return <UnauthorizedPage />;
      if (route === '/coordinator/verification') return <CoordinatorVerificationPage user={authUser} />;
      if (route === '/coordinator/requests') return <CoordinatorRequestsPage user={authUser} />;
      if (route.startsWith('/coordinator/requests/')) {
        const match = route.match(/^\/coordinator\/requests\/(\d+)$/);
        if (match) return <CoordinatorRequestDetailPage user={authUser} requestId={Number(match[1])} />;
      }
      if (route === '/coordinator/donors') return <CoordinatorDonorsPage user={authUser} />;
      if (route === '/coordinator/volunteers') return <CoordinatorVolunteersPage user={authUser} />;
      if (route === '/coordinator/campaigns') return <CoordinatorCampaignsPage user={authUser} />;
      if (route === '/coordinator/campaigns/create') return <CoordinatorCampaignCreatePage user={authUser} />;
      if (route.startsWith('/coordinator/campaigns/')) {
        const match = route.match(/^\/coordinator\/campaigns\/(\d+)$/);
        if (match) return <CoordinatorCampaignDetailPage user={authUser} campaignId={Number(match[1])} />;
      }
      if (route === '/coordinator/analytics') return <CoordinatorAnalyticsPage user={authUser} />;
      if (route === '/coordinator/reports') return <CoordinatorReportsPage user={authUser} />;
    }

    if (route.startsWith('/dashboard')) {
      if (!authUser) return <LoginPage onLoginComplete={(user) => setAuthUser(user)} />;
      return <DashboardRenderer user={authUser} onLogout={logout} />;
    }

    return <NotFoundPage />;
  };

  return renderCurrentPage();
}

function LandingPage() {
  return (
    <PageShell>
      <header className="topbar public-topbar">
        <div className="brand-block">
          <span className="brand-mark">NSS</span>
          <div>
            <p className="eyebrow">Blood donation coordination</p>
            <h1>NSS BloodConnect</h1>
          </div>
        </div>

        <nav className="public-actions">
          <button className="secondary-button" onClick={() => navigateTo('/login')}>Sign In</button>
        </nav>
      </header>

      <main className="hero-layout">
        <section className="hero-copy">
          <p className="eyebrow accent">Connecting Donors. Saving Lives. Empowering NSS.</p>
          <h2>A blood donation coordination platform connecting people who need blood with potentially compatible available donors through NSS volunteers and coordinators.</h2>
          <div className="cta-row">
            <button className="primary-button" onClick={() => navigateTo('/register?role=requester')}>Request Blood</button>
            <button className="secondary-button" onClick={() => navigateTo('/register?role=donor')}>Become a Donor</button>
          </div>
        </section>

        <aside className="hero-card">
          <h3>How it works</h3>
          <ol>
            <li>Request Blood</li>
            <li>Find Potential Donors</li>
            <li>Notify Donors</li>
            <li>Donor Responds</li>
            <li>NSS Coordinator Verifies</li>
            <li>Track Impact</li>
          </ol>
        </aside>
      </main>

      <section className="info-card">
          <h3>About NSS BloodConnect</h3>
          <p>NSS BloodConnect helps communities coordinate urgent blood support with a clear, accountable process. It provides a structured way for requesters to seek help, donors to indicate availability, and NSS teams to verify and coordinate response efforts while keeping medical decisions with qualified healthcare professionals.</p>
      </section>
    </PageShell>
  );
}

function LoginPage({ onLoginComplete }: { onLoginComplete: (user: AppUser) => void }) {
  const [email, setEmail] = useState('requester@example.com');
  const [password, setPassword] = useState('secret123');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
      }

      localStorage.setItem(TOKEN_KEY, data.access_token);
      const user = await fetchProfile(data.access_token);
      onLoginComplete(user);
      navigateTo(roleDashboardPath[user.role]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell>
      <div className="auth-shell">
        <section className="auth-card">
          <div className="card-header">
            <span className="brand-mark small">NSS</span>
            <h2>Sign In</h2>
          </div>
          <form onSubmit={handleSubmit} className="form-stack">
            <label className="field">
              <span>Email</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>

            <label className="field">
              <span>Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>

            {error ? <div className="error-box">{error}</div> : null}

            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting ? 'Signing In...' : 'Sign In'}
            </button>
          </form>

          <p className="auth-footnote">
            Need an account? <button className="link-button" onClick={() => navigateTo('/register')}>Create one</button>
          </p>
        </section>
      </div>
    </PageShell>
  );
}

function RegisterPage() {
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
    role: 'requester' as PublicRole,
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const roleParam = params.get('role');
    if (roleParam === 'donor' || roleParam === 'requester') {
      setForm((current) => ({ ...current, role: roleParam }));
    }
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setIsSubmitting(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed');
      }

      setSuccess('Account created successfully. Redirecting to sign in...');
      setTimeout(() => navigateTo('/login'), 600);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell>
      <div className="auth-shell">
        <section className="auth-card wide-card">
          <div className="card-header">
            <span className="brand-mark small">NSS</span>
            <h2>Create an account</h2>
          </div>

          <form onSubmit={handleSubmit} className="form-grid">
            <label className="field">
              <span>Full Name</span>
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            </label>

            <label className="field">
              <span>Email</span>
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </label>

            <label className="field">
              <span>Phone</span>
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required />
            </label>

            <label className="field">
              <span>Password</span>
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} />
            </label>

            <label className="field">
              <span>Role</span>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as PublicRole })}>
                <option value="requester">Requester</option>
                <option value="donor">Donor</option>
              </select>
            </label>

            {error ? <div className="error-box full-span">{error}</div> : null}
            {success ? <div className="success-box full-span">{success}</div> : null}

            <button type="submit" className="primary-button full-span" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account...' : 'Create account'}
            </button>
          </form>
        </section>
      </div>
    </PageShell>
  );
}

function DashboardRenderer({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const currentPath = window.location.pathname;

  if (currentPath === '/dashboard/donor/profile') return <DonorProfilePage user={user} onLogout={onLogout} />;
  if (currentPath === '/dashboard/requester' || currentPath === '/dashboard/requester/create' || currentPath === '/dashboard/requester/requests' || currentPath === '/dashboard/requester/notifications' || currentPath === '/dashboard/requester/profile') return <RequesterDashboard user={user} onLogout={onLogout} />;
  if (currentPath === '/dashboard/donor' || currentPath === '/dashboard/donor/requests' || currentPath === '/dashboard/donor/accepted' || currentPath === '/dashboard/donor/history' || currentPath === '/dashboard/donor/notifications') return <DonorDashboard user={user} onLogout={onLogout} />;
  if (currentPath === '/dashboard/volunteer' || currentPath === '/dashboard/volunteer/assigned' || currentPath === '/dashboard/volunteer/active' || currentPath === '/dashboard/volunteer/notifications' || currentPath === '/dashboard/volunteer/profile') return <VolunteerDashboard user={user} onLogout={onLogout} />;
  if (currentPath === '/dashboard/coordinator' || currentPath === '/dashboard/coordinator/pending' || currentPath === '/dashboard/coordinator/requests' || currentPath === '/dashboard/coordinator/donors' || currentPath === '/dashboard/coordinator/volunteers' || currentPath === '/dashboard/coordinator/notifications' || currentPath === '/dashboard/coordinator/profile') return <CoordinatorDashboard user={user} onLogout={onLogout} />;

  return <RequesterDashboard user={user} onLogout={onLogout} />;
}

function DashboardLayout({ user, onLogout, title, children }: { user: AppUser; onLogout: () => void; title: string; children: React.ReactNode }) {
  const navMap: Record<Role, { label: string; path: string }[]> = {
    requester: requesterNav,
    donor: donorNav,
    volunteer: volunteerNav,
    coordinator: coordinatorNav,
  };

  const navItems = navMap[user.role];
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const refreshUnreadCount = () => {
      const token = getStoredToken();
      if (!token) return;
      fetch(`${API_BASE}/api/notifications/unread-count`, { headers: { Authorization: `Bearer ${token}` } })
        .then((response) => response.ok ? response.json() : { count: 0 })
        .then((data) => setUnreadCount(Number(data.count) || 0))
        .catch(() => setUnreadCount(0));
    };
    refreshUnreadCount();
    window.addEventListener('notifications-updated', refreshUnreadCount);
    return () => window.removeEventListener('notifications-updated', refreshUnreadCount);
  }, [window.location.pathname]);

  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark small">NSS</span>
          <div>
            <strong>NSS BloodConnect</strong>
            <small>{user.role}</small>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
              <button key={item.path} className={window.location.pathname === item.path ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo(item.path)}>
              {item.label === 'Notifications' && unreadCount > 0 ? `${item.label} (${unreadCount})` : item.label}
            </button>
          ))}
        </nav>

        <button className="secondary-button full-width" onClick={onLogout}>Logout</button>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <p className="eyebrow">Dashboard</p>
            <h2>{title}</h2>
          </div>
          <div className="user-chip">{user.full_name}</div>
        </header>
        {children}
      </main>
    </div>
  );
}

function RequesterDashboard({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/requests`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load requests');
        const data = await response.json();
        setRequests(Array.isArray(data) ? data : []);
      })
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  const activeRequests = requests.filter((item) => !['fulfilled', 'cancelled'].includes(item.status || ''));

  return (
    <DashboardLayout user={user} onLogout={onLogout} title="Requester Dashboard">
      <section className="page-overview">
        <div>
          <p className="eyebrow">Welcome</p>
          <h3>Hi {user.full_name}, you can coordinate urgent support requests here.</h3>
        </div>
        <button className="primary-button" onClick={() => navigateTo('/requests/create')}>Request Blood</button>
      </section>

      <div className="stats-row">
        <StatusCard label="Active requests" value={String(activeRequests.length)} />
        <StatusCard label="Recent requests" value={String(Math.min(requests.length, 5))} />
      </div>

      <div className="content-grid two-col">
        <section className="panel-block">
          <h4>Recent requests</h4>
          {loading ? <LoadingState message="Loading requests..." /> : requests.length === 0 ? <EmptyState message="No requests have been created yet." /> : (
            <ul className="list-stack">
              {requests.slice(0, 5).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <strong>{item.patient_reference || 'Untitled request'}</strong>
                    <small>{item.request_code || 'BCR'} • {item.blood_group || 'Blood group not set'}</small>
                  </div>
                  <span className="pill status-pill">{item.status || 'submitted'}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel-block">
          <h4>Request status</h4>
          <div className="info-stack">
            <div className="info-row"><span>Submitted</span><strong>{requests.filter((item) => item.status === 'submitted').length}</strong></div>
            <div className="info-row"><span>Verified</span><strong>{requests.filter((item) => item.status === 'verified').length}</strong></div>
            <div className="info-row"><span>Fulfilled</span><strong>{requests.filter((item) => item.status === 'fulfilled').length}</strong></div>
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}

function DonorDashboard({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [profile, setProfile] = useState<DonorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingToggle, setPendingToggle] = useState(false);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/donors/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (response.status === 404) {
          setProfile(null);
          return;
        }
        if (!response.ok) throw new Error('Could not load donor profile');
        const data = await response.json();
        setProfile(data);
      })
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, []);

  const toggleAvailability = async () => {
    if (!profile) return;
    const nextState = !profile.available;
    setPendingToggle(true);

    try {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE}/api/donors/me/availability?available=${nextState}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Unable to update donor availability');
      const data = await response.json();
      setProfile((current) => (current ? { ...current, available: Boolean(data.available) } : current));
    } catch {
      setProfile((current) => (current ? { ...current, available: current.available } : current));
    } finally {
      setPendingToggle(false);
    }
  };

  const availabilityMessage = profile?.available
    ? 'You may be considered for potentially compatible blood requests in your area.'
    : 'You will not be included in new donor searches while your availability is turned off.';

  return (
    <DashboardLayout user={user} onLogout={onLogout} title="Donor Dashboard">
      <section className="page-overview">
        <div>
          <p className="eyebrow">Welcome</p>
          <h3>Hi {user.full_name}, your availability helps connect patients with support.</h3>
        </div>
        <button className="primary-button" onClick={() => navigateTo('/donor/profile')}>Manage Profile</button>
      </section>

      <div className="stats-row">
        <StatusCard label="Availability" value={profile?.available ? 'AVAILABLE' : 'UNAVAILABLE'} tone={profile?.available ? 'success' : 'neutral'} />
        <StatusCard label="Profile" value={profile ? 'Saved' : 'Pending'} tone={profile ? 'success' : 'neutral'} />
      </div>

      <div className="content-grid two-col">
        <section className="panel-block">
          <h4>Availability</h4>
          {loading ? <LoadingState message="Loading donor profile..." /> : (
            <>
              <button className={profile?.available ? 'toggle-button on' : 'toggle-button'} onClick={toggleAvailability} disabled={pendingToggle}>
                {pendingToggle ? 'Updating...' : profile?.available ? 'AVAILABLE' : 'UNAVAILABLE'}
              </button>
              <p className="muted-text">{availabilityMessage}</p>
            </>
          )}
        </section>

        <section className="panel-block">
          <h4>Potential request area</h4>
          {profile ? (
            <div className="info-stack">
              <div className="info-row"><span>Blood group</span><strong>{profile.blood_group}</strong></div>
              <div className="info-row"><span>City</span><strong>{profile.city}</strong></div>
              <div className="info-row"><span>Area</span><strong>{profile.area || 'Not set'}</strong></div>
            </div>
          ) : (
            <EmptyState message="Complete your donor profile to show your availability area." />
          )}
        </section>
      </div>

      <div className="content-grid">
        <section className="panel-block">
          <h4>Accepted requests</h4>
          <EmptyState message="No accepted requests yet." />
        </section>
        <section className="panel-block">
          <h4>Recent response history</h4>
          <EmptyState message="Your recent responses will appear here." />
        </section>
      </div>
    </DashboardLayout>
  );
}

function VolunteerDashboard({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [assignments, setAssignments] = useState<VolunteerAssignment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/volunteers/me/assignments`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load assignments');
        const data = await response.json();
        setAssignments(Array.isArray(data) ? data : []);
      })
      .catch(() => setAssignments([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={onLogout} title="Volunteer Dashboard">
      <div className="stats-row">
        <StatusCard label="Assigned" value={String(assignments.filter((item) => item.status === 'assigned').length)} />
        <StatusCard label="Active" value={String(assignments.filter((item) => ['accepted', 'in_progress'].includes(item.status)).length)} tone="success" />
        <StatusCard label="Completed" value={String(assignments.filter((item) => item.status === 'completed').length)} tone="neutral" />
      </div>

      <div className="content-grid">
        <section className="panel-block">
          <h4>Assigned requests</h4>
          {loading ? <LoadingState message="Loading assigned requests..." /> : assignments.length === 0 ? <EmptyState message="No assigned requests currently available." /> : (
            <ul className="list-stack">
              {assignments.slice(0, 5).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <strong>{item.request_code || 'Request'}</strong>
                    <small>{item.hospital_name || 'Hospital not set'}</small>
                  </div>
                  <span className="pill status-pill">{item.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel-block">
          <h4>Recent activity</h4>
          <EmptyState message="Recent volunteer coordination activity will appear here as the platform grows." />
        </section>
      </div>
    </DashboardLayout>
  );
}

function CoordinatorDashboard({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/requests`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load requests');
        const data = await response.json();
        setRequests(Array.isArray(data) ? data : []);
      })
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  const pendingVerification = requests.filter((item) => item.status === 'submitted').length;
  const activeRequests = requests.filter((item) => !['fulfilled', 'cancelled'].includes(item.status || '')).length;

  return (
    <DashboardLayout user={user} onLogout={onLogout} title="Coordinator Dashboard">
      <div className="stats-row">
        <StatusCard label="Pending verification" value={String(pendingVerification)} />
        <StatusCard label="Active requests" value={String(activeRequests)} />
      </div>

      <div className="content-grid two-col">
        <section className="panel-block">
          <h4>Active requests</h4>
          {loading ? <LoadingState message="Loading active requests..." /> : requests.length === 0 ? <EmptyState message="No active requests have been submitted yet." /> : (
            <ul className="list-stack">
              {requests.slice(0, 5).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <strong>{item.patient_reference || 'Request'}</strong>
                    <small>{item.city || 'City not set'}</small>
                  </div>
                  <span className="pill status-pill">{item.status || 'submitted'}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel-block">
          <h4>Available donors</h4>
          <EmptyState message="Donor directory data is not available in this phase." />
        </section>
      </div>

      <div className="content-grid">
        <section className="panel-block">
          <h4>Recent donor responses</h4>
          <EmptyState message="Recent organizer responses will appear here as donor interactions are recorded." />
        </section>
      </div>
    </DashboardLayout>
  );
}

function DonorProfilePage({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [form, setForm] = useState<DonorProfileForm>({ blood_group: 'A+', city: '', area: '', last_donation_date: '' });
  const [profileExists, setProfileExists] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/donors/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (response.status === 404) {
          setProfileExists(false);
          return;
        }
        if (!response.ok) throw new Error('Could not load donor profile');
        const data = await response.json();
        setProfileExists(true);
        setAvailable(Boolean(data.available));
        setForm({ blood_group: data.blood_group || 'A+', city: data.city || '', area: data.area || '', last_donation_date: data.last_donation_date || '' });
      })
      .catch(() => setError('Unable to load donor profile.'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!form.blood_group || !form.city.trim()) {
      setError('Blood group and city are required.');
      return;
    }

    try {
      const token = getStoredToken();
      const payload = {
        blood_group: form.blood_group,
        city: form.city,
        area: form.area || null,
        last_donation_date: form.last_donation_date || null,
        available,
      };

      const response = await fetch(`${API_BASE}/api/donors/me`, {
        method: profileExists ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) throwingError(data, 'Unable to save donor profile');

      setProfileExists(true);
      setAvailable(Boolean(data.available));
      setSuccess('Donor profile saved successfully.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save donor profile.');
    }
  };

  const toggleAvailability = async () => {
    const nextState = !available;
    setAvailable(nextState);

    try {
      const response = await fetch(`${API_BASE}/api/donors/me/availability?available=${nextState}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${getStoredToken()}` },
      });
      if (!response.ok) throw new Error('Unable to update availability');
    } catch {
      setAvailable(!nextState);
      setError('Availability could not be saved. Please try again.');
    }
  };

  return (
    <DashboardLayout user={user} onLogout={onLogout} title="Donor Profile">
      <div className="panel-block">
        <div className="profile-header-row">
          <div>
            <h4>Profile details</h4>
            <p className="muted-text">Your personal details remain visible only to your account.</p>
          </div>
          <button className={available ? 'toggle-button on' : 'toggle-button'} onClick={toggleAvailability}>
            {available ? 'AVAILABLE' : 'UNAVAILABLE'}
          </button>
        </div>

        {loading ? <LoadingState message="Loading donor profile..." /> : (
          <form onSubmit={handleSave} className="form-grid">
            <label className="field"><span>Full Name</span><input value={user.full_name} readOnly /></label>
            <label className="field"><span>Email</span><input type="email" value={user.email} readOnly /></label>
            <label className="field"><span>Phone</span><input value={user.phone} readOnly /></label>
            <label className="field">
              <span>Blood Group</span>
              <select value={form.blood_group} onChange={(e) => setForm({ ...form, blood_group: e.target.value })}>
                {BLOOD_GROUPS.map((group) => <option key={group} value={group}>{group}</option>)}
              </select>
            </label>
            <label className="field"><span>City</span><input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required /></label>
            <label className="field"><span>Area</span><input value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} placeholder="e.g. Koramangala" /></label>
            <label className="field"><span>Last Donation Date</span><input type="date" value={form.last_donation_date} onChange={(e) => setForm({ ...form, last_donation_date: e.target.value })} /></label>

            {error ? <div className="error-box full-span">{error}</div> : null}
            {success ? <div className="success-box full-span">{success}</div> : null}
            <button type="submit" className="primary-button full-span">Save profile</button>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

function RequestCreatePage({ user }: { user: AppUser }) {
  const [form, setForm] = useState({
    patient_reference: '',
    blood_group: 'O+',
    units_required: 1,
    hospital_name: '',
    hospital_address: '',
    city: '',
    required_at: '',
    required_time: '09:00',
    urgency: 'Normal',
    contact_name: '',
    contact_phone: '',
    notes: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [requestId, setRequestId] = useState<number | null>(null);

  const submitRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    if (!form.patient_reference || !form.hospital_name || !form.hospital_address || !form.city || !form.contact_name || !form.contact_phone || !form.required_at) {
      setError('Please complete all required request fields.');
      setLoading(false);
      return;
    }

    try {
      const dateTime = new Date(`${form.required_at}T${form.required_time}:00`);
      const token = getStoredToken();
      const response = await fetch(`${API_BASE}/api/requests`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...form,
          required_at: dateTime.toISOString(),
          urgency: form.urgency,
          units_required: Number(form.units_required),
          notes: form.notes || null,
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to submit request.');
      setRequestId(data.id);
      setSuccess(`Request created successfully with code ${data.request_code}.`);
      setTimeout(() => navigateTo(`/requests/${data.id}`), 600);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to submit request.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Create Blood Request">
      <div className="panel-block">
        <form onSubmit={submitRequest} className="form-grid">
          <label className="field"><span>Patient / Request Reference Name</span><input value={form.patient_reference} onChange={(e) => setForm({ ...form, patient_reference: e.target.value })} required /></label>
          <label className="field"><span>Blood Group Required</span><select value={form.blood_group} onChange={(e) => setForm({ ...form, blood_group: e.target.value })}>{BLOOD_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}</select></label>
          <label className="field"><span>Units Required</span><input type="number" min={1} value={form.units_required} onChange={(e) => setForm({ ...form, units_required: Number(e.target.value) })} required /></label>
          <label className="field"><span>Hospital Name</span><input value={form.hospital_name} onChange={(e) => setForm({ ...form, hospital_name: e.target.value })} required /></label>
          <label className="field"><span>Hospital Address</span><input value={form.hospital_address} onChange={(e) => setForm({ ...form, hospital_address: e.target.value })} required /></label>
          <label className="field"><span>City</span><input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required /></label>
          <label className="field"><span>Required Date</span><input type="date" value={form.required_at} onChange={(e) => setForm({ ...form, required_at: e.target.value })} required /></label>
          <label className="field"><span>Required Time</span><input type="time" value={form.required_time} onChange={(e) => setForm({ ...form, required_time: e.target.value })} required /></label>
          <label className="field"><span>Urgency</span><select value={form.urgency} onChange={(e) => setForm({ ...form, urgency: e.target.value })}><option>Normal</option><option>Urgent</option><option>Emergency</option></select></label>
          <label className="field"><span>Contact Person</span><input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} required /></label>
          <label className="field"><span>Contact Number</span><input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} required /></label>
          <label className="field full-span"><span>Additional Notes</span><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>

          {error ? <div className="error-box full-span">{error}</div> : null}
          {success ? <div className="success-box full-span">{success}</div> : null}

          <div className="button-row full-span">
            <button type="submit" className="primary-button" disabled={loading}>{loading ? 'Submitting...' : 'Submit Request'}</button>
            <button type="button" className="secondary-button" onClick={() => navigateTo('/requests/my')}>Cancel</button>
          </div>
          {requestId ? <div className="muted-text full-span">Request ID: {requestId}</div> : null}
        </form>
      </div>
    </DashboardLayout>
  );
}

function RequestsListPage({ user }: { user: AppUser }) {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'pending' | 'active' | 'fulfilled' | 'cancelled'>('all');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/requests`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to load requests');
        const data = await response.json();
        setRequests(Array.isArray(data) ? data : []);
      })
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = requests.filter((request) => {
    if (filter === 'all') return true;
    if (filter === 'pending') return request.status === 'submitted' || request.status === 'verified';
    if (filter === 'active') return !['fulfilled', 'cancelled'].includes(request.status || '');
    if (filter === 'fulfilled') return request.status === 'fulfilled';
    if (filter === 'cancelled') return request.status === 'cancelled';
    return true;
  });

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="My Requests">
      <div className="panel-block">
        <div className="toolbar-row">
          <div className="filter-row">
            {['all', 'pending', 'active', 'fulfilled', 'cancelled'].map((key) => (
              <button key={key} className={filter === key ? 'chip active' : 'chip'} onClick={() => setFilter(key as any)}>
                {key}
              </button>
            ))}
          </div>
          <button className="primary-button" onClick={() => navigateTo('/requests/create')}>New Request</button>
        </div>

        {loading ? <LoadingState message="Loading your requests..." /> : filtered.length === 0 ? <EmptyState message="No requests match the selected filter." /> : (
          <div className="card-list">
            {filtered.map((request) => (
              <button key={request.id} className="request-card" onClick={() => navigateTo(`/requests/${request.id}`)}>
                <div>
                  <strong>{request.request_code || `BCR-${request.id}`}</strong>
                  <small>{request.hospital_name || 'Hospital not set'}</small>
                </div>
                <div className="request-meta">
                  <span>{request.blood_group}</span>
                  <span>{request.units_required} units</span>
                  <span>{request.urgency}</span>
                </div>
                <div className="right-meta">
                  <StatusBadge text={request.status || 'submitted'} />
                  <small>{request.created_at ? new Date(request.created_at).toLocaleDateString() : ''}</small>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function RequestDetailPage({ user, requestId }: { user: AppUser; requestId: number }) {
  const [request, setRequest] = useState<RequestItem | null>(null);
  const [requestMap, setRequestMap] = useState<{ request: { latitude?: number | null; longitude?: number | null; hospital_name: string; city: string }; potential_donors: number; accepted_donors: number } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/requests/${requestId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Request not found');
        const data = await response.json();
        setRequest(data);
        const mapResponse = await fetch(`${API_BASE}/api/requests/${requestId}/requester-map`, { headers: { Authorization: `Bearer ${token}` } });
        if (mapResponse.ok) setRequestMap(await mapResponse.json());
      })
      .catch(() => setRequest(null))
      .finally(() => setLoading(false));
  }, [requestId]);

  const stages = ['submitted', 'verified', 'donor_accepted', 'fulfilled'];
  const currentStage = request?.status || 'submitted';
  const stageIndex = Math.max(0, stages.indexOf(currentStage));

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title={request ? request.request_code || `Request ${request.id}` : 'Request Details'}>
      <div className="panel-block">
        {loading ? <LoadingState message="Loading request details..." /> : !request ? <EmptyState message="This request could not be loaded." /> : (
          <>
            <div className="detail-grid">
              <div>
                <p className="eyebrow">Request information</p>
                <h3>{request.patient_reference}</h3>
                <div className="info-stack compact">
                  <div className="info-row"><span>Request code</span><strong>{request.request_code}</strong></div>
                  <div className="info-row"><span>Blood group</span><strong>{request.blood_group}</strong></div>
                  <div className="info-row"><span>Units required</span><strong>{request.units_required}</strong></div>
                  <div className="info-row"><span>Urgency</span><strong>{request.urgency}</strong></div>
                  <div className="info-row"><span>Hospital</span><strong>{request.hospital_name}</strong></div>
                  <div className="info-row"><span>Address</span><strong>{request.hospital_address}</strong></div>
                  <div className="info-row"><span>City</span><strong>{request.city}</strong></div>
                  <div className="info-row"><span>Required</span><strong>{request.required_at ? new Date(request.required_at).toLocaleString() : 'Not set'}</strong></div>
                  <div className="info-row"><span>Contact</span><strong>{request.contact_name} • {request.contact_phone}</strong></div>
                </div>
              </div>

              <div>
                <p className="eyebrow">Lifecycle</p>
                <div className="timeline">
                  {stages.map((stage, index) => (
                    <div key={stage} className={index <= stageIndex ? 'timeline-step active' : 'timeline-step'}>
                      <span>{stage.replace('_', ' ')}</span>
                    </div>
                  ))}
                </div>
                <div className="info-stack compact">
                  <div className="info-row"><span>Status</span><strong><StatusBadge text={request.status || 'submitted'} /></strong></div>
                  <div className="info-row"><span>Notes</span><strong>{request.notes || 'No additional notes.'}</strong></div>
                </div>
              </div>
            </div>
            {requestMap ? <section className="panel-block map-section">
              <h4>Request Location</h4>
              <CoordinationMap request={requestMap.request} />
              <div className="map-aggregate"><span>Potential donors found: {requestMap.potential_donors}</span><span>Accepted donors: {requestMap.accepted_donors}</span></div>
            </section> : null}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

function DonorRequestsPage({ user }: { user: AppUser }) {
  const [requests, setRequests] = useState<DonorMatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/donors/me/matches`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load matched requests');
        const data = await response.json();
        setRequests(Array.isArray(data) ? data : []);
      })
      .catch((err) => { setRequests([]); setError(err instanceof Error ? err.message : 'Could not load matched requests'); })
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Blood Requests">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading matched requests..." /> : error ? <div className="error-box">{error}</div> : requests.length === 0 ? <EmptyState message="No matching blood requests are currently available." /> : (
          <div className="card-list">
            {requests.map((request) => (
              <div key={request.match_id} className="request-card">
                <div>
                  <strong>{request.request_code}</strong>
                  <small>{request.hospital_name}</small>
                </div>
                <div className="request-meta">
                  <span>{request.blood_group_required}</span>
                  <span>{request.units_required} units</span>
                  <span>{request.city}</span>
                </div>
                <div className="right-meta">
                  <StatusBadge text={request.donor_response_status} />
                  <small>{request.distance_km == null ? 'Distance unavailable' : `${request.distance_km} km`} • {request.urgency}</small>
                  <div className="inline-actions">
                    <button className="secondary-button" onClick={() => navigateTo(`/donor/requests/${request.request_id}`)}>View</button>
                    {request.donor_response_status === 'pending' ? <>
                      <button className="primary-button" onClick={() => respondToRequest(request.request_id, 'accepted')}>Accept</button>
                      <button className="secondary-button" onClick={() => respondToRequest(request.request_id, 'declined')}>Decline</button>
                    </> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function DonorRequestDetailPage({ user, requestId }: { user: AppUser; requestId: number }) {
  const [request, setRequest] = useState<DonorMatchItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/donors/me/matches/${requestId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Matched request not found');
        const data = await response.json();
        setRequest(data);
      })
      .catch(() => setRequest(null))
      .finally(() => setLoading(false));
  }, [requestId]);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Donor Request Details">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading matched request details..." /> : !request ? <EmptyState message="This request is unavailable to you." /> : (
          <>
            <div className="detail-grid">
              <div>
                  <h3>{request.request_code}</h3>
                <div className="info-stack compact">
                  <div className="info-row"><span>Required blood group</span><strong>{request.blood_group_required}</strong></div>
                  <div className="info-row"><span>Units</span><strong>{request.units_required}</strong></div>
                  <div className="info-row"><span>Hospital</span><strong>{request.hospital_name}</strong></div>
                  <div className="info-row"><span>City / area</span><strong>{request.city}</strong></div>
                  <div className="info-row"><span>Urgency</span><strong>{request.urgency}</strong></div>
                  <div className="info-row"><span>Required</span><strong>{request.required_at ? new Date(request.required_at).toLocaleString() : 'Not set'}</strong></div>
                  <div className="info-row"><span>Distance</span><strong>{request.distance_km == null ? 'Unavailable' : `${request.distance_km} km`}</strong></div>
                  <div className="info-row"><span>Request status</span><strong>{request.request_status}</strong></div>
                </div>
                <CoordinationMap request={{ latitude: request.request_latitude, longitude: request.request_longitude, hospital_name: request.hospital_name, city: request.city }} />
              </div>

              <div className="info-box">
                <p>BloodConnect identifies potentially compatible donors for coordination. Final donor eligibility and blood compatibility must be confirmed by qualified healthcare professionals or an authorized blood bank.</p>
                <div className="button-row">
                  {request.donor_response_status === 'pending' ? <>
                    <button className="primary-button" onClick={() => respondToRequest(request.request_id, 'accepted')}>Accept Request</button>
                    <button className="secondary-button" onClick={() => respondToRequest(request.request_id, 'declined')}>Decline Request</button>
                  </> : <StatusBadge text={request.donor_response_status} />}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

function DonorAcceptedPage({ user }: { user: AppUser }) {
  const [items, setItems] = useState<DonorHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    fetch(`${API_BASE}/api/donors/me/accepted`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Unable to load accepted requests'); return response.json(); })
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Accepted Requests">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading accepted requests..." /> : items.length === 0 ? <EmptyState message="No requests have been accepted by this donor yet." /> : (
          <div className="card-list">{items.map((item) => <div key={item.request_id} className="request-card">
            <div><strong>{item.request_code}</strong><small>{item.hospital_name}</small></div>
            <div className="request-meta"><span>{item.blood_group}</span><span>{item.city}</span><span>{item.urgency}</span></div>
            <div className="right-meta"><StatusBadge text={item.request_status} /><small>{item.response_timestamp ? new Date(item.response_timestamp).toLocaleString() : 'Recently'}</small></div>
          </div>)}</div>
        )}
      </div>
    </DashboardLayout>
  );
}

function DonorHistoryPage({ user }: { user: AppUser }) {
  const [items, setItems] = useState<DonorHistoryItem[]>([]);
  const [filter, setFilter] = useState<'all' | 'accepted' | 'declined'>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    fetch(`${API_BASE}/api/donors/me/history`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Unable to load donor history'); return response.json(); })
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = items.filter((item) => filter === 'all' || item.response === filter);
  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Donor History">
      <div className="panel-block">
        <div className="filter-row">
          {(['all', 'accepted', 'declined'] as const).map((key) => <button key={key} className={filter === key ? 'chip active' : 'chip'} onClick={() => setFilter(key)}>{key}</button>)}
        </div>
        {loading ? <LoadingState message="Loading response history..." /> : filtered.length === 0 ? <EmptyState message="No donor responses match this filter." /> : (
          <div className="card-list">{filtered.map((item) => <div key={`${item.request_id}-${item.response}`} className="request-card">
            <div><strong>{item.request_code}</strong><small>{item.hospital_name}</small></div>
            <div className="request-meta"><span>{item.blood_group}</span><span>{item.city}</span></div>
            <div className="right-meta"><StatusBadge text={item.response} /><small>{item.response_timestamp ? new Date(item.response_timestamp).toLocaleString() : 'Recently'} • {item.request_status}</small></div>
          </div>)}</div>
        )}
      </div>
    </DashboardLayout>
  );
}

function VolunteerAssignedPage({ user }: { user: AppUser }) {
  const [assignments, setAssignments] = useState<VolunteerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(`${API_BASE}/api/volunteers/me/assignments`, { headers: { Authorization: `Bearer ${getStoredToken()}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Unable to load assignments'); return response.json(); })
      .then((data) => setAssignments(Array.isArray(data) ? data : []))
      .catch(() => setAssignments([]))
      .finally(() => setLoading(false));
  }, []);
  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Assigned Requests">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading assignments..." /> : assignments.length === 0 ? <EmptyState message="No requests are currently assigned to you." /> : <div className="card-list">{assignments.map((assignment) => <button key={assignment.id} className="request-card" onClick={() => navigateTo(`/volunteer/requests/${assignment.request_id}`)}><div><strong>{assignment.request_code}</strong><small>{assignment.hospital_name} • {assignment.city}</small></div><StatusBadge text={assignment.status} /></button>)}</div>}
      </div>
    </DashboardLayout>
  );
}

function VolunteerRequestsPage({ user }: { user: AppUser }) {
  const [assignments, setAssignments] = useState<VolunteerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [urgency, setUrgency] = useState('all');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/volunteers/me/assignments`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load assignments');
        const data = await response.json();
        setAssignments(Array.isArray(data) ? data : []);
      })
      .catch(() => setAssignments([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = assignments.filter((assignment) => {
    const matchesSearch = !search || (assignment.request_code || '').toLowerCase().includes(search.toLowerCase()) || (assignment.hospital_name || '').toLowerCase().includes(search.toLowerCase());
    const matchesStatus = status === 'all' || assignment.status === status;
    const matchesUrgency = urgency === 'all' || assignment.urgency === urgency;
    return matchesSearch && matchesStatus && matchesUrgency;
  });

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Active Requests">
      <div className="panel-block">
        <div className="filter-row stack-on-mobile">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search request or hospital" />
          <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All statuses</option><option value="submitted">Submitted</option><option value="verified">Verified</option><option value="fulfilled">Fulfilled</option></select>
          <select value={urgency} onChange={(e) => setUrgency(e.target.value)}><option value="all">All urgencies</option><option value="Normal">Normal</option><option value="Urgent">Urgent</option><option value="Emergency">Emergency</option></select>
        </div>

        {loading ? <LoadingState message="Loading active volunteer requests..." /> : filtered.length === 0 ? <EmptyState message="No active coordination cases are currently available for this volunteer." /> : (
          <div className="card-list">
            {filtered.map((assignment) => (
              <button key={assignment.id} className="request-card" onClick={() => navigateTo(`/volunteer/requests/${assignment.request_id}`)}>
                <div><strong>{assignment.request_code || 'Request'}</strong><small>{assignment.hospital_name || 'Hospital not set'}</small></div>
                <div className="request-meta"><span>{assignment.blood_group}</span><span>{assignment.urgency}</span><span>{assignment.request_status}</span></div>
                <div className="right-meta"><StatusBadge text={assignment.status} /><small>{assignment.city}</small></div>
              </button>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function VolunteerRequestDetailPage({ user, requestId }: { user: AppUser; requestId: number }) {
  const [assignment, setAssignment] = useState<VolunteerAssignment | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/volunteers/me/assignments`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to load assignments');
        const data = await response.json();
        setAssignment((Array.isArray(data) ? data : []).find((item: VolunteerAssignment) => item.request_id === requestId) || null);
      })
      .catch(() => setAssignment(null))
      .finally(() => setLoading(false));
  }, [requestId]);

  const updateAssignment = async (status: VolunteerAssignment['status']) => {
    if (!assignment) return;
    const response = await fetch(`${API_BASE}/api/volunteers/me/assignments/${assignment.id}/status?status=${status}`, { method: 'PATCH', headers: { Authorization: `Bearer ${getStoredToken()}` } });
    if (response.ok) setAssignment(await response.json());
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Volunteer Request Details">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading assignment detail..." /> : !assignment ? <EmptyState message="This assignment is not available." /> : (
          <div className="detail-grid">
            <div>
              <h3>{assignment.request_code}</h3>
              <div className="info-stack compact">
                <div className="info-row"><span>Blood group</span><strong>{assignment.blood_group}</strong></div>
                <div className="info-row"><span>Units</span><strong>{assignment.units_required}</strong></div>
                <div className="info-row"><span>Hospital</span><strong>{assignment.hospital_name}</strong></div>
                <div className="info-row"><span>Address</span><strong>{assignment.hospital_address}</strong></div>
                <div className="info-row"><span>City</span><strong>{assignment.city}</strong></div>
                <div className="info-row"><span>Required</span><strong>{assignment.required_at ? new Date(assignment.required_at).toLocaleString() : 'Not set'}</strong></div>
                <div className="info-row"><span>Request status</span><strong>{assignment.request_status}</strong></div>
                <div className="info-row"><span>Assignment status</span><strong>{assignment.status}</strong></div>
              </div>
            </div>
            <div className="info-box"><p>Coordination information is provided for operational support. Medical eligibility and final compatibility must be confirmed by qualified healthcare professionals or an authorized blood bank.</p><p>{assignment.notes || 'No coordinator notes.'}</p><div className="button-row">
              {assignment.status === 'assigned' ? <button className="primary-button" onClick={() => void updateAssignment('accepted')}>Accept Assignment</button> : null}
              {assignment.status === 'accepted' ? <button className="primary-button" onClick={() => void updateAssignment('in_progress')}>Start Coordination</button> : null}
              {assignment.status === 'in_progress' ? <button className="primary-button" onClick={() => void updateAssignment('completed')}>Mark Completed</button> : null}
            </div></div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorVerificationPage({ user }: { user: AppUser }) {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadRequests = async () => {
    const token = getStoredToken();
    if (!token) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/requests`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error('Unable to load verification queue');
      setRequests(Array.isArray(data) ? data.filter((item) => item.status === 'submitted') : []);
    } catch {
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadRequests(); }, []);

  const verifyRequest = async (requestId: number) => {
    const token = getStoredToken();
    const response = await fetch(`${API_BASE}/api/requests/${requestId}/verify`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) {
      alert('Could not verify this request.');
      return;
    }
    await loadRequests();
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Pending Verification">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading verification queue..." /> : requests.length === 0 ? <EmptyState message="No submitted requests are awaiting verification." /> : (
          <div className="card-list">
            {requests.map((request) => (
              <div key={request.id} className="request-card">
                <div><strong>{request.request_code || `BCR-${request.id}`}</strong><small>{request.hospital_name}</small></div>
                <div className="request-meta"><span>{request.blood_group}</span><span>{request.units_required} units</span><span>{request.urgency}</span></div>
                <div className="right-meta"><StatusBadge text={request.status || 'submitted'} /><div className="inline-actions"><button className="secondary-button" onClick={() => navigateTo(`/coordinator/requests/${request.id}`)}>View</button><button className="primary-button" onClick={() => void verifyRequest(request.id)}>Verify</button></div></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorRequestsPage({ user }: { user: AppUser }) {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/requests`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load requests');
        const data = await response.json();
        setRequests(Array.isArray(data) ? data : []);
      })
      .catch(() => setRequests([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Active Requests">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading active request log..." /> : requests.length === 0 ? <EmptyState message="No blood requests are currently available." /> : (
          <div className="card-list">
            {requests.map((request) => (
              <button key={request.id} className="request-card" onClick={() => navigateTo(`/coordinator/requests/${request.id}`)}>
                <div><strong>{request.request_code || `BCR-${request.id}`}</strong><small>{request.hospital_name || 'Hospital not set'}</small></div>
                <div className="request-meta"><span>{request.blood_group}</span><span>{request.units_required} units</span><span>{request.urgency}</span></div>
                <div className="right-meta"><StatusBadge text={request.status || 'submitted'} /><small>{request.created_at ? new Date(request.created_at).toLocaleDateString() : ''}</small></div>
              </button>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorRequestDetailPage({ user, requestId }: { user: AppUser; requestId: number }) {
  const [request, setRequest] = useState<RequestItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<MatchSummary | null>(null);
  const [coordinationMap, setCoordinationMap] = useState<CoordinationMapData | null>(null);
  const [assignments, setAssignments] = useState<VolunteerAssignment[]>([]);
  const [volunteers, setVolunteers] = useState<ManagedVolunteer[]>([]);
  const [selectedVolunteer, setSelectedVolunteer] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadData = async () => {
    const token = getStoredToken();
    if (!token) return;
    setLoading(true);
    try {
      const requestResponse = await fetch(`${API_BASE}/api/requests/${requestId}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!requestResponse.ok) throw new Error('Request not found');
      setRequest(await requestResponse.json());
      const matchResponse = await fetch(`${API_BASE}/api/requests/${requestId}/matches`, { headers: { Authorization: `Bearer ${token}` } });
      if (matchResponse.ok) setSummary(await matchResponse.json());
      else setSummary(null);
      const mapResponse = await fetch(`${API_BASE}/api/requests/${requestId}/coordination-map`, { headers: { Authorization: `Bearer ${token}` } });
      if (mapResponse.ok) setCoordinationMap(await mapResponse.json());
      else setCoordinationMap(null);
      const [assignmentResponse, volunteerResponse] = await Promise.all([
        fetch(`${API_BASE}/api/volunteers/requests/${requestId}/assignments`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/api/donors/management/volunteers`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (assignmentResponse.ok) setAssignments(await assignmentResponse.json());
      if (volunteerResponse.ok) setVolunteers(await volunteerResponse.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load request details');
      setRequest(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [requestId]);

  const verifyRequest = async () => {
    if (!request || request.status !== 'submitted') return;
    setActionLoading(true);
    setError('');
    setMessage('');
    try {
      const response = await fetch(`${API_BASE}/api/requests/${requestId}/verify`, { method: 'POST', headers: { Authorization: `Bearer ${getStoredToken()}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to verify request');
      setMessage('Request verified successfully.');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to verify request');
    } finally {
      setActionLoading(false);
    }
  };

  const findDonors = async () => {
    setActionLoading(true);
    setError('');
    setMessage('');
    try {
      const response = await fetch(`${API_BASE}/api/requests/${requestId}/match`, { method: 'POST', headers: { Authorization: `Bearer ${getStoredToken()}` } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to find donors');
      if (!data.matched_count && (!request?.latitude || !request?.longitude)) throw new Error('Request location could not be resolved. Donor matching cannot be performed.');
      setMessage(`${data.matched_count} potential donors found.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to find donors');
    } finally {
      setActionLoading(false);
    }
  };

  const assignVolunteer = async () => {
    if (!selectedVolunteer) return;
    setActionLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/api/volunteers/requests/${requestId}/assignments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getStoredToken()}` },
        body: JSON.stringify({ volunteer_id: Number(selectedVolunteer) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to assign volunteer');
      setMessage('Volunteer assigned successfully.');
      setSelectedVolunteer('');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to assign volunteer');
    } finally {
      setActionLoading(false);
    }
  };

  const cancelAssignment = async (assignmentId: number) => {
    const response = await fetch(`${API_BASE}/api/volunteers/${assignmentId}/cancel`, { method: 'PATCH', headers: { Authorization: `Bearer ${getStoredToken()}` } });
    if (response.ok) await loadData();
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Coordinator Request Details">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading request details..." /> : error && !request ? <div className="error-box">{error}</div> : !request ? <EmptyState message="This request is unavailable." /> : (
          <div className="detail-grid">
            <div>
              <h3>{request.patient_reference}</h3>
              <div className="info-stack compact">
                <div className="info-row"><span>Request code</span><strong>{request.request_code}</strong></div>
                <div className="info-row"><span>Requester</span><strong>{request.contact_name || 'Requester not disclosed'}</strong></div>
                <div className="info-row"><span>Blood group</span><strong>{request.blood_group}</strong></div>
                <div className="info-row"><span>Units</span><strong>{request.units_required}</strong></div>
                <div className="info-row"><span>Hospital</span><strong>{request.hospital_name}</strong></div>
                <div className="info-row"><span>Location</span><strong>{request.city}</strong></div>
                <div className="info-row"><span>Urgency</span><strong>{request.urgency}</strong></div>
                <div className="info-row"><span>Status</span><strong>{request.status || 'submitted'}</strong></div>
              </div>
            </div>
            <div className="info-box">
              {message ? <div className="success-box">{message}</div> : null}
              {error ? <div className="error-box">{error}</div> : null}
              <h4>Matching Summary</h4>
              <div className="info-stack compact">
                <div className="info-row"><span>Potential donors</span><strong>{summary?.total_matches ?? 0}</strong></div>
                <div className="info-row"><span>Accepted</span><strong>{summary?.accepted_count ?? 0}</strong></div>
                <div className="info-row"><span>Declined</span><strong>{summary?.declined_count ?? 0}</strong></div>
                <div className="info-row"><span>Awaiting response</span><strong>{summary?.pending_responses ?? 0}</strong></div>
              </div>
              {summary?.matches.length ? <div className="card-list">{summary.matches.map((match) => <div key={match.match_id} className="list-item">
                <div><strong>{match.donor_name}</strong><small>{match.blood_group} • {match.area || match.city || 'Location unavailable'}</small></div>
                <span className="pill status-pill">{match.response_status} • {match.distance_km ?? 'N/A'} km</span>
              </div>)}</div> : <p className="muted-text">No potential donors have been matched.</p>}
              {coordinationMap ? <CoordinationMap request={coordinationMap.request} donors={coordinationMap.matched_donors} showDonors /> : null}
              <h4>Volunteer Coordination</h4>
              {volunteers.length ? <div className="button-row"><select value={selectedVolunteer} onChange={(event) => setSelectedVolunteer(event.target.value)}><option value="">Select volunteer</option>{volunteers.filter((volunteer) => volunteer.active).map((volunteer) => <option key={volunteer.volunteer_id} value={volunteer.volunteer_id}>{volunteer.name}</option>)}</select><button className="secondary-button" onClick={() => void assignVolunteer()} disabled={!selectedVolunteer || actionLoading}>Assign Volunteer</button></div> : <p className="muted-text">No active volunteer accounts are available.</p>}
              {assignments.length ? <div className="card-list">{assignments.map((assignment) => <div key={assignment.id} className="list-item"><div><strong>{assignment.volunteer_name}</strong><small>{assignment.status} • {assignment.notes || 'No coordinator notes'}</small></div>{!['completed', 'cancelled'].includes(assignment.status) ? <button className="secondary-button" onClick={() => void cancelAssignment(assignment.id)}>Cancel Assignment</button> : null}</div>)}</div> : <p className="muted-text">No volunteers assigned to this request.</p>}
              <div className="button-row">
                {request.status === 'submitted' ? <button className="primary-button" onClick={() => void verifyRequest()} disabled={actionLoading}>{actionLoading ? 'Verifying...' : 'Verify'}</button> : null}
                {request.status === 'verified' ? <button className="secondary-button" onClick={() => void findDonors()} disabled={actionLoading}>{actionLoading ? 'Finding...' : 'Find Potential Donors'}</button> : null}
                <button className="secondary-button" onClick={() => navigateTo(`/coordinator/requests`)}>Back to list</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorDonorsPage({ user }: { user: AppUser }) {
  const [donors, setDonors] = useState<ManagedDonor[]>([]);
  const [search, setSearch] = useState('');
  const [bloodGroup, setBloodGroup] = useState('');
  const [city, setCity] = useState('');
  const [available, setAvailable] = useState('');
  const [verified, setVerified] = useState('');
  const [loading, setLoading] = useState(true);

  const loadDonors = async () => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (bloodGroup) params.set('blood_group', bloodGroup);
    if (city) params.set('city', city);
    if (available) params.set('available', available);
    if (verified) params.set('verified', verified);
    try {
      const response = await fetch(`${API_BASE}/api/donors/management?${params}`, { headers: { Authorization: `Bearer ${getStoredToken()}` } });
      if (!response.ok) throw new Error('Unable to load donors');
      const data = await response.json();
      setDonors(Array.isArray(data) ? data : []);
    } catch { setDonors([]); }
    finally { setLoading(false); }
  };

  useEffect(() => { void loadDonors(); }, [search, bloodGroup, city, available, verified]);

  const setVerification = async (donor: ManagedDonor, nextValue: boolean) => {
    const response = await fetch(`${API_BASE}/api/donors/management/${donor.donor_id}/verification?verified=${nextValue}`, { method: 'PATCH', headers: { Authorization: `Bearer ${getStoredToken()}` } });
    if (response.ok) await loadDonors();
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Donor Management">
      <div className="panel-block">
        <div className="filter-row stack-on-mobile">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, city, or area" />
          <select value={bloodGroup} onChange={(event) => setBloodGroup(event.target.value)}><option value="">All blood groups</option>{BLOOD_GROUPS.map((group) => <option key={group}>{group}</option>)}</select>
          <input value={city} onChange={(event) => setCity(event.target.value)} placeholder="City" />
          <select value={available} onChange={(event) => setAvailable(event.target.value)}><option value="">All availability</option><option value="true">Available</option><option value="false">Unavailable</option></select>
          <select value={verified} onChange={(event) => setVerified(event.target.value)}><option value="">All verification</option><option value="true">Verified</option><option value="false">Unverified</option></select>
        </div>
        {loading ? <LoadingState message="Loading donor directory..." /> : donors.length === 0 ? <EmptyState message="No donors match the selected filters." /> : <div className="card-list">{donors.map((donor) => <div key={donor.donor_id} className="request-card">
          <div><strong>{donor.name}</strong><small>{donor.blood_group} • {donor.city} • {donor.area || 'Area unavailable'}</small></div>
          <div className="request-meta"><StatusBadge text={donor.available ? 'available' : 'unavailable'} /><StatusBadge text={donor.verified ? 'verified' : 'unverified'} /></div>
          <div className="inline-actions"><button className="secondary-button" onClick={() => void setVerification(donor, !donor.verified)}>{donor.verified ? 'Revoke Verification' : 'Verify Donor'}</button></div>
        </div>)}</div>}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorVolunteersPage({ user }: { user: AppUser }) {
  const [volunteers, setVolunteers] = useState<ManagedVolunteer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/donors/management/volunteers`, { headers: { Authorization: `Bearer ${getStoredToken()}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Unable to load volunteers'); return response.json(); })
      .then((data) => setVolunteers(Array.isArray(data) ? data : []))
      .catch(() => setVolunteers([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Volunteer Management">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading volunteer accounts..." /> : volunteers.length === 0 ? <EmptyState message="No volunteer accounts are available." /> : <div className="card-list">{volunteers.map((volunteer) => <div key={volunteer.volunteer_id} className="request-card">
          <div><strong>{volunteer.name}</strong><small>{volunteer.city || 'City unavailable'} • {volunteer.area || 'Area unavailable'}</small></div>
          <StatusBadge text={volunteer.active ? 'active' : 'inactive'} />
        </div>)}</div>}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorCampaignsPage({ user }: { user: AppUser }) {
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/campaigns/management/all`, { headers: { Authorization: `Bearer ${getStoredToken()}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Unable to load campaigns'); return response.json(); })
      .then((data) => setCampaigns(Array.isArray(data) ? data : []))
      .catch(() => setCampaigns([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Campaigns">
      <div className="panel-block">
        <div className="toolbar-row"><span className="muted-text">Coordinator campaign management</span><button className="primary-button" onClick={() => navigateTo('/coordinator/campaigns/create')}>Create Campaign</button></div>
        {loading ? <LoadingState message="Loading campaigns..." /> : campaigns.length === 0 ? <EmptyState message="No campaigns have been created yet." /> : <div className="card-list">{campaigns.map((campaign) => <button key={campaign.id} className="request-card" onClick={() => navigateTo(`/coordinator/campaigns/${campaign.id}`)}><div><strong>{campaign.title}</strong><small>{campaign.location} • {new Date(campaign.campaign_date).toLocaleString()}</small></div><StatusBadge text={campaign.status} /></button>)}</div>}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorCampaignCreatePage({ user }: { user: AppUser }) {
  const [form, setForm] = useState({ title: '', description: '', location: '', campaign_date: '' });
  const [error, setError] = useState('');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/api/campaigns`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getStoredToken()}` }, body: JSON.stringify(form) });
    if (!response.ok) { const data = await response.json(); setError(data.detail || 'Unable to create campaign'); return; }
    const campaign = await response.json();
    navigateTo(`/coordinator/campaigns/${campaign.id}`);
  };
  return <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Create Campaign"><div className="panel-block"><form className="form-grid" onSubmit={submit}><label className="field"><span>Title</span><input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label><label className="field"><span>Location</span><input required value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></label><label className="field"><span>Date and time</span><input required type="datetime-local" value={form.campaign_date} onChange={(e) => setForm({ ...form, campaign_date: e.target.value })} /></label><label className="field full-span"><span>Description</span><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>{error ? <div className="error-box full-span">{error}</div> : null}<button className="primary-button full-span">Create Campaign</button></form></div></DashboardLayout>;
}

function CoordinatorCampaignDetailPage({ user, campaignId }: { user: AppUser; campaignId: number }) {
  const [campaign, setCampaign] = useState<CampaignItem | null>(null);
  useEffect(() => { fetch(`${API_BASE}/api/campaigns/management/all`, { headers: { Authorization: `Bearer ${getStoredToken()}` } }).then((response) => response.json()).then((data) => setCampaign((data as CampaignItem[]).find((item) => item.id === campaignId) || null)).catch(() => setCampaign(null)); }, [campaignId]);
  const setStatus = async (status: string) => { const response = await fetch(`${API_BASE}/api/campaigns/${campaignId}/status?status=${status}`, { method: 'PATCH', headers: { Authorization: `Bearer ${getStoredToken()}` } }); if (response.ok) setCampaign(await response.json()); };
  return <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Campaign Details"><div className="panel-block">{!campaign ? <LoadingState message="Loading campaign..." /> : <><h3>{campaign.title}</h3><p>{campaign.description || 'No description.'}</p><div className="info-stack compact"><div className="info-row"><span>Location</span><strong>{campaign.location}</strong></div><div className="info-row"><span>Date</span><strong>{new Date(campaign.campaign_date).toLocaleString()}</strong></div><div className="info-row"><span>Status</span><strong>{campaign.status}</strong></div></div><div className="button-row">{campaign.status === 'planned' ? <button className="primary-button" onClick={() => void setStatus('published')}>Publish</button> : null}{campaign.status === 'published' ? <button className="secondary-button" onClick={() => void setStatus('completed')}>Mark Completed</button> : null}{!['completed', 'cancelled'].includes(campaign.status) ? <button className="secondary-button" onClick={() => void setStatus('cancelled')}>Cancel</button> : null}</div></>}</div></DashboardLayout>;
}

function PublicCampaignsPage() {
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([]);
  useEffect(() => { fetch(`${API_BASE}/api/campaigns`).then((response) => response.json()).then((data) => setCampaigns(Array.isArray(data) ? data : [])).catch(() => setCampaigns([])); }, []);
  return <PageShell><PublicHeader /><div className="content-article"><h2>Published Campaigns</h2>{campaigns.length === 0 ? <EmptyState message="No published campaigns are available." /> : <div className="card-list">{campaigns.map((campaign) => <button key={campaign.id} className="request-card" onClick={() => navigateTo(`/campaigns/${campaign.id}`)}><div><strong>{campaign.title}</strong><small>{campaign.location} • {new Date(campaign.campaign_date).toLocaleString()}</small></div><StatusBadge text={campaign.status} /></button>)}</div>}</div></PageShell>;
}

function PublicCampaignDetailPage({ campaignId }: { campaignId: number }) {
  const [campaign, setCampaign] = useState<CampaignItem | null>(null);
  useEffect(() => { fetch(`${API_BASE}/api/campaigns/${campaignId}`).then((response) => response.ok ? response.json() : null).then(setCampaign).catch(() => setCampaign(null)); }, [campaignId]);
  return <PageShell><PublicHeader /><div className="content-article">{!campaign ? <EmptyState message="Published campaign not found." /> : <><h2>{campaign.title}</h2><p>{campaign.description || 'No description.'}</p><p>{campaign.location} • {new Date(campaign.campaign_date).toLocaleString()}</p></>}</div></PageShell>;
}

function CoordinatorAnalyticsPage({ user }: { user: AppUser }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch(`${API_BASE}/api/coordinator/analytics`, { headers: { Authorization: `Bearer ${getStoredToken()}` } }).then((response) => response.json()).then(setData).catch(() => setData(null)); }, []);
  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Analytics">
      <div className="panel-block">
        {!data ? <LoadingState message="Loading analytics..." /> : <div className="info-stack"><div className="info-row"><span>Total requests</span><strong>{data.requests.total}</strong></div><div className="info-row"><span>Verified requests</span><strong>{data.requests.verified}</strong></div><div className="info-row"><span>Fulfilled requests</span><strong>{data.requests.fulfilled}</strong></div><div className="info-row"><span>Registered donors</span><strong>{data.donors.registered}</strong></div><div className="info-row"><span>Volunteers</span><strong>{data.volunteers.total}</strong></div><div className="info-row"><span>Active assignments</span><strong>{data.assignments.active}</strong></div><div className="info-row"><span>Published campaigns</span><strong>{data.campaigns.published}</strong></div></div>}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorReportsPage({ user }: { user: AppUser }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => { fetch(`${API_BASE}/api/coordinator/reports`, { headers: { Authorization: `Bearer ${getStoredToken()}` } }).then((response) => response.json()).then(setData).catch(() => setData(null)); }, []);
  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Reports">
      <div className="panel-block">
        {!data ? <LoadingState message="Loading reports..." /> : <div className="card-list"><div className="panel-block"><h4>Recent Blood Requests</h4><p>{data.recent_requests.length} records</p></div><div className="panel-block"><h4>Fulfilled Requests</h4><p>{data.fulfilled_requests.length} records</p></div><div className="panel-block"><h4>Donor Responses</h4><p>{data.donor_responses.length} records</p></div><div className="panel-block"><h4>Volunteer Activity</h4><p>{data.volunteer_activity.length} records</p></div><div className="panel-block"><h4>Campaign Activity</h4><p>{data.campaign_activity.length} records</p></div></div>}
      </div>
    </DashboardLayout>
  );
}

function CoordinatorAuditPage({ user }: { user: AppUser }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/audit-logs`, { headers: { Authorization: `Bearer ${getStoredToken()}` } })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to load audit logs');
        return response.json();
      })
      .then((data) => setItems(Array.isArray(data.items) ? data.items : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Audit Logs">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading audit logs..." /> : items.length === 0 ? <EmptyState message="No audit events found." /> : <div className="card-list">{items.map((item) => <div key={item.id} className="request-card"><div><strong>{item.action}</strong><small>{item.entity_type} • {item.entity_id}</small></div><div className="request-meta"><span>{new Date(item.created_at).toLocaleString()}</span><span>Actor: {item.actor_user_id ?? 'system'}</span></div>{item.metadata ? <p className="muted-text">{item.metadata}</p> : null}</div>)}</div>}
      </div>
    </DashboardLayout>
  );
}

function NotificationsPage({ user }: { user: AppUser }) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadNotifications = async () => {
    const token = getStoredToken();
    if (!token) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/notifications`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error('Unable to load notifications');
      const data = await response.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load notifications');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadNotifications();
  }, []);

  const markRead = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      await fetch(`${API_BASE}/api/notifications/${notification.id}/read`, { method: 'PATCH', headers: { Authorization: `Bearer ${getStoredToken()}` } });
      setItems((current) => current.map((item) => item.id === notification.id ? { ...item, is_read: true } : item));
      window.dispatchEvent(new Event('notifications-updated'));
    }
    if (!notification.related_entity_id) return;
    if (user.role === 'donor') navigateTo(`/donor/requests/${notification.related_entity_id}`);
    else if (user.role === 'coordinator') navigateTo(`/coordinator/requests/${notification.related_entity_id}`);
    else if (user.role === 'requester') navigateTo(`/requests/${notification.related_entity_id}`);
  };

  const markAllRead = async () => {
    await fetch(`${API_BASE}/api/notifications/read-all`, { method: 'PATCH', headers: { Authorization: `Bearer ${getStoredToken()}` } });
    setItems((current) => current.map((item) => ({ ...item, is_read: true })));
    window.dispatchEvent(new Event('notifications-updated'));
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Notifications">
      <div className="panel-block">
        {loading ? <LoadingState message="Loading notifications..." /> : error ? <div className="error-box">{error}</div> : items.length === 0 ? <EmptyState message="No notifications yet." /> : (
          <>
          <div className="toolbar-row"><span className="muted-text">{items.filter((item) => !item.is_read).length} unread</span><button className="secondary-button" onClick={() => void markAllRead()}>Mark all as read</button></div>
          <div className="card-list">
            {items.map((item) => (
              <button key={item.id} className={item.is_read ? 'notification-item read' : 'notification-item'} onClick={() => void markRead(item)}>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                </div>
                <small>{item.created_at ? new Date(item.created_at).toLocaleString() : 'Recently'}</small>
              </button>
            ))}
          </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

function ProfilePage({ user }: { user: AppUser }) {
  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Profile">
      <div className="panel-block">
        <div className="detail-grid">
          <div>
            <div className="info-stack compact">
              <div className="info-row"><span>Full Name</span><strong>{user.full_name}</strong></div>
              <div className="info-row"><span>Email</span><strong>{user.email}</strong></div>
              <div className="info-row"><span>Phone</span><strong>{user.phone}</strong></div>
              <div className="info-row"><span>Role</span><strong>{user.role}</strong></div>
            </div>
          </div>
          <div className="info-box">
            <p>Role-specific details are surfaced on the relevant dashboard. Donors should use the dedicated donor profile page to manage their availability and profile details.</p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function AiAssistantPage({ user }: { user: AppUser }) {
  const [message, setMessage] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    const text = message.trim();
    if (!text) return;
    setLoading(true);
    setError('');
    setResponse('');
    try {
      const response = await fetch(`${API_BASE}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getStoredToken()}` },
        body: JSON.stringify({ message: text }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to get assistance');
      setResponse(data.response || 'No response available.');
      setMessage('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to get assistance');
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="BloodConnect AI Assistant">
      <div className="panel-block">
        <p className="muted-text">Get help using BloodConnect, understanding the blood-request process, and supporting NSS awareness activities.</p>
        <div className="ai-box">
          <div className="ai-message">{response || 'AI assistance will be enabled when the configured AI service is connected.'}</div>
          {error ? <div className="error-box">{error}</div> : null}
        </div>
        <div className="message-box-row">
          <input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask a BloodConnect question" />
          <button className="primary-button" type="button" onClick={() => void submit()} disabled={loading || !message.trim()}>{loading ? 'Sending...' : 'Send'}</button>
        </div>
      </div>
    </DashboardLayout>
  );
}

function AboutPage() {
  return (
    <PageShell>
      <PublicHeader />
      <div className="content-article">
        <h2>About NSS BloodConnect</h2>
        <p>BloodConnect is an NSS-led coordination platform designed to help communities request blood quickly, identify suitable donors, track verification, and coordinate safe responses with clear accountability.</p>
        <p>Requesters can create a blood request, volunteers can support coordination, and coordinators can verify requests and manage donor response activity. Donors can manage their profile, indicate availability, and respond to requests when they are able to help.</p>
        <p>Privacy is protected by limiting access to authorized data and by avoiding unnecessary disclosure of private donor information. Medical eligibility and compatibility decisions remain responsibilities of qualified healthcare professionals and authorized blood banks.</p>
      </div>
    </PageShell>
  );
}

function AwarenessPage() {
  return (
    <PageShell>
      <PublicHeader />
      <div className="content-article">
        <h2>Why Blood Donation Matters</h2>
        <p>Regular blood donation supports patients who need transfusions due to surgery, trauma, chronic illness, or emergencies. A coordinated platform helps reduce delays and improves community support during urgent moments.</p>
        <h3>Blood Donation Process</h3>
        <ul>
          <li>Register with the donor profile.</li>
          <li>Confirm your availability.</li>
          <li>Respond when a request is relevant and safe for you.</li>
          <li>Coordinate with NSS volunteers and authorized clinical teams.</li>
        </ul>
        <h3>General Safety Information</h3>
        <p>Blood donation safety depends on screening, medical checks, and clear guidance from qualified health professionals or authorized blood banks.</p>
        <h3>When to Consult Healthcare Professionals</h3>
        <p>Anyone unsure about eligibility, medical history, current health, or recovery after a procedure should consult a qualified healthcare professional or authorized blood bank before donating.</p>
        <p>BloodConnect provides general awareness and coordination support. Medical eligibility to donate blood must be determined by qualified healthcare professionals or authorized blood banks.</p>
      </div>
    </PageShell>
  );
}

function UnauthorizedPage() {
  return (
    <PageShell>
      <PublicHeader />
      <div className="content-article narrow-card">
        <h2>You don't have permission to access this page.</h2>
        <button className="primary-button" onClick={() => navigateTo('/')}>Back to Home</button>
      </div>
    </PageShell>
  );
}

function NotFoundPage() {
  return (
    <PageShell>
      <PublicHeader />
      <div className="content-article narrow-card">
        <h2>Page not found.</h2>
        <button className="primary-button" onClick={() => navigateTo('/')}>Back to Home</button>
      </div>
    </PageShell>
  );
}

function PublicHeader() {
  return (
    <header className="topbar public-topbar">
      <div className="brand-block">
        <span className="brand-mark">NSS</span>
        <div>
          <p className="eyebrow">Blood donation coordination</p>
          <h1>NSS BloodConnect</h1>
        </div>
      </div>
      <nav className="public-actions">
        <button className="secondary-button" onClick={() => navigateTo('/about')}>About</button>
        <button className="secondary-button" onClick={() => navigateTo('/awareness')}>Awareness</button>
        <button className="primary-button" onClick={() => navigateTo('/login')}>Sign In</button>
      </nav>
    </header>
  );
}

async function respondToRequest(requestId: number, response: 'accepted' | 'declined') {
  const token = getStoredToken();
  if (!token) {
    navigateTo('/login');
    return;
  }

  const endpoint = response === 'accepted' ? `${API_BASE}/api/requests/${requestId}/accept` : `${API_BASE}/api/requests/${requestId}/decline`;
  const result = await fetch(endpoint, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!result.ok) {
    alert(response === 'accepted' ? 'This request could not be accepted.' : 'This request could not be declined.');
    return;
  }

  navigateTo(response === 'accepted' ? '/donor/accepted' : '/donor/history');
}

function throwingError(data: any, fallback: string) {
  throw new Error(data?.detail || fallback);
}

function PageShell({ children }: { children: React.ReactNode }) {
  return <div className="page-shell">{children}</div>;
}

function LoadingState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

function StatusCard({ label, value, tone = 'neutral' }: { label: string; value: string; tone?: 'neutral' | 'success' }) {
  return (
    <div className={tone === 'success' ? 'status-card success' : 'status-card'}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusBadge({ text }: { text: string }) {
  return <span className="pill status-pill">{text}</span>;
}

export default App;
