export type Profile = {
  id: string;
  user_id: string;
  headline: string | null;
  summary: string | null;
  target_roles: string[];
  target_locations: string[];
  user: {
    display_name: string;
    email: string | null;
  };
};

export type Internship = {
  id: string;
  title: string;
  company_name: string;
  application_url: string;
  normalized_title: string;
  normalized_location: string | null;
  work_mode: string;
};

export type InternshipMatch = {
  id: string;
  profile_id: string;
  internship_id: string;
  total_score: string;
  skill_score: string;
  semantic_score: string;
  explanation_json: {
    signals?: {
      matched_skills?: string[];
    };
  };
  internship: Internship | null;
};

export type GapResponse = {
  missing_skills: Array<{
    skill_name_raw: string;
    skill?: {
      name: string;
    } | null;
  }>;
};

export type ApplicationStatus =
  | "saved"
  | "applying"
  | "applied"
  | "interview"
  | "rejected"
  | "offer"
  | "closed"
  | "ignored";

export type ApplicationRecord = {
  id: string;
  profile_id: string;
  internship_id: string;
  internship_match_id: string | null;
  status: ApplicationStatus;
  priority: number;
  notes: string | null;
  next_action_at: string | null;
  internship: Internship | null;
};

export type GeneratedResume = {
  id: string;
  profile_id: string;
  internship_id: string | null;
  status: string;
  rendered_html_path: string | null;
  rendered_pdf_path: string | null;
  created_at: string;
};

export type DashboardData = {
  profile: Profile | null;
  internshipsCount: number;
  matches: InternshipMatch[];
  applications: ApplicationRecord[];
  resumes: GeneratedResume[];
};
