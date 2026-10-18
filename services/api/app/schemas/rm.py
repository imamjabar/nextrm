from typing import Literal, Any
from pydantic import BaseModel,ConfigDict,Field

class StrictRM(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class RMSource(BaseModel):
    id:str;title:str;content:str;kind:str;mode:str;version:int;hash:str;event_at:str;ingested_at:str
class RMContact(BaseModel):
    id:str;person_id:str;name:str;role:str;email:str;source_ref:str;authority:str
class RMParty(BaseModel):
    id:str;name:str;kind:str;segment:str;owner_id:str;owner_name:str;relationship:str;identity:str;contact:str;locality:str;customer_ref:str|None;version:int
    products:list[str];declared_goal:str;occupation:str;contact_channel:str;contact_purpose:str;email:str;mode:str;contacts:list[RMContact]
class RMParties(BaseModel):
    parties:list[RMParty]
class RMSignal(BaseModel):
    id:str;party_id:str;name:str;category:str;urgency:str;evidence:str;workflow:str;review:str;title:str;need:str;rationale:str;uncertainty:str;confirmed:bool;version:int;source_id:str;turn_id:str|None;created_at:str;display_label:str;contact:str
class RMSignals(BaseModel):
    signals:list[RMSignal];parties:list[RMParty]
class RMProspect(BaseModel):
    id:str;party:RMParty;source:RMSource;state:str;disposition:str|None;need:str;need_reviewed:bool;reasons:list[str];latitude:float;longitude:float;version:int;map_mode:str
    priority_tier:str;priority_reason:str;next_action:str;priority_method:str
    hot_lead:bool;hot_reason:str
    followup_id:str|None=None;followup_status:str|None=None
class RMProspects(BaseModel):
    prospects:list[RMProspect];map_label:str
    priority_method:str='ACQ-1: identity, relationship, permission and freshness gates; reviewed needs and opt-in enquiries before referrals. No purchase probability.'
class RMReview(StrictRM):
    base_version:int=Field(ge=1);decision:Literal['ACCEPTED','EDITED','REJECTED'];reason:str=Field(default='',max_length=800);need:str|None=Field(default=None,max_length=1200);confirmed:bool=False
class RMProspectReview(StrictRM):
    base_version:int=Field(ge=1);need:str=Field(min_length=3,max_length=1200);confirm:bool=True
class RMDisposition(StrictRM):
    base_version:int=Field(ge=1);disposition:Literal['NURTURE','NOT_QUALIFIED','DUPLICATE','NO_CURRENT_NEED','CUSTOMER_DECLINED','NEEDS_IDENTITY_REVIEW'];reason:str=Field(min_length=3,max_length=800)
class RMIdentityReview(StrictRM):
    base_version:int=Field(ge=1);evidence:str=Field(min_length=12,max_length=800);decision:Literal['CONFIRMED','AMBIGUOUS','UNRESOLVED']
class RMPreference(StrictRM):
    base_version:int=Field(ge=1);commercial_allowed:bool;reason:str=Field(min_length=3,max_length=600)
class RMChatRequest(StrictRM):
    message:str=Field(min_length=1,max_length=1500);base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100);share_with_rm:bool|None=None;session_id:str|None=None;use_memory:bool=True
class RMClaim(BaseModel):
    text:str;source_id:str;supported:bool
class RMTool(BaseModel):
    name:str;duration_ms:int;status:str;scope:str
class RMTurn(BaseModel):
    id:str;message:str;answer:str;status:str;route:str;mode:str;model:str;created_at:str;latency_ms:int;sources:list[RMSource];tools:list[RMTool];signal_id:str|None;error_code:str|None
    sharing_status:str='NOT_RECORDED';governance:dict|None=None;suggestions:list[str]=Field(default_factory=list);thinking_level:str|None=None
class RMConversation(BaseModel):
    id:str;party:RMParty;institution_name:str;version:int;turns:list[RMTurn];provider:str;provider_ready:bool
    older_cursor:str|None=None
class RMStartJourney(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100)
class RMJourneyEvent(StrictRM):
    base_version:int=Field(ge=1);event:Literal['SUBMIT','TIMEOUT','ACCEPT','ACCOUNT_OPENED','COMPLETE','CANCEL']
class RMCheckpoint(BaseModel):
    event:str;status:str;at:str;reference:str;mode:str;note:str='';due_at:str|None=None
class RMJourney(BaseModel):
    id:str;party_id:str;name:str;kind:str;need:str;status:str;stage:int;version:int;operation_ref:str;draft:str;source_id:str;signal_id:str|None;prospect_id:str|None;history:list[RMCheckpoint];completion_rule:str;mode:str;due_at:str|None=None
    snoozed_until:str|None=None;outcome:str|None=None
class RMJourneys(BaseModel):
    journeys:list[RMJourney]
class RMReviewHistory(BaseModel):
    id:str;action:str;reason:str;actor_id:str;before:dict;after:dict;at:str
class RMPartyDetail(BaseModel):
    party:RMParty;signals:list[RMSignal];journeys:list[RMJourney];sources:list[RMSource];review_history:list[RMReviewHistory];internal_note:str|None=None
class RMHome(BaseModel):
    customers:int;prospects:int;open_signals:int;open_journeys:int;signals:list[RMSignal];prospect_preview:list[RMProspect];provider:str;provider_ready:bool;data_mode:str;quality_access:bool;open_followups:int=0
class RMTrace(BaseModel):
    id:str;party_id:str;name:str;route:str;status:str;mode:str;model:str;latency_ms:int;at:str;message:str|None;answer:str|None;tools:list[RMTool];sources:list[RMSource];error_code:str|None;content_access:bool
    context_source_id:str|None=None;context_source_version:int|None=None;context_source_hash:str|None=None;prompt_version:str='UNKNOWN';thinking_level:str|None=None
    governance:dict|None=None
class RMMetric(BaseModel):
    label:str;numerator:int;denominator:int;unit:str;method:str
class RMEvalCase(BaseModel):
    case_id:str;family:str;question:str;expected_route:str;actual_route:str;qa_pass:bool;tool_pass:bool;supported_claims:int;assessable_claims:int;latency_ms:int;status:str;answer:str;reason:str
class RMEvalRun(BaseModel):
    id:str;status:str;version:int;suite_version:str;model:str;source_digest:str;mode:str;created_at:str;updated_at:str;results:list[RMEvalCase];error:str|None
class RMEvalStart(StrictRM):
    request_key:str=Field(min_length=8,max_length=100)
class RMAdjudication(StrictRM):
    base_version:int=Field(ge=1)
    case_id:str;qa_correct:bool;reason:str=Field(min_length=3,max_length=800)
class RMHealthItem(BaseModel):
    name:str;status:str;detail:str;checked_at:str
class RMQuality(BaseModel):
    provider:str;provider_ready:bool;model_mode:str;turn_count:int;error_count:int;p50_ms:int|None;p95_ms:int|None;metrics:list[RMMetric];traces:list[RMTrace];runs:list[RMEvalRun];health:list[RMHealthItem];content_access:bool;method_note:str
    metrics_run_id:str|None=None

class RMCopilotHistoryItem(StrictRM):
    question:str=Field(min_length=1,max_length=1500);answer:str=Field(default='',max_length=3000)
class RMCopilotRequest(StrictRM):
    message:str=Field(min_length=1,max_length=1500)
    party_id:str|None=None;run_id:str|None=None;base_version:int|None=Field(default=None,ge=1)
    history:list[RMCopilotHistoryItem]=Field(default_factory=list,max_length=6)
class RMCopilotRef(BaseModel):
    id:str;label:str;evidence:str;record_type:str;record_id:str|None=None;href:str|None=None;source:RMSource|None=None
class RMCopilotPoint(BaseModel):
    text:str;evidence:str;evidence_label:str;refs:list[str]
class RMCopilotAction(BaseModel):
    kind:str;label:str;available:bool;reason:str|None=None;text:str|None=None;record_type:str|None=None;record_id:str|None=None;href:str|None=None
class RMCopilotContext(BaseModel):
    surface:Literal['RM','QUALITY'];scope:Literal['PARTY','BOOK','QUALITY'];scope_label:str;scope_detail:str;access:str
    starters:list[str];base_version:int|None;record_count:int;provider:str;provider_ready:bool;mode:Literal['LIVE','SIMULATED']
class RMCopilotTurn(BaseModel):
    id:str;question:str;answer:str;points:list[RMCopilotPoint];refs:list[RMCopilotRef];suggestions:list[str];action:RMCopilotAction|None
    mode:Literal['LIVE','SIMULATED'];model:str;prompt_version:str;latency_ms:int;created_at:str;scope_label:str

class RMImportRequest(StrictRM):
    csv_text:str=Field(min_length=10,max_length=10000)
    request_key:str=Field(min_length=8,max_length=100)
class RMImportReceipt(BaseModel):
    imported:int;reused:int;prospect_ids:list[str];mode:str;matched_existing:int=0;held_for_review:int=0

class RMFollowupUpdate(StrictRM):
    base_version:int=Field(ge=1)
    request_key:str=Field(min_length=8,max_length=100)
    action:Literal['START','NOTE','COMPLETE','CANCEL','SNOOZE']
    note:str=Field(default='',max_length=1500)
    due_at:str|None=None
    outcome:Literal['PREPARATION_RECORDED','CUSTOMER_DECLINED_DISCUSSION','NO_CURRENT_NEED','INFORMATION_MISSING','DISCUSSION_RECORDED','CUSTOMER_REPORTS_CONTINUING_ELSEWHERE']|None=None
class RMDestination(BaseModel):
    key:str;title:str;menu_path:str;href:str|None;status:str;boundary:str
class RMDestinations(BaseModel):
    destinations:list[RMDestination]
class RMPulse(BaseModel):
    open_signals:int;needs_review:int;urgent_service:int;open_followups:int;overdue_followups:int
    signals:list[RMSignal];followups:list[RMJourney];method:str

class RMNudge(BaseModel):
    id:str;party_id:str;route:str;title:str;body:str;prompt:str;state:str;version:int
    source:RMSource;knowledge:RMSource;why:str;signal_id:str|None;mode:str
class RMNudges(BaseModel):
    nudges:list[RMNudge];method:str
class RMNudgeAction(StrictRM):
    base_version:int=Field(ge=1)
    request_key:str=Field(min_length=8,max_length=100)
    action:Literal['EXPLORE','REQUEST_RM','DISMISS']
    share_with_rm:bool=False

class RMCustomerRequest(BaseModel):
    id:str;message:str;status:str;created_at:str;updated_at:str;due_at:str|None;mode:str
class RMCustomerRequests(BaseModel):
    requests:list[RMCustomerRequest];boundary:str

class RMEngagementProfile(BaseModel):
    version:int;goal:str;horizon:str;interests:list[str];share_context:bool;source_id:str|None;topic_snoozes:dict[str,str];commercial_allowed:bool
class RMContextUpdate(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100)
    goal:str=Field(default='',max_length=500);horizon:str=Field(default='',max_length=100)
    interests:list[str]=Field(default_factory=list,max_length=8);share_context:bool=False
class RMEnrichedNudge(RMNudge):
    family:str;topic:str;category:str;expires_at:str;primary:bool=False;can_request_rm:bool=True
class RMDecisionItem(BaseModel):
    nudge_id:str;family:str;category:str;result:str;reason:str
    source_versions:list[list[str|int]]=Field(default_factory=list);expires_at:str|None=None
class RMInsight(BaseModel):
    key:str;title:str;status:str;explanation:str;currency:str|None=None;values:dict[str,str];rows:list[dict[str,str]]=Field(default_factory=list);series:list[dict[str,str]]=Field(default_factory=list);source:RMSource|None=None;method:str;kind:str|None=None;evidence:dict[str,Any]|str|None=None
class RMComparison(BaseModel):
    title:str;education:str;ownership:str;eligibility:str;terms_status:str;source:RMSource
class RMEngagementFeed(BaseModel):
    profile:RMEngagementProfile;nudges:list[RMEnrichedNudge];decisions:list[RMDecisionItem];decision_id:str;method:str;insights:list[RMInsight];comparisons:list[RMComparison]
class RMFeedbackRequest(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100)
    action:Literal['HELPFUL','NOT_RELEVANT','SNOOZE','DISMISS','OPT_OUT','EXPOSED']
    nudge_id:str|None=None;days:int=Field(default=7,ge=1,le=90)
class RMFeedbackReceipt(BaseModel):
    id:str;action:str;profile_version:int;message:str
class RMBriefFact(BaseModel):
    kind:str;text:str;source:RMSource|None=None
class RMBrief(BaseModel):
    party_id:str;why_now:str;facts:list[RMBriefFact];questions:list[str];constraints:list[str];next_action:str;contacts:list['RMContactRecord'];timeline:list[RMBriefFact];source_review:bool;method:str
class RMContactRecord(BaseModel):
    id:str;channel:str;purpose:str;event:str;note:str;occurred_at:str;source_id:str
class RMContactRequest(StrictRM):
    request_key:str=Field(min_length=8,max_length=100);base_version:int=Field(ge=1)
    channel:Literal['IN_APP','PHONE','EMAIL','MEETING'];purpose:Literal['SERVICE','REQUESTED_DISCUSSION']
    event:Literal['PREPARED','CUSTOMER_DISCUSSION_RECORDED'];note:str=Field(min_length=3,max_length=800)
    occurred_at:str
class RMEngagementAudit(BaseModel):
    decisions:list[dict];metrics:list[RMMetric];method:str

class RMCategoryCorrection(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100)
    source_id:str;source_version:int=Field(ge=1);source_hash:str=Field(min_length=64,max_length=64)
    category:str=Field(min_length=1,max_length=80)

class RMRMContact(BaseModel):
    name:str;email:str|None;phone:str|None;email_href:str|None;phone_href:str|None;status:str;mode:str
class RMActivityRequest(StrictRM):
    request_key:str=Field(min_length=8,max_length=100)
    kind:Literal['PRODUCT_VIEW','RM_CONTACT_VIEW'];product:Literal['DEPOSIT','LOAN','SAVINGS','NONE']
class RMActivityReceipt(BaseModel):
    id:str;signal_id:str|None;mode:str;message:str
class RMBehaviorRow(BaseModel):
    kind:str;product:str;count:int;window:str;latest_at:str;mode:str;interpretation:str
class RMBehavior(BaseModel):
    events:list[RMBehaviorRow];signals:list[RMSignal];method:str

class RMIntentRule(StrictRM):
    id:str=Field(min_length=3,max_length=50,pattern=r'^[a-z0-9_-]+$');name:str=Field(min_length=3,max_length=100)
    keywords:list[str]=Field(min_length=1,max_length=20);route:Literal['SAVINGS','DEPOSIT','LOAN','SERVICE','CARD','WEALTH','CLARIFY']
    priority:int=Field(ge=1,le=100);enabled:bool=True
    steps:list[Literal['READ_KNOWLEDGE','READ_FINANCIAL_CONTEXT','ANSWER','ASK_CLARIFICATION','OFFER_RM_CONTACT','PROPOSE_SIGNAL']]=Field(min_length=1,max_length=6)
    question:str=Field(default='',max_length=240);examples:list[str]=Field(min_length=1,max_length=8)
class RMPolicyDefinition(StrictRM):
    rules:list[RMIntentRule]=Field(max_length=30)
    repeat_view_threshold:int=Field(default=5,ge=3,le=100);behavior_window_days:int=Field(default=7,ge=1,le=30)
    spending_change_percent:int=Field(default=25,ge=10,le=200);max_nudges:int=Field(default=3,ge=1,le=3)
    enabled_families:list[str]=Field(default_factory=lambda:['E'+str(n).zfill(2) for n in range(1,13)],max_length=12)
class RMGovernanceUpdate(StrictRM):
    base_version:int=Field(ge=1);definition:RMPolicyDefinition;reason:str=Field(min_length=3,max_length=800)
class RMGovernanceAction(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100);reason:str=Field(min_length=3,max_length=800)
class RMPolicyTest(StrictRM):
    question:str=Field(min_length=1,max_length=1500);use_draft:bool=True
class RMGovernance(BaseModel):
    version:int;definition:RMPolicyDefinition;tested:bool;tests:list[dict];release_id:str|None;release_version:int;history:list[dict];boundaries:list[str]
class RMPolicyPreview(BaseModel):
    route:str;rule_id:str;rule_name:str;steps:list[str];reason:str;guarded:bool;question:str;release_id:str|None;release_version:int;guardrails:list[str]=Field(default_factory=list);advice_requested:bool=False
class RMCapacityUpdate(StrictRM):
    base_version:int=Field(ge=1);dedicated_limit:int=Field(ge=1,le=5000);case_limit:int=Field(ge=1,le=500);pool_enabled:bool;reason:str=Field(min_length=3,max_length=800)
class RMCoverageUpdate(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100)
    mode:Literal['DEDICATED','POOL','DIGITAL'];rm_id:str|None=None;tier:Literal['STANDARD','AFFLUENT','HNW','PRIVATE']= 'STANDARD';reason:str=Field(min_length=3,max_length=800)
class RMAssignments(BaseModel):
    rms:list[dict];customers:list[dict];next_cursor:str|None;pool_cases:int;method:str
class RMPool(BaseModel):
    signals:list[RMSignal];capacity:int;active_cases:int;method:str
class RMPoolClaim(StrictRM):
    base_version:int=Field(ge=1);request_key:str=Field(min_length=8,max_length=100)
class RMNewSession(StrictRM):
    request_key:str=Field(min_length=8,max_length=100)
class RMChatSession(BaseModel):
    id:str;title:str;version:int;created_at:str;updated_at:str;turn_count:int;legacy:bool=False
class RMChatSessions(BaseModel):
    sessions:list[RMChatSession];next_cursor:str|None
class RMChatMemoryItem(BaseModel):
    session_id:str;title:str;date:str;message:str
class RMChatMemory(BaseModel):
    topics:list[str];items:list[RMChatMemoryItem]

class RMAIBriefTalkingPoint(BaseModel):
    text:str
    source_ids:list[str]

class RMAIBrief(BaseModel):
    party_id:str
    summary:str
    talking_points:list[RMAIBriefTalkingPoint]
    questions:list[str]
    cautions:list[str]
    sources:list[RMSource]
    mode:Literal['LIVE','SIMULATED']
    model:str
    prompt_version:str
    latency_ms:int
    generated_at:str
    method:str

class RMAIDraftRequest(StrictRM):
    channel:Literal['EMAIL','PHONE_SCRIPT']

class RMAIDraft(BaseModel):
    followup_id:str
    subject:str|None=None
    body:str
    source_ids:list[str]
    sources:list[RMSource]
    mode:Literal['LIVE','SIMULATED']
    model:str
    prompt_version:str
    latency_ms:int
    generated_at:str
    boundary:str

class RMPoiMatchedCustomer(BaseModel):
    id:str
    cif:str
    name:str
    segment:str
    relationship_owner_rm:bool

class RMPoiPlace(BaseModel):
    id:str
    name:str
    primary_type:str
    address:str
    latitude:str
    longitude:str
    distance_m:int
    phone_masked:str|None=None
    website:str|None=None
    rating:float|None=None
    rating_count:int|None=None
    match_status:str
    match_score:str|None=None
    match_reasons:list[str]=[]
    matched_customer:RMPoiMatchedCustomer|None=None
    prospect_id:str|None=None
    provider:str
    attribution:str
    fetched_at:str

class RMPoiCounts(BaseModel):
    existing_customer:int
    possible_match:int
    new_lead:int
    prospect:int

class RMPoiCenter(BaseModel):
    lat:float
    lng:float

class RMPoiNearby(BaseModel):
    provider:str
    attribution:str
    center:RMPoiCenter
    radius_m:int
    places:list[RMPoiPlace]
    counts:RMPoiCounts

class RMGeocodeResult(BaseModel):
    label:str
    latitude:str
    longitude:str

class RMGeocode(BaseModel):
    provider:str
    results:list[RMGeocodeResult]

class RMPoiCreateProspect(StrictRM):
    request_key:str=Field(min_length=8,max_length=100)
    confirm_not_customer:bool=False
    reason:str|None=Field(default=None,max_length=800)

class RMPoiMatchReview(StrictRM):
    request_key:str=Field(min_length=8,max_length=100)
    decision:Literal['CONFIRM_EXISTING','NOT_A_CUSTOMER']
    customer_id:str|None=None
    reason:str=Field(min_length=3,max_length=800)
