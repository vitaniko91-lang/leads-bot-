export type Period = "today" | "week" | "month";

export type StatsResponse = {
  period: Period;
  leads_total: number;
  sent_count: number;
  reply_count: number;
  conversion_pct: number;
  by_hour: { hour: string; count: number }[];
};

export type LeadSummary = {
  id: number;
  source_id: number;
  source_title: string | null;
  raw_text: string;
  posted_at: string;
  analyzed_at: string | null;
  is_lead: boolean | null;
  project_type: string | null;
  budget_usd: number | null;
  language: string | null;
  client_country: string | null;
  urgency: string | null;
  relevance_score: number | null;
  status: string;
  has_response: boolean;
};

export type ResponseDetail = {
  id: number;
  draft_text: string;
  final_text: string | null;
  status: string;
  sent_to: string | null;
  sent_at: string | null;
  client_replied: boolean;
  client_status: string | null;
  notes: string | null;
};

export type LeadDetail = LeadSummary & {
  reasoning: string | null;
  author_username: string | null;
  author_tg_id: number | null;
  responses: ResponseDetail[];
};

export type LeadListResponse = {
  items: LeadSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type SourceSummary = {
  id: number;
  tg_id: number;
  title: string;
  type: string;
  language: string;
  region: string;
  status: string;
  muted_until: string | null;
  leads_per_day: number;
  sent_per_day: number;
  conversion_pct: number;
};

export type ProfilePayload = {
  name: string;
  portfolio_url: string;
  telegram: string;
  min_rate_usd_per_hour: number;
  tone: string;
  payment_methods: string[];
  cases: { title: string; tags: string[]; description: string; url: string }[];
};

export type SettingsPayload = {
  quiet_hours: string;
  min_budget_usd: number;
  min_relevance_score: number;
  max_responses_per_hour: number;
  max_responses_per_day: number;
  max_responses_per_week: number;
};

export type Template = {
  id: number;
  name: string;
  variant: string;
  prompt: string;
  active: boolean;
  traffic_share: number;
  sent_count: number;
  reply_count: number;
  conversion_rate: number;
  is_winner: boolean;
};

export type HotHoursResponse = {
  matrix: number[][];
  owner_tz: string;
  total: number;
  insight: string;
  weekday_labels: string[];
  hour_labels: string[];
};

export type DiscoveryCandidate = {
  id: number;
  tg_id: number;
  title: string;
  description: string | null;
  member_count: number | null;
  language: string | null;
  predicted_region: string | null;
  matched_query: string | null;
  status: string;
};
