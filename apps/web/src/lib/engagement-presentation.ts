/** Display decimal strings without losing precision through Number coercion. */
export function insightValue(key:string,value:string,currency:string|null|undefined):string {
  const match=/^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if(!match)return value;
  const grouped=match[2].replace(/\B(?=(\d{3})+(?!\d))/g,',');
  const decimal=match[3]!==undefined&&/[1-9]/.test(match[3])?'.'+match[3]:'';
  const amount=match[1]+grouped+decimal;
  if(key.endsWith('_percent'))return amount+'%';
  if(/(_count|_day|_months|^days_|^months_)/.test(key))return amount;
  return currency?currency+' '+amount:amount;
}
export function insightLabel(key:string):string {
  const labels:Record<string,string>={
    available:'Available funds',
    commitments:'Upcoming commitments',
    difference:'Snapshot difference',
    previous_spend:'Previous period',
    current_spend:'Current period',
    change:'Amount changed',
    change_percent:'Percentage changed',
    amount:'Charge amount',
    headroom_until_payday:'Safe to spend until payday',
    payday:'Payday',
    days_to_payday:'Days until payday',
    expected_spending_until_payday:'Expected spending until payday',
    projected_30d_balance:'Projected 30-day balance',
    monthly_surplus_estimate:'Estimated monthly surplus',
    buffer_months:'Emergency buffer',
    goal_name:'Goal name',
    target_amount:'Target amount',
    saved_amount:'Amount saved',
    progress_percent:'Progress',
    required_monthly:'Required monthly',
    planned_monthly:'Planned monthly',
    shortfall_amount:'Shortfall amount',
    extra_monthly_needed:'Extra monthly needed',
    goal_status:'Goal status',
    months_left:'Months remaining',
    target_date:'Target date',
    outstanding_total:'Total outstanding',
    card_rate_percent:'Card interest rate',
    monthly_interest_cost:'Interest per month',
    minimum_payment_total:'Minimum payment',
    savings_interest_percent:'Savings interest rate',
    monthly_interest_earned_on_same_amount:'Interest earned on savings',
    buffer_months_after_repayment:'Buffer after repayment',
    months_to_clear_at_minimum:'Months to clear at minimum',
    interest_paid_at_minimum:'Interest paid at minimum',
    due_day:'Payment due day',
    total_value:'Portfolio value',
    total_cost:'Total cost',
    gain_loss:'Total return',
    gain_loss_percent:'Return',
    change_30d:'30-day change',
    change_30d_percent:'30-day return',
    equity_percent:'Equities',
    bond_percent:'Bonds',
    money_market_percent:'Money market',
    weakest_holding:'Lowest 30-day performer',
    weakest_change_30d_percent:'Lowest 30-day return',
    as_of:'As of',
    holdings_count:'Holdings count',
    net_worth:'Net worth',
    assets_total:'Total assets',
    liabilities_total:'Total liabilities',
    assets_change_30d:'30-day asset change',
    assets_change_30d_percent:'30-day asset change',
    savings_rate_percent:'Savings rate',
    debt_to_income_percent:'Debt-to-income ratio',
    total_spend:'Total spend',
    spend_to_income_percent:'Spend-to-income ratio',
    biggest_increase_category:'Highest increase category',
    biggest_increase_percent:'Highest increase',
    merchant_count:'Recurring merchants',
    monthly_total:'Repeats each month',
    bills_count:'Bills and subscriptions',
    bills_monthly_total:'Bills and subscriptions each month',
    regular_count:'Regular merchants',
    regular_monthly_total:'Regular spending each month',
    commitments_until_payday:'Bills due before payday',
    card_payment_until_payday:'Card payment due before payday',
    everyday_spending_until_payday:'Everyday spending until payday',
    goal_contributions_reserved:'Goal contributions set aside',
    goal_savings:'Goal savings pockets',
    discretionary_total:'Discretionary spend',
    label:'Description',
    target:'Target',
    saved:'Saved',
    status:'Status',
    rate_percent:'Interest rate',
    minimum_payment:'Minimum payment',
    asset_class:'Asset class',
    value:'Value',
    share_percent:'Share',
    cost:'Cost',
    monthly_estimate:'Monthly estimate',
    typical_amount:'Typical amount',
    times_90d:'Occurrences (90d)',
    next_expected:'Next expected date',
    rank:'Rank',
    topic:'Topic',
    action:'Action',
    reason:'Reason'
  };
  return labels[key]||key.replace(/_/g,' ');
}
export function suggestionCategory(category:string):string {
  return ({CARE:'Here to help',GUIDANCE:'Your plans',EDUCATION:'Banking essentials',RECOGNITION:'A moment for you',COMMERCIAL:'Product discussion'} as Record<string,string>)[category]||'For you';
}
export function localDateTimeValue(value:string|null|undefined):string {
  if(!value)return '';
  const date=new Date(value);if(!Number.isFinite(date.getTime()))return '';
  const pad=(n:number)=>String(n).padStart(2,'0');
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
