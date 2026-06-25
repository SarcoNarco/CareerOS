import type {
  ApplicationRecord,
  ApplicationStatus,
  DashboardData,
  GapResponse,
  GeneratedResume,
  Internship,
  InternshipMatch,
  Profile
} from "./types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const apiToken = import.meta.env.VITE_API_TOKEN ?? "dev-token";

export const apiConfig = {
  baseUrl: apiBaseUrl,
  hasExplicitToken: Boolean(import.meta.env.VITE_API_TOKEN)
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-API-Token", apiToken);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export async function loadDashboard(profileId: string): Promise<DashboardData> {
  const [profile, internships, matches, applications, resumes] = await Promise.all([
    request<Profile>(`/profiles/${profileId}`),
    request<{ items: Internship[] }>("/internships"),
    request<{ items: InternshipMatch[] }>(`/profiles/${profileId}/top-matches?limit=20`),
    request<{ items: ApplicationRecord[] }>(`/profiles/${profileId}/applications`),
    request<{ items: GeneratedResume[] }>(`/profiles/${profileId}/resumes`)
  ]);
  return {
    profile,
    internshipsCount: internships.items.length,
    matches: matches.items,
    applications: applications.items,
    resumes: resumes.items
  };
}

export async function loadMatchGaps(matchId: string): Promise<GapResponse> {
  return request<GapResponse>(`/matches/${matchId}/gaps`);
}

export async function saveApplication(
  profileId: string,
  match: InternshipMatch
): Promise<ApplicationRecord> {
  if (!match.internship) {
    throw new Error("Match has no internship payload.");
  }
  return request<ApplicationRecord>("/applications", {
    method: "POST",
    body: JSON.stringify({
      profile_id: profileId,
      internship_id: match.internship.id,
      internship_match_id: match.id,
      status: "saved",
      priority: 3
    })
  });
}

export async function updateApplication(
  applicationId: string,
  payload: { status?: ApplicationStatus; notes?: string }
): Promise<ApplicationRecord> {
  return request<ApplicationRecord>(`/applications/${applicationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function openResumeHtml(resumeId: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/resumes/${resumeId}/html`, {
    headers: {
      "X-API-Token": apiToken
    }
  });
  if (!response.ok) {
    throw new Error(`Could not open resume HTML: ${response.statusText}`);
  }
  const html = await response.text();
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
}
