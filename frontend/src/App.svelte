export default function App() {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', maxWidth: 1100, margin: '0 auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '2.2rem' }}>NSS BloodConnect</h1>
          <p style={{ margin: '0.5rem 0 0', color: '#4b5563' }}>Connecting Donors. Saving Lives. Empowering NSS.</p>
        </div>
        <button style={{ background: '#b91c1c', color: 'white', border: 'none', padding: '0.8rem 1.2rem', borderRadius: '8px', cursor: 'pointer' }}>Request Blood</button>
      </header>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <StatCard label="Active Requests" value="24" />
        <StatCard label="Available Donors" value="138" />
        <StatCard label="Fulfilled" value="61" />
        <StatCard label="Campaigns" value="8" />
      </section>

      <main style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
        <Panel title="How BloodConnect works" items={['Request blood', 'Verify request', 'Match donors', 'Coordinate fulfilment']} />
        <Panel title="Core workflow" items={['Request Blood → Verify Request', 'Find potentially compatible donors', 'Donor accepts/declines', 'Coordinator marks fulfilled']} />
        <Panel title="Safety" items={['Medical decisions remain with blood banks and clinicians', 'No guarantee of compatibility', 'Focus on coordination and verification']} />
      </main>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: '1.25rem', background: '#fff7f7', border: '1px solid #fecaca', borderRadius: '12px' }}>
      <div style={{ color: '#7f1d1d', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
      <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: '0.75rem' }}>{value}</div>
    </div>
  );
}

function Panel({ title, items }: { title: string; items: string[] }) {
  return (
    <div style={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '1.25rem' }}>
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <ul style={{ paddingLeft: '1.2rem', margin: 0, color: '#374151', lineHeight: 1.8 }}>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
