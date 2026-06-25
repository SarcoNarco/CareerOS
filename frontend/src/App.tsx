import { useEffect, useState } from "react";
import {
  apiConfig,
  loadDashboard,
  loadMatchGaps,
  openResumeHtml,
  saveApplication,
  updateApplication
} from "./api";
import type {
  ApplicationRecord,
  ApplicationStatus,
  DashboardData,
  GapResponse,
  InternshipMatch
} from "./types";

type View = "dashboard" | "matches" | "applications" | "resumes";

const statuses: ApplicationStatus[] = [
  "saved",
  "applying",
  "applied",
  "interview",
  "rejected",
  "offer",
  "closed",
  "ignored"
];

function App() {
  const [profileId, setProfileId] = useState(localStorage.getItem("careeros.profileId") ?? "");
  const [activeView, setActiveView] = useState<View>("dashboard");
  const [data, setData] = useState<DashboardData | null>(null);
  const [gaps, setGaps] = useState<Record<string, GapResponse>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!profileId.trim()) {
      setError("Paste a profile ID to load the dashboard.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      localStorage.setItem("careeros.profileId", profileId.trim());
      const dashboard = await loadDashboard(profileId.trim());
      setData(dashboard);
      const gapPairs = await Promise.all(
        dashboard.matches.map(async (match) => [match.id, await loadMatchGaps(match.id)] as const)
      );
      setGaps(Object.fromEntries(gapPairs));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown dashboard error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (profileId) {
      void refresh();
    }
  }, []);

  async function handleSave(match: InternshipMatch) {
    if (!data) return;
    await saveApplication(data.profile?.id ?? profileId, match);
    await refresh();
  }

  async function handleApplicationChange(
    application: ApplicationRecord,
    payload: { status?: ApplicationStatus; notes?: string }
  ) {
    await updateApplication(application.id, payload);
    await refresh();
  }

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">CareerOS Local Dashboard</p>
          <h1>Your internship cockpit, minus the tab jungle.</h1>
          <p className="subtitle">
            Review matches, save opportunities, track applications, and open truthful resume
            outputs from the local backend.
          </p>
        </div>
        <div className="profile-card">
          <label htmlFor="profile-id">Profile ID</label>
          <input
            id="profile-id"
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            placeholder="Paste profile UUID"
          />
          <button onClick={() => void refresh()} disabled={loading}>
            {loading ? "Loading..." : "Load Dashboard"}
          </button>
          <p className="help-text">
            API: <code>{apiConfig.baseUrl}</code>
          </p>
          <p className="help-text">
            Token: {apiConfig.hasExplicitToken ? "configured from VITE_API_TOKEN" : "using dev-token fallback"}
          </p>
        </div>
      </section>

      <nav className="tabs" aria-label="Dashboard views">
        {(["dashboard", "matches", "applications", "resumes"] as View[]).map((view) => (
          <button
            key={view}
            className={activeView === view ? "active" : ""}
            onClick={() => setActiveView(view)}
          >
            {view}
          </button>
        ))}
      </nav>

      {error && (
        <div className="error">
          <strong>Dashboard could not load data.</strong>
          <p>{error}</p>
          <p>
            Check that the backend is running, <code>VITE_API_BASE_URL</code> points to it,
            and <code>VITE_API_TOKEN</code> matches <code>API_TOKEN</code>.
          </p>
        </div>
      )}

      {data ? (
        <>
          {activeView === "dashboard" && <DashboardView data={data} />}
          {activeView === "matches" && (
            <MatchesView data={data} gaps={gaps} onSave={handleSave} />
          )}
          {activeView === "applications" && (
            <ApplicationsView data={data} onChange={handleApplicationChange} />
          )}
          {activeView === "resumes" && <ResumesView data={data} />}
        </>
      ) : (
        <section className="empty-state">
          <h2>Load a profile to begin.</h2>
          <p>
            Run resume upload, claim approval, and job discovery first, then paste the profile ID.
            If you are starting fresh, run <code>python scripts/run_v1_demo.py</code> and use
            the printed profile ID.
          </p>
        </section>
      )}
    </main>
  );
}

function DashboardView({ data }: { data: DashboardData }) {
  return (
    <section className="grid">
      <article className="panel wide">
        <p className="eyebrow">Selected Profile</p>
        <h2>{data.profile?.user.display_name ?? "Unknown profile"}</h2>
        <p>{data.profile?.headline ?? "No headline yet."}</p>
        <div className="chips">
          {data.profile?.target_roles.map((role) => <span key={role}>{role}</span>)}
          {data.profile?.target_locations.map((location) => <span key={location}>{location}</span>)}
        </div>
      </article>
      <Metric label="Internships" value={data.internshipsCount} />
      <Metric label="Matches" value={data.matches.length} />
      <Metric label="Applications" value={data.applications.length} />
      <Metric label="Resumes" value={data.resumes.length} />
    </section>
  );
}

function MatchesView({
  data,
  gaps,
  onSave
}: {
  data: DashboardData;
  gaps: Record<string, GapResponse>;
  onSave: (match: InternshipMatch) => Promise<void>;
}) {
  return (
    <section className="stack">
      {!data.matches.length && (
        <EmptyPanel
          title="No matches yet."
          body="Run job discovery or recompute matches for this profile, then refresh the dashboard."
        />
      )}
      {data.matches.map((match) => {
        const internship = match.internship;
        const missing = gaps[match.id]?.missing_skills ?? [];
        const matched = match.explanation_json.signals?.matched_skills ?? [];
        return (
          <article className="panel match-card" key={match.id}>
            <div>
              <p className="eyebrow">Score {Number(match.total_score).toFixed(2)}</p>
              <h3>{internship?.title ?? "Untitled match"}</h3>
              <p>{internship?.company_name ?? "Unknown company"}</p>
              <p className="muted">{internship?.normalized_location ?? internship?.work_mode}</p>
            </div>
            <div>
              <strong>Matched skills</strong>
              <p>{matched.length ? matched.join(", ") : "No explicit skill overlap yet."}</p>
              <strong>Missing skills</strong>
              <p>
                {missing.length
                  ? missing.map((item) => item.skill?.name ?? item.skill_name_raw).join(", ")
                  : "No missing skills recorded."}
              </p>
            </div>
            <div className="actions">
              {internship?.application_url && (
                <a href={internship.application_url} target="_blank" rel="noreferrer">
                  Apply link
                </a>
              )}
              <button onClick={() => void onSave(match)}>Save to applications</button>
            </div>
          </article>
        );
      })}
    </section>
  );
}

function ApplicationsView({
  data,
  onChange
}: {
  data: DashboardData;
  onChange: (
    application: ApplicationRecord,
    payload: { status?: ApplicationStatus; notes?: string }
  ) => Promise<void>;
}) {
  return (
    <section className="stack">
      {!data.applications.length && (
        <EmptyPanel
          title="No applications saved."
          body="Save a match from the Matches tab to start tracking it here."
        />
      )}
      {data.applications.map((application) => (
        <article className="panel application-card" key={application.id}>
          <div>
            <p className="eyebrow">Priority {application.priority}</p>
            <h3>{application.internship?.title ?? "Tracked opportunity"}</h3>
            <p>{application.internship?.company_name ?? "Unknown company"}</p>
          </div>
          <select
            value={application.status}
            onChange={(event) =>
              void onChange(application, { status: event.target.value as ApplicationStatus })
            }
          >
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
          <textarea
            defaultValue={application.notes ?? ""}
            placeholder="Notes"
            onBlur={(event) => void onChange(application, { notes: event.target.value })}
          />
        </article>
      ))}
    </section>
  );
}

function ResumesView({ data }: { data: DashboardData }) {
  return (
    <section className="stack">
      {!data.resumes.length && (
        <EmptyPanel
          title="No generated resumes."
          body="Generate a truthful resume from approved claims, then refresh this page."
        />
      )}
      {data.resumes.map((resume) => (
        <article className="panel resume-card" key={resume.id}>
          <div>
            <p className="eyebrow">{new Date(resume.created_at).toLocaleString()}</p>
            <h3>Generated Resume</h3>
            <p>Status: {resume.status}</p>
            <p className="muted">{resume.rendered_html_path ?? "No HTML artifact path."}</p>
          </div>
          <button onClick={() => void openResumeHtml(resume.id)} disabled={!resume.rendered_html_path}>
            Open HTML
          </button>
        </article>
      ))}
    </section>
  );
}

function EmptyPanel({ title, body }: { title: string; body: string }) {
  return (
    <article className="panel empty-panel">
      <h3>{title}</h3>
      <p>{body}</p>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <article className="panel metric">
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

export default App;
