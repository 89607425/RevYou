export interface User {
  user_id: string;
  username: string;
  display_name: string;
  role: "PM" | "DEV" | "QA" | "SM" | "ADMIN";
  email?: string;
}

export interface ReviewIssue {
  issue_id: string;
  session_id: string;
  source_agent: "PM_REVIEW" | "DEV_REVIEW" | "QA_REVIEW";
  issue_type: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  description: string;
  suggestion?: string;
  prd_section?: string;
  prd_quote?: string;
  image_ref?: string;
  confidence: number;
  confidence_label: "HIGH" | "MEDIUM" | "LOW";
  status: "OPEN" | "CONFIRMED" | "FALSE_POSITIVE" | "RESOLVED" | "DEFERRED";
  created_at: string;
  updated_at: string;
}

export interface ReviewSession {
  session_id: string;
  project_id: string;
  status: "RUNNING" | "COMPLETED" | "TIMEOUT" | "CANCELLED";
  agent_mode: "DETERMINISTIC" | "AUTONOMOUS";
  prd_source: "TEXT" | "FILE" | "TAPD";
  issue_count?: { HIGH: number; MEDIUM: number; LOW: number; total: number };
  initiator?: { user_id: string; display_name: string };
  created_at: string;
  completed_at?: string;
}

export interface FollowUp {
  follow_up_id: string;
  source_agent: string;
  question: string;
  prd_section?: string;
  status: "PENDING" | "ANSWERED" | "SKIPPED";
  round: number;
  created_at: string;
  answer?: string;
}
