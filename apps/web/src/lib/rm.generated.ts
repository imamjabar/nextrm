// Generated from OpenAPI by scripts/generate_rm_types.py. Do not edit.
export interface RMAIBrief {
  party_id: string;
  summary: string;
  talking_points: Array<RMAIBriefTalkingPoint>;
  questions: Array<string>;
  cautions: Array<string>;
  sources: Array<RMSource>;
  mode: "LIVE" | "SIMULATED";
  model: string;
  prompt_version: string;
  latency_ms: number;
  generated_at: string;
  method: string;
}
export interface RMAIBriefTalkingPoint {
  text: string;
  source_ids: Array<string>;
}
export interface RMAIDraft {
  followup_id: string;
  subject?: string | null;
  body: string;
  source_ids: Array<string>;
  sources: Array<RMSource>;
  mode: "LIVE" | "SIMULATED";
  model: string;
  prompt_version: string;
  latency_ms: number;
  generated_at: string;
  boundary: string;
}
export interface RMAIDraftRequest {
  channel: "EMAIL" | "PHONE_SCRIPT";
}
export interface RMActivityReceipt {
  id: string;
  signal_id: string | null;
  mode: string;
  message: string;
}
export interface RMActivityRequest {
  request_key: string;
  kind: "PRODUCT_VIEW" | "RM_CONTACT_VIEW";
  product: "DEPOSIT" | "LOAN" | "SAVINGS" | "NONE";
}
export interface RMAdjudication {
  base_version: number;
  case_id: string;
  qa_correct: boolean;
  reason: string;
}
export interface RMAssignments {
  rms: Array<Record<string, unknown>>;
  customers: Array<Record<string, unknown>>;
  next_cursor: string | null;
  pool_cases: number;
  method: string;
}
export interface RMBehavior {
  events: Array<RMBehaviorRow>;
  signals: Array<RMSignal>;
  method: string;
}
export interface RMBehaviorRow {
  kind: string;
  product: string;
  count: number;
  window: string;
  latest_at: string;
  mode: string;
  interpretation: string;
}
export interface RMBrief {
  party_id: string;
  why_now: string;
  facts: Array<RMBriefFact>;
  questions: Array<string>;
  constraints: Array<string>;
  next_action: string;
  contacts: Array<RMContactRecord>;
  timeline: Array<RMBriefFact>;
  source_review: boolean;
  method: string;
}
export interface RMBriefFact {
  kind: string;
  text: string;
  source?: RMSource | null;
}
export interface RMCapacityUpdate {
  base_version: number;
  dedicated_limit: number;
  case_limit: number;
  pool_enabled: boolean;
  reason: string;
}
export interface RMCategoryCorrection {
  base_version: number;
  request_key: string;
  source_id: string;
  source_version: number;
  source_hash: string;
  category: string;
}
export interface RMChatMemory {
  topics: Array<string>;
  items: Array<RMChatMemoryItem>;
}
export interface RMChatMemoryItem {
  session_id: string;
  title: string;
  date: string;
  message: string;
}
export interface RMChatRequest {
  message: string;
  base_version: number;
  request_key: string;
  share_with_rm?: boolean | null;
  session_id?: string | null;
  use_memory?: boolean;
}
export interface RMChatSession {
  id: string;
  title: string;
  version: number;
  created_at: string;
  updated_at: string;
  turn_count: number;
  legacy?: boolean;
}
export interface RMChatSessions {
  sessions: Array<RMChatSession>;
  next_cursor: string | null;
}
export interface RMCheckpoint {
  event: string;
  status: string;
  at: string;
  reference: string;
  mode: string;
  note?: string;
  due_at?: string | null;
}
export interface RMComparison {
  title: string;
  education: string;
  ownership: string;
  eligibility: string;
  terms_status: string;
  source: RMSource;
}
export interface RMContact {
  id: string;
  person_id: string;
  name: string;
  role: string;
  email: string;
  source_ref: string;
  authority: string;
}
export interface RMContactPreferenceIn {
  request_key: string;
  method: "PHONE_CALL" | "VIDEO_CALL" | "BRANCH_MEETING" | "EMAIL";
  window: "MORNING" | "AFTERNOON" | "ANY_TIME";
}
export interface RMContactRecord {
  id: string;
  channel: string;
  purpose: string;
  event: string;
  note: string;
  occurred_at: string;
  source_id: string;
}
export interface RMContactRequest {
  request_key: string;
  base_version: number;
  channel: "IN_APP" | "PHONE" | "EMAIL" | "MEETING";
  purpose: "SERVICE" | "REQUESTED_DISCUSSION";
  event: "PREPARED" | "CUSTOMER_DISCUSSION_RECORDED";
  note: string;
  occurred_at: string;
}
export interface RMContextUpdate {
  base_version: number;
  request_key: string;
  goal?: string;
  horizon?: string;
  interests?: Array<string>;
  share_context?: boolean;
}
export interface RMConversation {
  id: string;
  party: RMParty;
  institution_name: string;
  version: number;
  turns: Array<RMTurn>;
  provider: string;
  provider_ready: boolean;
  older_cursor?: string | null;
}
export interface RMCopilotAction {
  kind: string;
  label: string;
  available: boolean;
  reason?: string | null;
  text?: string | null;
  record_type?: string | null;
  record_id?: string | null;
  href?: string | null;
}
export interface RMCopilotContext {
  surface: "RM" | "QUALITY";
  scope: "PARTY" | "BOOK" | "QUALITY";
  scope_label: string;
  scope_detail: string;
  access: string;
  starters: Array<string>;
  base_version: number | null;
  record_count: number;
  provider: string;
  provider_ready: boolean;
  mode: "LIVE" | "SIMULATED";
}
export interface RMCopilotHistoryItem {
  question: string;
  answer?: string;
}
export interface RMCopilotPoint {
  text: string;
  evidence: string;
  evidence_label: string;
  refs: Array<string>;
}
export interface RMCopilotRef {
  id: string;
  label: string;
  evidence: string;
  record_type: string;
  record_id?: string | null;
  href?: string | null;
  source?: RMSource | null;
}
export interface RMCopilotRequest {
  message: string;
  party_id?: string | null;
  run_id?: string | null;
  base_version?: number | null;
  history?: Array<RMCopilotHistoryItem>;
}
export interface RMCopilotTurn {
  id: string;
  question: string;
  answer: string;
  points: Array<RMCopilotPoint>;
  refs: Array<RMCopilotRef>;
  suggestions: Array<string>;
  action: RMCopilotAction | null;
  mode: "LIVE" | "SIMULATED";
  model: string;
  prompt_version: string;
  latency_ms: number;
  created_at: string;
  scope_label: string;
}
export interface RMCoverageUpdate {
  base_version: number;
  request_key: string;
  mode: "DEDICATED" | "POOL" | "DIGITAL";
  rm_id?: string | null;
  tier?: "STANDARD" | "AFFLUENT" | "HNW" | "PRIVATE";
  reason: string;
}
export interface RMCustomerRequest {
  id: string;
  message: string;
  status: string;
  created_at: string;
  updated_at: string;
  due_at: string | null;
  mode: string;
  contact_method?: string | null;
  contact_window?: string | null;
}
export interface RMCustomerRequestIn {
  request_key: string;
  message: string;
  method: "PHONE_CALL" | "VIDEO_CALL" | "BRANCH_MEETING" | "EMAIL";
  window: "MORNING" | "AFTERNOON" | "ANY_TIME";
  turn_id?: string | null;
}
export interface RMCustomerRequests {
  requests: Array<RMCustomerRequest>;
  boundary: string;
}
export interface RMDecisionItem {
  nudge_id: string;
  family: string;
  category: string;
  result: string;
  reason: string;
  source_versions?: Array<Array<string | number>>;
  expires_at?: string | null;
}
export interface RMDestination {
  key: string;
  title: string;
  menu_path: string;
  href: string | null;
  status: string;
  boundary: string;
}
export interface RMDestinations {
  destinations: Array<RMDestination>;
}
export interface RMDisposition {
  base_version: number;
  disposition: "NURTURE" | "NOT_QUALIFIED" | "DUPLICATE" | "NO_CURRENT_NEED" | "CUSTOMER_DECLINED" | "NEEDS_IDENTITY_REVIEW";
  reason: string;
}
export interface RMEngagementAudit {
  decisions: Array<Record<string, unknown>>;
  metrics: Array<RMMetric>;
  method: string;
}
export interface RMEngagementFeed {
  profile: RMEngagementProfile;
  nudges: Array<RMEnrichedNudge>;
  decisions: Array<RMDecisionItem>;
  decision_id: string;
  method: string;
  insights: Array<RMInsight>;
  comparisons: Array<RMComparison>;
}
export interface RMEngagementProfile {
  version: number;
  goal: string;
  horizon: string;
  interests: Array<string>;
  share_context: boolean;
  source_id: string | null;
  topic_snoozes: Record<string, string>;
  commercial_allowed: boolean;
}
export interface RMEnrichedNudge {
  id: string;
  party_id: string;
  route: string;
  title: string;
  body: string;
  prompt: string;
  state: string;
  version: number;
  source: RMSource;
  knowledge: RMSource;
  why: string;
  signal_id: string | null;
  mode: string;
  family: string;
  topic: string;
  category: string;
  expires_at: string;
  primary?: boolean;
  can_request_rm?: boolean;
}
export interface RMEvalCase {
  case_id: string;
  family: string;
  question: string;
  expected_route: string;
  actual_route: string;
  qa_pass: boolean;
  tool_pass: boolean;
  supported_claims: number;
  assessable_claims: number;
  latency_ms: number;
  status: string;
  answer: string;
  reason: string;
}
export interface RMEvalRun {
  id: string;
  status: string;
  version: number;
  suite_version: string;
  model: string;
  source_digest: string;
  mode: string;
  created_at: string;
  updated_at: string;
  results: Array<RMEvalCase>;
  error: string | null;
}
export interface RMEvalStart {
  request_key: string;
}
export interface RMFeedItem {
  id: string;
  kind: "CHAT" | "APP";
  party_id: string;
  name: string;
  at: string;
  title: string;
  text: string;
  topic: string;
  signal_id?: string | null;
  mode: string;
}
export interface RMFeedbackReceipt {
  id: string;
  action: string;
  profile_version: number;
  message: string;
}
export interface RMFeedbackRequest {
  base_version: number;
  request_key: string;
  action: "HELPFUL" | "NOT_RELEVANT" | "SNOOZE" | "DISMISS" | "OPT_OUT" | "EXPOSED";
  nudge_id?: string | null;
  days?: number;
}
export interface RMFollowupUpdate {
  base_version: number;
  request_key: string;
  action: "START" | "NOTE" | "COMPLETE" | "CANCEL" | "SNOOZE";
  note?: string;
  due_at?: string | null;
  outcome?: "PREPARATION_RECORDED" | "CUSTOMER_DECLINED_DISCUSSION" | "NO_CURRENT_NEED" | "INFORMATION_MISSING" | "DISCUSSION_RECORDED" | "CUSTOMER_REPORTS_CONTINUING_ELSEWHERE" | null;
}
export interface RMGeocode {
  provider: string;
  results: Array<RMGeocodeResult>;
}
export interface RMGeocodeResult {
  label: string;
  latitude: string;
  longitude: string;
}
export interface RMGovernance {
  version: number;
  definition: RMPolicyDefinition;
  tested: boolean;
  tests: Array<Record<string, unknown>>;
  release_id: string | null;
  release_version: number;
  history: Array<Record<string, unknown>>;
  boundaries: Array<string>;
}
export interface RMGovernanceAction {
  base_version: number;
  request_key: string;
  reason: string;
}
export interface RMGovernanceUpdate {
  base_version: number;
  definition: RMPolicyDefinition;
  reason: string;
}
export interface RMHealthItem {
  name: string;
  status: string;
  detail: string;
  checked_at: string;
}
export interface RMHome {
  customers: number;
  prospects: number;
  open_signals: number;
  open_journeys: number;
  signals: Array<RMSignal>;
  prospect_preview: Array<RMProspect>;
  provider: string;
  provider_ready: boolean;
  data_mode: string;
  quality_access: boolean;
  open_followups?: number;
}
export interface RMIdentityReview {
  base_version: number;
  evidence: string;
  decision: "CONFIRMED" | "AMBIGUOUS" | "UNRESOLVED";
}
export interface RMImportReceipt {
  imported: number;
  reused: number;
  prospect_ids: Array<string>;
  mode: string;
  matched_existing?: number;
  held_for_review?: number;
}
export interface RMImportRequest {
  csv_text: string;
  request_key: string;
}
export interface RMInsight {
  key: string;
  title: string;
  status: string;
  explanation: string;
  currency?: string | null;
  values: Record<string, string>;
  rows?: Array<Record<string, string>>;
  series?: Array<Record<string, string>>;
  source?: RMSource | null;
  method: string;
  kind?: string | null;
  evidence?: Record<string, unknown> | string | null;
}
export interface RMIntentRule {
  id: string;
  name: string;
  keywords: Array<string>;
  route: "SAVINGS" | "DEPOSIT" | "LOAN" | "SERVICE" | "CARD" | "WEALTH" | "CLARIFY";
  priority: number;
  enabled?: boolean;
  steps: Array<"READ_KNOWLEDGE" | "READ_FINANCIAL_CONTEXT" | "ANSWER" | "ASK_CLARIFICATION" | "OFFER_RM_CONTACT" | "PROPOSE_SIGNAL">;
  question?: string;
  examples: Array<string>;
}
export interface RMJourney {
  id: string;
  party_id: string;
  name: string;
  kind: string;
  need: string;
  status: string;
  stage: number;
  version: number;
  operation_ref: string;
  draft: string;
  source_id: string;
  signal_id: string | null;
  prospect_id: string | null;
  history: Array<RMCheckpoint>;
  completion_rule: string;
  mode: string;
  due_at?: string | null;
  snoozed_until?: string | null;
  outcome?: string | null;
  contact_method?: string | null;
  contact_window?: string | null;
}
export interface RMJourneys {
  journeys: Array<RMJourney>;
}
export interface RMMetric {
  label: string;
  numerator: number;
  denominator: number;
  unit: string;
  method: string;
}
export interface RMNewSession {
  request_key: string;
}
export interface RMNudge {
  id: string;
  party_id: string;
  route: string;
  title: string;
  body: string;
  prompt: string;
  state: string;
  version: number;
  source: RMSource;
  knowledge: RMSource;
  why: string;
  signal_id: string | null;
  mode: string;
}
export interface RMNudgeAction {
  base_version: number;
  request_key: string;
  action: "EXPLORE" | "REQUEST_RM" | "DISMISS";
  share_with_rm?: boolean;
}
export interface RMNudges {
  nudges: Array<RMNudge>;
  method: string;
}
export interface RMParties {
  parties: Array<RMParty>;
}
export interface RMParty {
  id: string;
  name: string;
  kind: string;
  segment: string;
  owner_id: string;
  owner_name: string;
  relationship: string;
  identity: string;
  contact: string;
  locality: string;
  customer_ref: string | null;
  version: number;
  products: Array<string>;
  declared_goal: string;
  occupation: string;
  contact_channel: string;
  contact_purpose: string;
  email: string;
  mode: string;
  contacts: Array<RMContact>;
}
export interface RMPartyDetail {
  party: RMParty;
  signals: Array<RMSignal>;
  journeys: Array<RMJourney>;
  sources: Array<RMSource>;
  review_history: Array<RMReviewHistory>;
  internal_note?: string | null;
}
export interface RMPartySnapshot {
  party_id: string;
  available: boolean;
  insights: Array<RMInsight>;
  conversations: Array<RMFeedItem>;
  method: string;
}
export interface RMPoiCenter {
  lat: number;
  lng: number;
}
export interface RMPoiCounts {
  existing_customer: number;
  possible_match: number;
  new_lead: number;
  prospect: number;
}
export interface RMPoiCreateProspect {
  request_key: string;
  confirm_not_customer?: boolean;
  reason?: string | null;
}
export interface RMPoiMatchReview {
  request_key: string;
  decision: "CONFIRM_EXISTING" | "NOT_A_CUSTOMER";
  customer_id?: string | null;
  reason: string;
}
export interface RMPoiMatchedCustomer {
  id: string;
  cif: string;
  name: string;
  segment: string;
  relationship_owner_rm: boolean;
}
export interface RMPoiNearby {
  provider: string;
  attribution: string;
  center: RMPoiCenter;
  radius_m: number;
  places: Array<RMPoiPlace>;
  counts: RMPoiCounts;
}
export interface RMPoiPlace {
  id: string;
  name: string;
  primary_type: string;
  address: string;
  latitude: string;
  longitude: string;
  distance_m: number;
  phone_masked?: string | null;
  website?: string | null;
  rating?: number | null;
  rating_count?: number | null;
  match_status: string;
  match_score?: string | null;
  match_reasons?: Array<string>;
  matched_customer?: RMPoiMatchedCustomer | null;
  prospect_id?: string | null;
  provider: string;
  attribution: string;
  fetched_at: string;
}
export interface RMPolicyDefinition {
  rules: Array<RMIntentRule>;
  repeat_view_threshold?: number;
  behavior_window_days?: number;
  spending_change_percent?: number;
  max_nudges?: number;
  enabled_families?: Array<string>;
}
export interface RMPolicyPreview {
  route: string;
  rule_id: string;
  rule_name: string;
  steps: Array<string>;
  reason: string;
  guarded: boolean;
  question: string;
  release_id: string | null;
  release_version: number;
  guardrails?: Array<string>;
  advice_requested?: boolean;
}
export interface RMPolicyTest {
  question: string;
  use_draft?: boolean;
}
export interface RMPool {
  signals: Array<RMSignal>;
  capacity: number;
  active_cases: number;
  method: string;
}
export interface RMPoolClaim {
  base_version: number;
  request_key: string;
}
export interface RMPreference {
  base_version: number;
  commercial_allowed: boolean;
  reason: string;
}
export interface RMProspect {
  id: string;
  party: RMParty;
  source: RMSource;
  state: string;
  disposition: string | null;
  need: string;
  need_reviewed: boolean;
  reasons: Array<string>;
  latitude: number;
  longitude: number;
  version: number;
  map_mode: string;
  priority_tier: string;
  priority_reason: string;
  next_action: string;
  priority_method: string;
  hot_lead: boolean;
  hot_reason: string;
  followup_id?: string | null;
  followup_status?: string | null;
}
export interface RMProspectReview {
  base_version: number;
  need: string;
  confirm?: boolean;
}
export interface RMProspects {
  prospects: Array<RMProspect>;
  map_label: string;
  priority_method?: string;
}
export interface RMPulse {
  open_signals: number;
  needs_review: number;
  urgent_service: number;
  open_followups: number;
  overdue_followups: number;
  signals: Array<RMSignal>;
  followups: Array<RMJourney>;
  method: string;
}
export interface RMQuality {
  provider: string;
  provider_ready: boolean;
  model_mode: string;
  turn_count: number;
  error_count: number;
  p50_ms: number | null;
  p95_ms: number | null;
  metrics: Array<RMMetric>;
  traces: Array<RMTrace>;
  runs: Array<RMEvalRun>;
  health: Array<RMHealthItem>;
  content_access: boolean;
  method_note: string;
  metrics_run_id?: string | null;
}
export interface RMRMContact {
  name: string;
  email: string | null;
  phone: string | null;
  email_href: string | null;
  phone_href: string | null;
  status: string;
  mode: string;
}
export interface RMReview {
  base_version: number;
  decision: "ACCEPTED" | "EDITED" | "REJECTED";
  reason?: string;
  need?: string | null;
  confirmed?: boolean;
}
export interface RMReviewHistory {
  id: string;
  action: string;
  reason: string;
  actor_id: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  at: string;
}
export interface RMSignal {
  id: string;
  party_id: string;
  name: string;
  category: string;
  urgency: string;
  evidence: string;
  workflow: string;
  review: string;
  title: string;
  need: string;
  rationale: string;
  uncertainty: string;
  confirmed: boolean;
  version: number;
  source_id: string;
  turn_id: string | null;
  created_at: string;
  display_label: string;
  contact: string;
  origin: "CHAT" | "APP" | "INSIGHT" | "EVENT" | "REQUEST";
  group: "PROBLEM" | "READY" | "ASKED" | "SPOTTED";
  contact_method?: string | null;
  contact_window?: string | null;
}
export interface RMSignals {
  signals: Array<RMSignal>;
  parties: Array<RMParty>;
}
export interface RMSource {
  id: string;
  title: string;
  content: string;
  kind: string;
  mode: string;
  version: number;
  hash: string;
  event_at: string;
  ingested_at: string;
}
export interface RMStartJourney {
  base_version: number;
  request_key: string;
}
export interface RMToday {
  generated_at: string;
  rm_name: string;
  counts: RMTodayCounts;
  queue: Array<RMTodayNeed>;
  activity: Array<RMFeedItem>;
  followups: Array<RMJourney>;
  prospects: Array<RMProspect>;
  customers: Array<RMTodayCustomer>;
  provider: string;
  provider_ready: boolean;
  method: string;
}
export interface RMTodayCounts {
  customers: number;
  needs_open: number;
  needs_to_review: number;
  urgent_service: number;
  followups_open: number;
  followups_overdue: number;
  prospects_ready: number;
  conversations_today: number;
}
export interface RMTodayCustomer {
  party: RMParty;
  open_needs: number;
  last_activity_at?: string | null;
  last_topic?: string | null;
}
export interface RMTodayNeed {
  signal: RMSignal;
  quote?: string | null;
}
export interface RMTool {
  name: string;
  duration_ms: number;
  status: string;
  scope: string;
}
export interface RMTrace {
  id: string;
  party_id: string;
  name: string;
  route: string;
  status: string;
  mode: string;
  model: string;
  latency_ms: number;
  at: string;
  message: string | null;
  answer: string | null;
  tools: Array<RMTool>;
  sources: Array<RMSource>;
  error_code: string | null;
  content_access: boolean;
  context_source_id?: string | null;
  context_source_version?: number | null;
  context_source_hash?: string | null;
  prompt_version?: string;
  thinking_level?: string | null;
  governance?: Record<string, unknown> | null;
}
export interface RMTurn {
  id: string;
  message: string;
  answer: string;
  status: string;
  route: string;
  mode: string;
  model: string;
  created_at: string;
  latency_ms: number;
  sources: Array<RMSource>;
  tools: Array<RMTool>;
  signal_id: string | null;
  error_code: string | null;
  sharing_status?: string;
  governance?: Record<string, unknown> | null;
  suggestions?: Array<string>;
  thinking_level?: string | null;
  rm_suggested?: boolean;
}
