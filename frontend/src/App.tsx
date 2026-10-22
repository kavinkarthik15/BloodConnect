import { FormEvent, useEffect, useState } from 'react';
import CoordinationMap from './components/maps/CoordinationMap';
import { resolveAsyncState } from './asyncState.mjs';

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
  units_confirmed?: number;
  legacy_fulfillment_unverified?: boolean;
  escalation_status?: string;
  required_at?: string;
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
  request_latitude?: number | null;
  request_longitude?: number | null;
  request_status: string;
  distance_km?: number | null;
  match_score?: number;
  donor_response_status: 'pending' | 'accepted' | 'declined' | 'withdrawn';
  units_confirmed: number;
  escalation_status: string;
  response_timestamp?: string | null;
};

type DonorHistoryItem = {
  request_id: number;
  request_code: string;
  blood_group: string;
  hospital_name: string;
  city: string;
  urgency: string;
  units_required?: number;
  units_confirmed?: number;
  escalation_status?: string;
  response: 'accepted' | 'declined' | 'withdrawn';
  response_timestamp?: string;
  request_status: string;
};

type MatchSummary = {
  total_matches: number;
  pending_responses: number;
  accepted_count: number;
  declined_count: number;
  withdrawn_count?: number;
  matches: Array<{
    match_id: number;
    donor_id: number;
    donor_name: string;
    blood_group: string;
    city?: string;
    area?: string | null;
    distance_km?: number | null;
    match_score?: number;
    response_status: string;
    donation_confirmed: boolean;
    units_confirmed: number;
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
  units_confirmed?: number;
  hospital_name?: string;
  hospital_address?: string;
  city?: string;
  required_at?: string;
  urgency?: string;
  request_status?: string;
  escalation_status?: string;
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
const COOKIE_AUTH_ENABLED = import.meta.env.VITE_COOKIE_AUTH_ENABLED === 'true';
const TOKEN_KEY = 'nss-bloodconnect-token';
const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
let csrfToken: string | null = null;

async function fetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const method = (init.method || 'GET').toUpperCase();
  if (COOKIE_AUTH_ENABLED) {
    headers.delete('Authorization');
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && csrfToken) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }
  return globalThis.fetch(input, { ...init, headers, credentials: 'include' });
}

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

async function fetchProfile(token?: string): Promise<AppUser> {
  const headers = new Headers();
  if (!COOKIE_AUTH_ENABLED && token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers,
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
    const restoreSession = async () => {
      try {
        if (COOKIE_AUTH_ENABLED) {
          const csrfResponse = await fetch(`${API_BASE}/api/auth/csrf`);
          if (csrfResponse.ok) {
            csrfToken = (await csrfResponse.json()).csrf_token;
          }
          setAuthUser(await fetchProfile());
          return;
        }
        const token = getStoredToken();
        if (!token) {
          setAuthUser(null);
          return;
        }
        setAuthUser(await fetchProfile(token));
      } catch {
        localStorage.removeItem(TOKEN_KEY);
        setAuthUser(null);
      } finally {
        setAuthLoading(false);
      }
    };
    void restoreSession();
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

  const logout = async () => {
    try {
      const headers = new Headers();
      if (!COOKIE_AUTH_ENABLED) {
        const token = getStoredToken();
        if (token) headers.set('Authorization', `Bearer ${token}`);
      }
      const response = await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST', headers });
      if (!response.ok) {
        throw new Error('Sign out could not be confirmed.');
      }
    } catch {
      window.alert('Unable to confirm sign out. Please try again.');
      return;
    }
    localStorage.removeItem(TOKEN_KEY);
    csrfToken = null;
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
    if (route === '/forgot-password') return <ForgotPasswordPage />;
    if (route === '/reset-password') return <ResetPasswordPage />;
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
      if (route === '/coordinator/audit') return <CoordinatorAuditPage user={authUser} />;
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
          <span className="brand-mark" aria-hidden="true">NSS</span>
          <div>
            <p className="eyebrow">Blood donation coordination</p>
            <h1>NSS BloodConnect</h1>
          </div>
        </div>

        <nav className="public-actions" aria-label="Public navigation">
          <a className="text-nav-link" href="#how-it-works">How it works</a>
          <a className="text-nav-link" href="#roles">Roles</a>
          <a className="text-nav-link" href="#safety">Safety</a>
          <button className="secondary-button" onClick={() => navigateTo('/login')}>Sign In</button>
        </nav>
      </header>

      <main className="hero-layout">
        <section className="hero-copy">
          <p className="eyebrow accent">A clearer path from request to coordination</p>
          <h2>When blood is needed, help people coordinate the next step.</h2>
          <p className="hero-description">NSS BloodConnect brings requesters, potential donors, volunteers, and coordinators into one accountable workflow. Every donor response is an opportunity to coordinate—not a promise of availability or clinical compatibility.</p>
          <div className="cta-row">
            <button className="primary-button" onClick={() => navigateTo('/register?role=requester')}>Request Blood</button>
            <button className="secondary-button" onClick={() => navigateTo('/register?role=donor')}>Become a Donor</button>
          </div>
          <p className="hero-assurance"><span className="assurance-mark" aria-hidden="true">i</span> Donor eligibility and blood compatibility must be confirmed by qualified healthcare professionals or an authorized blood bank.</p>
        </section>

        <aside className="hero-card" id="how-it-works">
          <p className="eyebrow">A coordinated process</p>
          <h3>What happens next</h3>
          <ol className="process-list">
            <li><span>01</span><div><strong>Submit a request</strong><small>Share the request and timing details.</small></div></li>
            <li><span>02</span><div><strong>Coordinator reviews</strong><small>Authorized coordinators review requests.</small></div></li>
            <li><span>03</span><div><strong>Potential donors respond</strong><small>Responses are offers to coordinate.</small></div></li>
            <li><span>04</span><div><strong>Track confirmed outcomes</strong><small>Donation outcomes are recorded separately.</small></div></li>
          </ol>
        </aside>
      </main>

      <section className="public-section" id="roles" aria-labelledby="roles-heading">
        <div className="section-heading">
          <p className="eyebrow">Working together</p>
          <h2 id="roles-heading">A shared process, with clear roles</h2>
          <p>Each person has a focused role in moving a request through coordination safely and transparently.</p>
        </div>
        <div className="role-grid">
          <article className="role-card"><span className="role-index">01</span><h3>Requesters</h3><p>Submit a request and follow its progress, including requested and confirmed units.</p></article>
          <article className="role-card"><span className="role-index">02</span><h3>Donors</h3><p>Manage availability and respond to matched opportunities when able.</p></article>
          <article className="role-card"><span className="role-index">03</span><h3>Volunteers</h3><p>Support coordination for requests assigned by an authorized coordinator.</p></article>
          <article className="role-card"><span className="role-index">04</span><h3>Coordinators</h3><p>Review requests, coordinate responses, and record verified outcomes.</p></article>
        </div>
      </section>

      <section className="public-section public-section-soft" id="safety" aria-labelledby="safety-heading">
        <div className="awareness-panel">
          <div>
            <p className="eyebrow">Awareness and safety</p>
            <h2 id="safety-heading">Coordination supports care. It does not replace it.</h2>
            <p>BloodConnect does not determine donor eligibility, clinical compatibility, or whether a transfusion should occur. Please contact qualified healthcare professionals or an authorized blood bank for medical advice and urgent care.</p>
          </div>
          <aside className="guidance-card">
            <h3>Need emergency medical help?</h3>
            <p>Contact local emergency services and the treating hospital or authorized blood bank directly. This platform cannot guarantee donor availability or response times.</p>
          </aside>
        </div>
      </section>

      <section className="public-section trust-section" aria-label="Privacy and trust">
        <div><p className="eyebrow">Privacy by design</p><h2>Personal information belongs in the right hands.</h2></div>
        <p>Access is role-scoped. Donor location details are used for coordination only where permitted, and request responses do not confirm a donation. Share only information needed for coordination.</p>
      </section>

      <footer className="public-footer">
        <div className="brand-block"><span className="brand-mark small" aria-hidden="true">NSS</span><div><strong>NSS BloodConnect</strong><small>Community blood donation coordination</small></div></div>
        <nav aria-label="Footer navigation"><a className="text-nav-link" href="#roles">Roles</a><a className="text-nav-link" href="#safety">Safety</a><button className="text-nav-button" onClick={() => navigateTo('/login')}>Sign in</button></nav>
        <p>For urgent medical needs, contact local emergency services or an authorized healthcare provider.</p>
      </footer>
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

      csrfToken = data.csrf_token || null;
      if (!COOKIE_AUTH_ENABLED) {
        localStorage.setItem(TOKEN_KEY, data.access_token);
      }
      const user = await fetchProfile(COOKIE_AUTH_ENABLED ? undefined : data.access_token);
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
          <p className="auth-footnote">
            Forgot your password? <button className="link-button" onClick={() => navigateTo('/forgot-password')}>Reset it</button>
          </p>
        </section>
      </div>
    </PageShell>
  );
}

function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage('');
    setError('');
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to request a password reset.');
      setMessage(data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to request a password reset.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell>
      <div className="auth-shell">
        <section className="auth-card">
          <h2>Reset your password</h2>
          <form onSubmit={handleSubmit} className="form-stack">
            <label className="field">
              <span>Email</span>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            {error ? <div className="error-box">{error}</div> : null}
            {message ? <div className="success-box">{message}</div> : null}
            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting ? 'Sending...' : 'Send reset instructions'}
            </button>
          </form>
          <p className="auth-footnote">
            <button className="link-button" onClick={() => navigateTo('/login')}>Return to sign in</button>
          </p>
        </section>
      </div>
    </PageShell>
  );
}

function ResetPasswordPage() {
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '');

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage('');
    setError('');
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to reset your password.');
      setMessage(data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reset your password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell>
      <div className="auth-shell">
        <section className="auth-card">
          <h2>Choose a new password</h2>
          <form onSubmit={handleSubmit} className="form-stack">
            <label className="field">
              <span>New password</span>
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} maxLength={72} />
            </label>
            {error ? <div className="error-box">{error}</div> : null}
            {message ? <div className="success-box">{message}</div> : null}
            <button type="submit" className="primary-button" disabled={isSubmitting || !token}>
              {isSubmitting ? 'Saving...' : 'Update password'}
            </button>
          </form>
          <p className="auth-footnote">
            <button className="link-button" onClick={() => navigateTo('/login')}>Return to sign in</button>
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
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={12} maxLength={72} />
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

        <nav className="sidebar-nav" aria-label="Dashboard navigation">
          {navItems.map((item) => (
              <button key={item.path} className={window.location.pathname === item.path ? 'nav-link active' : 'nav-link'} aria-current={window.location.pathname === item.path ? 'page' : undefined} onClick={() => navigateTo(item.path)}>
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
  const [error, setError] = useState('');

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
      .catch(() => setError('Unable to load your requests. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  const activeRequests = requests.filter((item) => !['fulfilled', 'cancelled', 'expired'].includes(item.status || ''));
  const outstandingUnits = requests
    .filter((item) => !['fulfilled', 'cancelled', 'expired'].includes(item.status || ''))
    .reduce((sum, item) => sum + Math.max(0, (item.units_required || 0) - (item.units_confirmed || 0)), 0);

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
        <StatusCard label="Confirmed units" value={String(requests.reduce((sum, item) => sum + (item.units_confirmed || 0), 0))} tone="success" />
        <StatusCard label="Units outstanding" value={String(outstandingUnits)} />
      </div>

      <div className="content-grid two-col">
        <section className="panel-block">
          <h4>Recent requests</h4>
          <AsyncState loading={loading} error={error} hasData={requests.length > 0} loadingMessage="Loading requests..." emptyMessage="No requests have been created yet.">
            <ul className="list-stack">
              {requests.slice(0, 5).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <strong>{item.patient_reference || 'Untitled request'}</strong>
                    <small>{item.request_code || 'BCR'} • {item.blood_group || 'Blood group not set'} • {item.units_confirmed || 0} of {item.units_required || 0} units confirmed</small>
                    {item.legacy_fulfillment_unverified ? <small>Legacy fulfilled status; donation outcome is unverified.</small> : null}
                  </div>
                  <span className={`pill status-pill ${item.escalation_status && item.escalation_status !== 'normal' ? 'urgent' : ''}`}>{item.status || 'submitted'}</span>
                </li>
              ))}
            </ul>
          </AsyncState>
        </section>

        <section className="panel-block">
          <h4>Request status</h4>
          <div className="info-stack">
            <div className="info-row"><span>Submitted</span><strong>{requests.filter((item) => item.status === 'submitted').length}</strong></div>
            <div className="info-row"><span>Partially fulfilled</span><strong>{requests.filter((item) => item.status === 'partially_fulfilled').length}</strong></div>
            <div className="info-row"><span>Fulfilled</span><strong>{requests.filter((item) => item.status === 'fulfilled').length}</strong></div>
            <div className="info-row"><span>Cancelled / expired</span><strong>{requests.filter((item) => ['cancelled', 'expired'].includes(item.status || '')).length}</strong></div>
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}

function DonorDashboard({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [profile, setProfile] = useState<DonorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileError, setProfileError] = useState('');
  const [matches, setMatches] = useState<DonorMatchItem[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(true);
  const [matchesError, setMatchesError] = useState('');
  const [availabilityError, setAvailabilityError] = useState('');
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
      .catch(() => setProfileError('Unable to load donor profile. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    fetch(`${API_BASE}/api/donors/me/matches`, {
      headers: !COOKIE_AUTH_ENABLED && token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Could not load matching requests');
        const data = await response.json();
        setMatches(Array.isArray(data) ? data : []);
      })
      .catch(() => setMatchesError('Unable to load matching requests. Please try again.'))
      .finally(() => setMatchesLoading(false));
  }, []);

  const toggleAvailability = async () => {
    if (!profile) return;
    const nextState = !profile.available;
    setPendingToggle(true);
    setAvailabilityError('');

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
      setAvailabilityError('Availability could not be updated. Please try again.');
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
          {loading ? <LoadingState message="Loading donor profile..." /> : profileError ? <div className="error-box" role="alert">{profileError}</div> : !profile ? (
            <EmptyState message="Complete your donor profile to manage availability." />
          ) : (
            <>
              <button className={profile.available ? 'toggle-button on' : 'toggle-button'} onClick={toggleAvailability} disabled={pendingToggle}>
                {pendingToggle ? 'Updating...' : profile?.available ? 'AVAILABLE' : 'UNAVAILABLE'}
              </button>
              {availabilityError ? <p className="error-box" role="alert">{availabilityError}</p> : null}
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

      <div className="stats-row">
        <StatusCard label="Matching opportunities" value={String(matches.length)} />
        <StatusCard label="Awaiting your response" value={String(matches.filter((item) => item.donor_response_status === 'pending').length)} />
        <StatusCard label="Accepted responses" value={String(matches.filter((item) => item.donor_response_status === 'accepted').length)} tone="success" />
      </div>

      <div className="content-grid">
        <section className="panel-block">
          <h4>Matching opportunities</h4>
          {matchesLoading ? <LoadingState message="Loading matching opportunities..." /> : matchesError ? <div className="error-box" role="alert">{matchesError}</div> : matches.length === 0 ? <EmptyState message="No matching requests are currently available. Your response history remains separate from confirmed donation outcomes." /> : (
            <ul className="list-stack">
              {matches.slice(0, 5).map((item) => (
                <li key={item.match_id} className="list-item">
                  <div>
                    <strong>{item.request_code}</strong>
                    <small>{item.hospital_name} • {item.city} • {item.urgency}</small>
                    <small>{item.units_confirmed} of {item.units_required} units confirmed • {item.distance_km == null ? 'Distance unavailable' : `${item.distance_km} km`}</small>
                  </div>
                  <span className="pill status-pill">{item.donor_response_status}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="muted-text">Accepting is an offer to coordinate and does not confirm a donation.</p>
        </section>
      </div>
    </DashboardLayout>
  );
}

function VolunteerDashboard({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  const [assignments, setAssignments] = useState<VolunteerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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
      .catch(() => setError('Unable to load assigned requests. Please try again.'))
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
          {loading ? <LoadingState message="Loading assigned requests..." /> : error ? <div className="error-box" role="alert">{error}</div> : assignments.length === 0 ? <EmptyState message="No assigned requests currently available." /> : (
            <ul className="list-stack">
              {assignments.slice(0, 5).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <strong>{item.request_code || 'Request'}</strong>
                    <small>{item.hospital_name || 'Hospital not set'} • {item.city || 'City not set'}</small>
                    <small>{item.request_status || 'Request status unavailable'} • {item.units_confirmed || 0} of {item.units_required || 0} units confirmed</small>
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
  const [error, setError] = useState('');

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
      .catch(() => setError('Unable to load requests. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  const pendingVerification = requests.filter((item) => item.status === 'submitted').length;
  const activeItems = requests.filter((item) => !['fulfilled', 'cancelled', 'expired'].includes(item.status || ''));
  const activeRequests = activeItems.length;
  const escalatedRequests = activeItems.filter((item) => item.escalation_status && item.escalation_status !== 'normal').length;
  const priorityRequests = [...activeItems].sort((a, b) => {
    const aPriority = (a.escalation_status && a.escalation_status !== 'normal' ? 2 : 0) + (['emergency', 'critical', 'urgent'].includes((a.urgency || '').toLowerCase()) ? 1 : 0);
    const bPriority = (b.escalation_status && b.escalation_status !== 'normal' ? 2 : 0) + (['emergency', 'critical', 'urgent'].includes((b.urgency || '').toLowerCase()) ? 1 : 0);
    return bPriority - aPriority;
  });

  return (
    <DashboardLayout user={user} onLogout={onLogout} title="Coordinator Dashboard">
      <div className="stats-row">
        <StatusCard label="Pending verification" value={String(pendingVerification)} />
        <StatusCard label="Active requests" value={String(activeRequests)} />
        <StatusCard label="Escalated requests" value={String(escalatedRequests)} />
      </div>

      <div className="content-grid two-col">
        <section className="panel-block">
          <h4>Priority requests</h4>
          {loading ? <LoadingState message="Loading requests..." /> : error ? <div className="error-box" role="alert">{error}</div> : priorityRequests.length === 0 ? <EmptyState message="No active requests are awaiting coordination." /> : (
            <ul className="list-stack">
              {priorityRequests.slice(0, 8).map((item) => (
                <li key={item.id} className="list-item">
                  <div>
                    <strong>{item.patient_reference || 'Request'}</strong>
                    <small>{item.request_code || 'BCR'} • {item.city || 'City not set'} • {item.urgency || 'Urgency not set'}</small>
                    <small>{item.units_confirmed || 0} of {item.units_required || 0} units confirmed</small>
                    {item.escalation_status && item.escalation_status !== 'normal' ? <small>Escalation: {item.escalation_status}</small> : null}
                  </div>
                  <span className={`pill status-pill ${item.escalation_status && item.escalation_status !== 'normal' ? 'urgent' : ''}`}>{item.status || 'submitted'}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel-block">
          <h4>Coordinator actions</h4>
          <p className="muted-text">Review new requests and use request details to coordinate donor responses and record authorized donation verification.</p>
          <button className="secondary-button" onClick={() => navigateTo('/coordinator/requests')}>Open request queue</button>
          <p className="muted-text">Donor directory and response summaries are not exposed in this dashboard view.</p>
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
    if (filter === 'active') return ['submitted', 'verified', 'coordinating', 'partially_fulfilled'].includes(request.status || '');
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
                  <span>{request.units_confirmed || 0} / {request.units_required} units confirmed</span>
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

  const stages = ['submitted', 'verified', 'coordinating', 'partially_fulfilled', 'fulfilled'];
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
                  <div className="info-row"><span>Units confirmed</span><strong>{request.units_confirmed || 0} of {request.units_required}</strong></div>
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
                  {request.legacy_fulfillment_unverified ? <p className="muted-text">Legacy fulfilled status; no donation confirmation records are available.</p> : null}
                  {request.escalation_status && request.escalation_status !== 'normal' ? <div className="info-row"><span>Escalation</span><strong><StatusBadge text={request.escalation_status} /></strong></div> : null}
                  <div className="info-row"><span>Notes</span><strong>{request.notes || 'No additional notes.'}</strong></div>
                </div>
              </div>
            </div>
            {requestMap ? <section className="panel-block map-section">
              <h4>Request Location</h4>
              <CoordinationMap request={requestMap.request} />
              <div className="map-aggregate"><span>Potential donors found: {requestMap.potential_donors}</span><span>Accepted donors: {requestMap.accepted_donors}</span></div>
            </section> : null}
            {user.role === 'requester' && ['submitted', 'verified', 'coordinating', 'partially_fulfilled'].includes(request.status || '') && (request.units_confirmed || 0) === 0 ? (
              <button className="secondary-button" onClick={() => void cancelRequesterRequest(request.id)}>Cancel Request</button>
            ) : null}
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
                  <div className="info-row"><span>Units confirmed</span><strong>{request.units_confirmed} of {request.units_required}</strong></div>
                  <div className="info-row"><span>Hospital</span><strong>{request.hospital_name}</strong></div>
                  <div className="info-row"><span>City / area</span><strong>{request.city}</strong></div>
                  <div className="info-row"><span>Urgency</span><strong>{request.urgency}</strong></div>
                  <div className="info-row"><span>Required</span><strong>{request.required_at ? new Date(request.required_at).toLocaleString() : 'Not set'}</strong></div>
                  <div className="info-row"><span>Distance</span><strong>{request.distance_km == null ? 'Unavailable' : `${request.distance_km} km`}</strong></div>
                  <div className="info-row"><span>Request status</span><strong>{request.request_status}</strong></div>
                  <div className="info-row"><span>Confirmed units</span><strong>{request.units_confirmed} of {request.units_required}</strong></div>
                  {request.escalation_status !== 'normal' ? <div className="info-row"><span>Escalation</span><strong>{request.escalation_status}</strong></div> : null}
                </div>
                <CoordinationMap request={{ latitude: request.request_latitude, longitude: request.request_longitude, hospital_name: request.hospital_name, city: request.city }} />
              </div>

              <div className="info-box">
                <p>BloodConnect identifies potentially compatible donors for coordination. Final donor eligibility and blood compatibility must be confirmed by qualified healthcare professionals or an authorized blood bank.</p>
                <div className="button-row">
                  {request.donor_response_status === 'pending' ? <>
                    <button className="primary-button" onClick={() => respondToRequest(request.request_id, 'accepted')}>Accept Request</button>
                    <button className="secondary-button" onClick={() => respondToRequest(request.request_id, 'declined')}>Decline Request</button>
                  </> : <><StatusBadge text={request.donor_response_status} /><p>An accepted response is an offer to coordinate, not confirmation of a donation.</p>{request.donor_response_status === 'accepted' ? <button className="secondary-button" onClick={() => respondToRequest(request.request_id, 'withdrawn')}>Withdraw Response</button> : null}</>}
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
            <div className="right-meta"><StatusBadge text={item.request_status} /><small>{item.units_confirmed || 0} / {item.units_required} units confirmed • {item.response_timestamp ? new Date(item.response_timestamp).toLocaleString() : 'Recently'}</small></div>
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
            <div className="right-meta"><StatusBadge text={item.response} /><small>{item.units_confirmed || 0} / {item.units_required} units confirmed • {item.response_timestamp ? new Date(item.response_timestamp).toLocaleString() : 'Recently'} • {item.request_status}</small></div>
          </div>)}</div>
        )}
      </div>
    </DashboardLayout>
  );
}

function VolunteerAssignedPage({ user }: { user: AppUser }) {
  const [assignments, setAssignments] = useState<VolunteerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    fetch(`${API_BASE}/api/volunteers/me/assignments`, { headers: { Authorization: `Bearer ${getStoredToken()}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Unable to load assignments'); return response.json(); })
      .then((data) => setAssignments(Array.isArray(data) ? data : []))
      .catch(() => setError('Unable to load assigned requests. Please try again.'))
      .finally(() => setLoading(false));
  }, []);
  return (
    <DashboardLayout user={user} onLogout={() => navigateTo('/')} title="Assigned Requests">
      <div className="panel-block">
        <AsyncState loading={loading} error={error} hasData={assignments.length > 0} loadingMessage="Loading assignments..." emptyMessage="No requests are currently assigned to you.">
          <div className="card-list">{assignments.map((assignment) => <button key={assignment.id} className="request-card" onClick={() => navigateTo(`/volunteer/requests/${assignment.request_id}`)}><div><strong>{assignment.request_code}</strong><small>{assignment.hospital_name} • {assignment.city}</small></div><StatusBadge text={assignment.status} /></button>)}</div>
        </AsyncState>
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
                <div className="info-row"><span>Units confirmed</span><strong>{assignment.units_confirmed || 0} / {assignment.units_required}</strong></div>
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
  const [error, setError] = useState('');

  const loadRequests = async () => {
    const token = getStoredToken();
    if (!token) return;

    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/api/requests`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      if (!response.ok) throw new Error('Unable to load verification queue');
      setRequests(Array.isArray(data) ? data.filter((item) => item.status === 'submitted') : []);
    } catch {
      setError('Unable to load the verification queue. Please try again.');
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
        <AsyncState loading={loading} error={error} hasData={requests.length > 0} loadingMessage="Loading verification queue..." emptyMessage="No submitted requests are awaiting verification.">
          <div className="card-list">
            {requests.map((request) => (
              <div key={request.id} className="request-card">
                <div><strong>{request.request_code || `BCR-${request.id}`}</strong><small>{request.hospital_name}</small></div>
                <div className="request-meta"><span>{request.blood_group}</span><span>{request.units_required} units</span><span>{request.urgency}</span></div>
                <div className="right-meta"><StatusBadge text={request.status || 'submitted'} /><div className="inline-actions"><button className="secondary-button" onClick={() => navigateTo(`/coordinator/requests/${request.id}`)}>View</button><button className="primary-button" onClick={() => void verifyRequest(request.id)}>Verify</button></div></div>
              </div>
            ))}
          </div>
        </AsyncState>
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
  const [confirmationUnits, setConfirmationUnits] = useState('1');
  const [confirmationSource, setConfirmationSource] = useState('');
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
      setMessage(data.matched_count ? `${data.matched_count} potential donors found.` : 'No potentially compatible donors were found using the available location information.');
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

  const confirmDonation = async (donorId: number) => {
    const token = getStoredToken();
    if (!token || !request) return;
    setActionLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/api/requests/${requestId}/donations/${donorId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({
          units_confirmed: Number(confirmationUnits),
          verification_source: confirmationSource,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to record donation confirmation');
      setMessage('Donation outcome recorded. This does not assert transfusion.');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to record donation confirmation');
    } finally {
      setActionLoading(false);
    }
  };

  const closeRequest = async () => {
    const token = getStoredToken();
    if (!token) return;
    const response = await fetch(`${API_BASE}/api/requests/${requestId}/close`, { method: 'POST', headers: { Authorization: 'Bearer ' + token } });
    const data = await response.json();
    if (!response.ok) {
      setError(data.detail || 'Unable to close request');
      return;
    }
    setMessage('Request closed.');
    await loadData();
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
                <div className="info-row"><span>Units required</span><strong>{request.units_required}</strong></div>
                <div className="info-row"><span>Units confirmed</span><strong>{request.units_confirmed || 0} / {request.units_required}</strong></div>
                <div className="info-row"><span>Escalation</span><strong>{request.escalation_status || 'normal'}</strong></div>
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
                <div><strong>{match.donor_name}</strong><small>{match.blood_group} • {match.area || match.city || 'Location unavailable'} • {match.units_confirmed} confirmed unit(s)</small></div>
                <span className="pill status-pill">{match.response_status} • {match.distance_km ?? 'N/A'} km</span>
                {match.response_status === 'accepted' && !match.donation_confirmed && request.status !== 'fulfilled' ? <div className="inline-actions"><label>Confirmed units <input type="number" min="1" max={Math.max(0, (request.units_required ?? 0) - (request.units_confirmed || 0))} value={confirmationUnits} onChange={(event) => setConfirmationUnits(event.target.value)} /></label><label>Verification source <input value={confirmationSource} onChange={(event) => setConfirmationSource(event.target.value)} placeholder="Authorized blood bank or healthcare professional" required /></label><button className="secondary-button" onClick={() => void confirmDonation(match.donor_id)} disabled={actionLoading || !confirmationSource.trim()}>Record verified donation</button></div> : null}
              </div>)}</div> : <p className="muted-text">No potential donors have been matched.</p>}
              {coordinationMap ? <CoordinationMap request={coordinationMap.request} donors={coordinationMap.matched_donors} showDonors /> : null}
              <h4>Volunteer Coordination</h4>
              {volunteers.length ? <div className="button-row"><label htmlFor="coordinator-volunteer">Volunteer to assign</label><select id="coordinator-volunteer" value={selectedVolunteer} onChange={(event) => setSelectedVolunteer(event.target.value)}><option value="">Select volunteer</option>{volunteers.filter((volunteer) => volunteer.active).map((volunteer) => <option key={volunteer.volunteer_id} value={volunteer.volunteer_id}>{volunteer.name}</option>)}</select><button className="secondary-button" onClick={() => void assignVolunteer()} disabled={!selectedVolunteer || actionLoading}>Assign Volunteer</button></div> : <p className="muted-text">No active volunteer accounts are available.</p>}
              {assignments.length ? <div className="card-list">{assignments.map((assignment) => <div key={assignment.id} className="list-item"><div><strong>{assignment.volunteer_name}</strong><small>{assignment.status} • {assignment.notes || 'No coordinator notes'}</small></div>{!['completed', 'cancelled'].includes(assignment.status) ? <button className="secondary-button" onClick={() => void cancelAssignment(assignment.id)}>Cancel Assignment</button> : null}</div>)}</div> : <p className="muted-text">No volunteers assigned to this request.</p>}
              <div className="button-row">
                {request.status === 'submitted' ? <button className="primary-button" onClick={() => void verifyRequest()} disabled={actionLoading}>{actionLoading ? 'Verifying...' : 'Verify'}</button> : null}
                {request.status === 'verified' ? <button className="secondary-button" onClick={() => void findDonors()} disabled={actionLoading}>{actionLoading ? 'Finding...' : 'Find Potential Donors'}</button> : null}
                {['submitted', 'verified', 'coordinating', 'partially_fulfilled'].includes(request.status || '') ? <button className="secondary-button" onClick={() => void closeRequest()} disabled={actionLoading}>Close Request</button> : null}
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

async function respondToRequest(requestId: number, response: 'accepted' | 'declined' | 'withdrawn') {
  const token = getStoredToken();
  if (!token) {
    navigateTo('/login');
    return;
  }

  const endpoint = response === 'withdrawn'
    ? `${API_BASE}/api/requests/${requestId}/withdraw`
    : response === 'accepted'
      ? `${API_BASE}/api/requests/${requestId}/accept`
      : `${API_BASE}/api/requests/${requestId}/decline`;
  const result = await fetch(endpoint, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!result.ok) {
    alert(response === 'accepted' ? 'This request could not be accepted.' : response === 'withdrawn' ? 'This response could not be withdrawn.' : 'This request could not be declined.');
    return;
  }

  navigateTo(response === 'accepted' ? '/donor/accepted' : '/donor/history');
}

async function cancelRequesterRequest(requestId: number) {
  const token = getStoredToken();
  if (!token) {
    navigateTo('/login');
    return;
  }
  const result = await fetch(`${API_BASE}/api/requests/${requestId}/cancel`, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + token },
  });
  if (!result.ok) {
    alert('This request could not be cancelled.');
    return;
  }
  navigateTo('/requests');
}

function throwingError(data: any, fallback: string) {
  throw new Error(data?.detail || fallback);
}

function PageShell({ children }: { children: React.ReactNode }) {
  return <div className="page-shell">{children}</div>;
}

function LoadingState({ message }: { message: string }) {
  return <div className="empty-state" role="status" aria-live="polite">{message}</div>;
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state" role="status">{message}</div>;
}

function AsyncState({ loading, error, hasData, loadingMessage, emptyMessage, children }: {
  loading: boolean;
  error: string;
  hasData: boolean;
  loadingMessage: string;
  emptyMessage: string;
  children: React.ReactNode;
}) {
  const state = resolveAsyncState({ loading, error, hasData, loadingMessage, emptyMessage });

  if (state.kind === 'loading') return <LoadingState message={state.message} />;
  if (state.kind === 'error') return <div className="error-box" role="alert">{state.message}</div>;
  if (state.kind === 'empty') return <EmptyState message={state.message} />;
  return children;
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
