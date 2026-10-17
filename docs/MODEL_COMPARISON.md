# Gemini model comparison for NextRM

Latency, Singapore, cost and reliability of the Gemini models available on Vertex AI, measured against the real NextRM customer chat.

| Item | Value |
|---|---|
| Test window | 18 Oct 2026 (WIB), 02:30 to 03:45 |
| Production setting during the tests | `gemini-3.5-flash`, `asia-southeast1`, `GEMINI_THINKING_LEVEL=low`, 20 s model timeout (`GEMINI_TIMEOUT_MS` default) |
| Application under test | One structured-JSON Gemini call per chat turn (answer, route, source ids, need, interest flag, suggestions), temperature 0, about 9,300 input tokens |
| Prices | USD at list price from the Vertex pricing page and the Flex PayGo, Priority PayGo, locations and model pages, read on 18 Oct 2026. Not read from a bill. IDR at 17,977 per USD |
| Raw data | [`docs/model-comparison-data/`](model-comparison-data/): `replay-results.jsonl` (555 calls), `availability-probe.json` (78 calls), `quality-harness-runs.txt` |
| Status | This report was written from experiments already run. No new test was run for it. Statements about what Google *might* do are tagged `[INFERENCE]` |

## 1. Executive summary

**Decision: keep `gemini-3.5-flash` in `asia-southeast1` with thinking `low` for the submission.** It is the only setup that is both in Singapore and reliable. Every faster or cheaper model tested runs outside Singapore, and the one Singapore change that is faster (`minimal` thinking) fails too many questions.

1. **Singapore serves two models.** Only `gemini-3.5-flash` and `gemini-2.5-flash` answer on `asia-southeast1`. `gemini-3.5-flash-lite` answers in Mumbai. `gemini-3.1-flash-lite`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash` and `gemini-4-argon` answer on `global`, `us` and `eu` only. `gemini-3.8-flash-lite` does not exist as a text model.
2. **Latency in Singapore.** The current model takes 4.6 to 5.4 s per call at the median (p90 6.3 to 7.5 s, worst 8.4 s, no failure in 44 calls). A customer waits about 6.5 s per reply end to end. Thinking tokens are the cause: at `minimal` thinking the call takes 2.2 s.
3. **`minimal` thinking is not safe yet.** It passed 43 of 50 ten-question checks against 50 of 50 at `low` (Fisher exact p about 0.012). Four of the seven failures are the numeric-validator rejection described in section 4.4.
4. **Fastest models** are the Flash-Lite pair: `gemini-3.5-flash-lite` 1.6 to 1.7 s, `gemini-3.1-flash-lite` 2.3 s (p90 4.2 s). Neither runs in Singapore.
5. **Cheapest good model: `gemini-3.1-flash-lite` on `global`.** USD 0.0032 per turn (IDR 57), 88% below the current model, 30 of 30 on the ten questions, 2.3 s median. The cost is leaving Singapore.
6. **Gemini 4 Argon is not a chat candidate.** About USD 0.024 per turn now and USD 0.048 after the 30 Nov promo, 9.2 s median over three calls, global/us/eu only, no Flex, and its quality was not graded.
7. **Flex halves the price and multiplies latency by 3.3 to 7.5.** It is global-only, its median is 7.7 to 18.0 s, and 6 of 22 `gemini-3.5-flash` Flex calls would exceed the app's 20 s timeout. It does not fit an interactive chat. **Priority** was accepted but served as Standard on all 43 calls.
8. **The 3.6, 3.7 and 3.8 Flash promo** (USD 0.75 / 3.75 per 1M tokens until 31 Dec 2026, then 1.50 / 7.50) is real, but only 3.6 behaved: 2.6 s median, 28 of 30. 3.8 had a 55 s worst case and 3.7 had server errors.
9. **Reliability of the current setting** is 114 of 120 questions (95.0%, Wilson 95% interval 89.5% to 97.7%) over twelve local runs, and 50 of 50 in the last five sequential runs. Most failures are the app's own guardrail refusing an answer, not a wrong answer reaching the customer.
10. **Cost is not the lever at demo volume.** The whole spread between the current model and the cheapest good one is about IDR 420 per turn, so IDR 126k per 300 judge turns. Fixed infrastructure is about IDR 30k per day.

### If your priority is...

| Priority | Pick | Median model latency | USD (IDR) per turn | Ten-question result | Trade-off |
|---|---|---|---|---|---|
| Singapore and reliability (submission default) | `gemini-3.5-flash`, `asia-southeast1`, `low` | 4.6 to 5.4 s | 0.0265 to 0.0282 (476 to 507) | 114/120 pooled, 50/50 latest | Slowest of the good options |
| Singapore and speed | Same, `minimal` thinking | 2.2 s | 0.0190 (342) | 43/50 | 7 more failures per 50; needs the validator fix first |
| Lowest latency overall | `gemini-3.5-flash-lite`, Mumbai or `global` | 1.6 to 1.7 s | 0.0036 to 0.0039 (64 to 70) | 28/30 | Not Singapore; two answers omitted required content |
| Cheapest good model | `gemini-3.1-flash-lite`, `global` | 2.3 s (p90 4.2 s) | 0.0032 (57) | 30/30 | Not Singapore, no residency guarantee |
| Same class, simple | `gemini-3.6-flash`, `global` | 2.6 s | 0.0087 promo, 0.0174 after 1 Jan (156, 313) | 28/30 | Not Singapore; price doubles on 1 Jan 2027 |
| Possible quality ceiling (untested) | `gemini-4-argon` | 9.2 s (n=3) | 0.024 promo, 0.048 after 30 Nov (431, 863) | not graded | Slow, global, unknown quality |
| Background jobs only | Flex on any supported model | 7.7 to 18.0 s | half of Standard | same model | NextRM has no such call |

## 2. What was tested

| ID | Test | Setup | Size | Used for |
|---|---|---|---|---|
| T1 | Availability probe | One-word prompt to 13 model IDs on 6 endpoints: Singapore, Mumbai (`asia-south1`), Tokyo (`asia-northeast1`), `global`, `us`, `eu` | 78 calls | Where each model answers |
| T2 | Ten-question quality harness (`scripts/top10_questions.py --live`) | Local API on a disposable PostgreSQL database, live Vertex AI. Ten common customer money questions asked as the demo customer, plus a check that an RM handoff reaches the RM queue. Nine processes ran in parallel | 7 configs with 3 runs each and 2 configs with 1 run each (230 questions) | Pass rate and failure causes. Its latencies are inflated by the parallelism and are not used |
| T3 | In-region latency replay, run 1 | A Cloud Run job in `asia-southeast1` replays 11 real chat requests captured from the app, twice each, with the API's service account. Calls are sequential inside a config; configs ran in parallel. A random nonce in each system prompt defeats implicit caching | 19 configs, 379 calls | Model-call latency, tokens, cost per turn, Flex and Priority behaviour |
| T4 | Thinking level and region replay, run 2 | Same job. `minimal` against `low` thinking; Singapore, Tokyo, Mumbai and `global` for the same model | 8 configs, 176 calls | What drives latency; effect of region |
| T5 | Quality at `low` against `minimal` | Ten-question harness, five sequential runs each, `gemini-3.5-flash` in Singapore | 100 questions | Whether `minimal` is safe |
| T6 | Error capture | Three harness runs with a hook around every SDK request, to catch the Google error behind a `ClientError` on Q8 | 30 questions | Root cause (not found) |
| T7 | Document review | Vertex pricing page (Gemini 4, 3, 2.5, 2.0 tables), Flex PayGo, Priority PayGo, locations table, `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` model pages | | Prices, supported endpoints, documented limits |

**Replay mechanics.** A hook on the SDK's `BaseApiClient.request` captured the request bodies of the 11 model calls in a harness run: system instruction, contents (about 9,300 tokens on average), response schema and generation config (temperature 0, `maxOutputTokens` 5,120, thinking `low`). The job sends the same bodies over REST with only the model, endpoint, thinking level and headers changed. A new TLS connection is opened per call, as the app does. Flex used the headers `X-Vertex-AI-LLM-Request-Type: shared` and `X-Vertex-AI-LLM-Shared-Request-Type: flex`; the mode actually served is read from `usageMetadata.trafficType`. Thinking tokens are billed as output tokens.

**What the harness grades.** Per question: the route, required figures or phrases (a regular expression), forbidden patterns (a seven-digit decimal, the fallback sentence) and, for wealth questions, a referral to an advisor or RM. It also checks the RM handoff. It does not grade tone or the quality of reasoning.

### Limits of the evidence

- **Small samples.** 22 calls per replay config (11 prompts twice), 30 questions per model in T2, 3 calls for Argon. A 30/30 result has a 95% lower bound of about 89 to 91%, so it is not separable from a 93% model.
- **One customer.** All 11 prompts come from one synthetic customer's scenario. Other customers produce other prompts.
- **One time window.** About 75 minutes on one night. Vertex capacity and routing change over time.
- **Network paths.** Replay latency is model-call time from Cloud Run in Singapore. Harness latency includes my laptop's route to Vertex and the local API.
- **Unmeasured.** Implicit-cache savings (the nonce removed them), billing data, tone, Q8 `ClientError` root cause, quality of 3 Flash Preview, 3.1 Pro Preview and Argon.
- **List price.** Costs are tokens times list price. The promo models are billed as "50% credits back on net spend", so an invoice shows the list price and a credit line.

## 3. Results

### 3.1 Where each model answers (T1, live probe)

`yes` = HTTP 200. `no` = HTTP 404. `us` and `eu` are the multi-region endpoints.

| Model ID | Singapore | Mumbai | Tokyo | `global` | `us` | `eu` |
|---|---|---|---|---|---|---|
| `gemini-4-argon` | no | no | no | yes (see note) | yes | yes |
| `gemini-3.8-flash` | no | no | no | yes | yes | yes |
| `gemini-3.8-flash-lite` | no | no | no | no | no | no |
| `gemini-3.7-flash` | no | no | no | yes | yes | yes |
| `gemini-3.6-flash` | no | no | no | yes | yes | yes |
| `gemini-3.5-flash` | **yes** | yes | yes | yes | yes | yes |
| `gemini-3.5-flash-lite` | no | **yes** | no | yes | yes | yes |
| `gemini-3.1-flash-lite` | no | no | no | yes | yes | yes |
| `gemini-3-flash-preview` | no | no | no | yes | no | no |
| `gemini-3.1-pro-preview` | no | no | no | yes | no | no |
| `gemini-2.5-pro` | no | no | yes | yes | no | no |
| `gemini-2.5-flash` | **yes** | yes | yes | yes | no | no |
| `gemini-2.5-flash-lite` | no | no | no | yes (HTTP 400 on my thinking budget; the model exists) | no | no |
| `gemini-2.0-flash`, `gemini-2.0-flash-lite` | no | | | no | | |

- A blank cell means the endpoint was not probed. The 2.0 models were probed on Singapore and `global` only.
- Argon's one-word probe on `global` hit the 60 s client timeout once. The replay later answered 3 of 3.
- The API's service account worked on Singapore, Mumbai, Tokyo and `global` in the replay, so switching to those endpoints needs no new IAM role. The `us` and `eu` probes used my own credentials.
- Google's locations table agrees with the probe, and adds regions I did not probe (for example Montréal, London and Frankfurt for `gemini-3.5-flash`).
- Both `gemini-3.5-flash-lite` (in Mumbai) and `gemini-3.5-flash` (in Singapore) answered Standard calls with `trafficType` `ON_DEMAND`, although their model pages list Standard PayGo as `global`, `us` and `eu` only. I report what was observed; the pages may lag.
- `gemini-3.8-flash-lite-tts` (a speech model, `global`) is the only "3.8 Flash-Lite" SKU on Google's pages.

### 3.2 Full price list

USD per 1M tokens, input / output, prompts up to 200K tokens. "Regional" is the +10% price on non-global endpoints (Gemini 3 and later, since 1 Jul 2026). Flex has no regional price. 2.5 models have no regional split.

| Model | Standard, global | Standard, regional | Flex = Batch, global | Priority, global | Cached input |
|---|---|---|---|---|---|
| Gemini 4 Argon, until 30 Nov 2026 | 2.00 / 10.00 | 2.20 / 11.00 | no Flex; Batch 1.00 / 5.00 | 3.60 / 18.00 | 0.10 |
| Gemini 4 Argon, from 1 Dec 2026 | 4.00 / 20.00 | 4.40 / 22.00 | no Flex; Batch 2.00 / 10.00 | 7.20 / 36.00 | 0.20 |
| **3.8, 3.7, 3.6 Flash, promo until 31 Dec 2026** | **0.75 / 3.75** | 0.825 / 4.125 | 0.375 / 1.875 | 1.35 / 6.75 | 0.075 |
| 3.8, 3.7, 3.6 Flash, from 1 Jan 2027 | 1.50 / 7.50 | 1.65 / 8.25 | 0.75 / 3.75 | 2.70 / 13.50 | 0.15 |
| **3.5 Flash (current)** | 1.50 / 9.00 | **1.65 / 9.90** (Singapore) | 0.75 / 4.50 | 2.70 / 16.20 | 0.15 |
| 3.5 Flash-Lite | 0.30 / 2.50 | 0.33 / 2.75 | 0.15 / 1.25 | 0.54 / 4.50 | 0.03 |
| 3.1 Flash-Lite | 0.25 / 1.50 | 0.275 / 1.65 | 0.125 / 0.75 | 0.45 / 2.70 | 0.025 |
| 3 Flash Preview | 0.50 / 3.00 (1) | global only | 0.25 / 1.50 | 0.90 / 5.40 | 0.05 |
| 3.1 Pro Preview | 2.00 / 12.00 (2) | global only | 1.00 / 6.00 | 3.60 / 21.60 | 0.20 |
| 3.8 Flash-Lite | no text model | | | | |
| 2.5 Pro | 1.25 / 10.00 (2) | same | Batch 0.625 / 5.00 | 2.25 / 18.00 | 0.125 |
| 2.5 Flash | 0.30 / 2.50 | same | Batch 0.15 / 1.25 | 0.54 / 4.50 | 0.03 |
| 2.5 Flash-Lite | 0.10 / 0.40 | same | Batch 0.05 / 0.20 | 0.18 / 0.72 | 0.01 |
| 2.0 Flash / 2.0 Flash-Lite | 0.15 / 0.60 and 0.075 / 0.30 | same | Batch half | | not available to this project (404) |

1. The pricing page omits the 3 Flash Preview Standard output row. $3.00 is derived: its Flex output price of $1.50 is exactly 50% of Standard.
2. Over 200K tokens of context, 3.1 Pro Preview is 4.00 / 18.00 and 2.5 Pro is 2.50 / 15.00, for all tokens.

Notes:

- **Promo.** The page prices the 3.6, 3.7 and 3.8 Flash promo and the Argon promo as "50% credits back on net spend". The promo rate is the effective rate after the credit.
- **Flex coverage.** Flex PayGo supports `gemini-3.8-flash`, `3.7-flash`, `3.6-flash`, `3.5-flash`, `3.5-flash-lite`, `3.1-flash-lite`, `3-flash-preview`, `3.1-pro-preview` and the image models, on the `global` endpoint only. Argon and the 2.5 models get Batch (asynchronous), not Flex.
- **Audio input.** 3.1 Flash-Lite audio input is 0.50 (Flex 0.25); 3 Flash Preview audio is 1.00. NextRM sends text only.
- **Out of scope SKUs on the same page:** Live API (`gemini-3.8-live`, 2.5 Flash Live), speech (3.8 Flash TTS, 3.8 Flash-Lite TTS, 2.5 TTS), image (3.1 Flash Image, 3 Pro Image, Nano Banana 2.1, 3.1 Flash-Lite Image), Omni Flash previews, transcription and translation, embeddings, and the cyber variants (`gemini-3.8-flash-cyber`, `gemini-4-argon-cyber-permissive`, no promo).

### 3.3 Quality: ten questions and RM handoff (T2, T5, T6)

| Config | Runs | Passed | What failed |
|---|---|---|---|
| **3.5 Flash, Singapore, `low` (current)** | 12 local runs, pooled | **114/120 (95.0%)** | See below |
| ... T2 parallel runs | 3 | 28/30 | Q3 numeric validator (8,000,000); Q4 numeric validator (2,732,142.86) |
| ... capture run | 1 | 9/10 | Q8 `ClientError` |
| ... T6 error-capture runs | 3 | 27/30 | Q4 and Q2 refused by the app; Q6 content check. Reasons not captured |
| ... T5 sequential runs | 5 | **50/50** | none |
| 3.5 Flash, Singapore, `minimal` (T5) | 5 sequential | **43/50 (86%)** | 4 numeric validator (357,142.86 twice, 2,380,000 twice); 2 missing IDR 84,000 on Q6; 1 "unavailable binding action or unsupported assessment" on Q3 |
| 3.5 Flash, `global`, `low` | 3 | 28/30 | Q8 `ClientError`; Q4 numeric validator (357,142.86) |
| 3.5 Flash-Lite, `global` | 3 | 28/30 | Q10 omitted the 6.10% figure; Q6 omitted the advisor/RM referral |
| **3.1 Flash-Lite, `global`** | 3 | **30/30** | none |
| 3.6 Flash, `global` | 3 | 28/30 | Q4 numeric validator twice (931,666.67; 357,142.86) |
| 3.7 Flash, `global` | 3 | 26/30 | Four `ServerError` (Q8, Q9, Q10 in run 1; Q2 in run 2); the RM handoff failed in run 1 because no signal reached the RM |
| 3.8 Flash, `global` | 3 | 27/30 | `ServerError` on Q1; Q6 "unavailable binding action"; Q2 numeric validator (931,666.67) |
| 2.5 Flash, Singapore (thinking budget 1,024) | 1 | 6/10 | Three numeric validator (357,142.86; 375,000; "3.4%"); Q5 missing IDR 10,399,000 |
| 2.5 Flash-Lite, `global` (budget 1,024) | 1 | 3/10 | Two "unauthorized or nonexistent source"; three missing required content; two numeric validator |
| 3 Flash Preview, 3.1 Pro Preview, Argon | | not graded | Replay only: all JSON valid |

Reading the table:

- Differences between 26/30 and 30/30 at n=30 are mostly noise. Distinguishable results: both 2.5 models fail; `minimal` fails more than `low` (7 against 0 in 50 sequential questions each, p about 0.012); 3.1 Flash-Lite has the only clean sweep.
- The harness counts four different failure kinds (section 4.4): a guardrail refusal, a delivered answer that omits required content, a provider error, and a source-binding error.

### 3.4 Latency and cost per turn (T3, T4)

Model-call time from a Cloud Run job in `asia-southeast1`, with the app's real prompts (about 9,300 input tokens). 22 calls per row unless stated. "Over 20 s or failed" counts calls that would hit the app's 20 s timeout. USD per turn uses the measured mean tokens and the list price of the endpoint class. "After promo" is the same turn at the post-promo price.

| Config | OK/total | Median s | p90 s | Max s | Over 20 s or failed | Thinking tokens | Answer tokens | USD per turn | IDR per turn | USD after promo |
|---|---|---|---|---|---|---|---|---|---|---|
| **Standard, Singapore** | | | | | | | | | | |
| **3.5 Flash, `low` (current), run 1** | 22/22 | **4.6** | 6.3 | 7.6 | 0 | 748 | 370 | 0.0265 | 476 | |
| 3.5 Flash, `low`, run 2 | 22/22 | 5.4 | 7.5 | 8.4 | 0 | 925 | 371 | 0.0282 | 507 | |
| 3.5 Flash, `minimal` | 22/22 | **2.2** | 2.4 | 2.6 | 0 | 0 | 368 | 0.0190 | 342 | |
| 2.5 Flash (budget 1,024) | 22/22 | 5.1 | 5.8 | 6.2 | 0 | 686 | 361 | 0.0054 | 96 | |
| **Standard, other Asia endpoints** | | | | | | | | | | |
| 3.5 Flash, Tokyo, `low` | 22/22 | 5.2 | 7.6 | 8.9 | 0 | 698 | 376 | 0.0260 | 468 | |
| 3.5 Flash, Mumbai, `low` | 22/22 | 5.3 | 7.5 | 8.6 | 0 | 690 | 367 | 0.0259 | 465 | |
| 3.5 Flash-Lite, Mumbai, `low` | 22/22 | 1.6 | 1.8 | 1.9 | 0 | 0 | 292 | 0.0039 | 70 | |
| 3.5 Flash-Lite, Mumbai, `minimal` | 22/22 | 1.6 | 1.8 | 1.9 | 0 | 0 | 302 | 0.0039 | 70 | |
| **Standard, `global`** | | | | | | | | | | |
| 3.5 Flash, `low` | 19/22 | 5.0 | 6.5 | 7.9 | **3 stalled over 60 s** | 635 | 372 | 0.0233 | 418 | |
| 3.5 Flash, `minimal` | 21/22 | 2.6 | 3.1 | 3.4 | 1 (HTTP 429) | 0 | 381 | 0.0174 | 312 | |
| 3.5 Flash-Lite, `low` | 22/22 | 1.7 | 1.8 | 1.8 | 0 | 0 | 309 | 0.0036 | 64 | |
| **3.1 Flash-Lite, `low`** | 22/22 | 2.3 | 4.2 | 5.6 | 0 | 263 | 309 | **0.0032** | **57** | |
| 3.1 Flash-Lite, `minimal` | 22/22 | 1.8 | 2.0 | 2.1 | 0 | 0 | 289 | 0.0028 | 50 | |
| 3.6 Flash, `low` | 22/22 | 2.6 | 3.8 | 4.9 | 0 | 82 | 368 | 0.0087 | 156 | 0.0174 |
| 3.6 Flash, `minimal` | 22/22 | 2.6 | 2.8 | 5.1 | 0 | 0 | 381 | 0.0084 | 151 | 0.0168 |
| 3.7 Flash, `low` | 22/22 | 4.3 | 7.7 | 9.0 | 0 | 0 | 406 | 0.0085 | 153 | 0.0170 |
| 3.8 Flash, `low` | 22/22 | 4.3 | **23.4** | **55.4** | 4 | 0 | 401 | 0.0085 | 153 | 0.0170 |
| 3 Flash Preview, `low` | 22/22 | 3.0 | 3.6 | 4.7 | 0 | 0 | 357 | 0.0057 | 103 | |
| Gemini 4 Argon, `low` (3 calls, the 3 shortest prompts) | 3/3 | 9.2 | 13.1 | 13.1 | 0 | 0 | 536 | 0.0240 (3) | 431 | 0.0480 |
| **Flex, `global`** | | | | | | | | | | |
| 3.5 Flash-Lite | 22/22 | 7.7 | 9.8 | 29.4 | 1 | 0 | 296 | 0.0018 | 32 | |
| 3.1 Flash-Lite | 22/22 | 17.3 | 18.7 | 20.6 | 1 | 227 | 317 | 0.0016 | 28 | |
| 3.5 Flash | 22/22 | 18.0 | 32.1 | 48.3 | **6** | 666 | 364 | 0.0116 | 209 | |
| 3.6 Flash | 22/22 | 9.2 | 12.2 | 13.5 | 0 | 326 | 376 | 0.0048 | 87 | 0.0096 |
| 3.8 Flash | 22/22 | 14.2 | 19.5 | 31.5 | 2 | 0 | 405 | 0.0043 | 77 | 0.0085 |
| **Priority header, `global` (served as Standard)** | | | | | | | | | | |
| 3.5 Flash | 19/22 | 5.8 | 8.8 | 10.5 | 3 (1 HTTP 429, 2 stalled) | 889 | 365 | 0.0251 (4) | 450 | |
| 3.5 Flash-Lite | 22/22 | 1.6 | 1.8 | 1.9 | 0 | 0 | 304 | 0.0036 (4) | 64 | |
| 3.5 Flash, Singapore (2 calls) | 2/2 | 5.8 | 7.1 | 7.1 | 0 | 950 | 414 | 0.0244 (4) | 439 | |

3. Argon ran only the three shortest prompts (mean 7,623 input tokens). The raw cost on those prompts is USD 0.0206. The value shown is normalised to the 9,327-token average prompt: 9,327 input tokens at USD 2.00 plus 536 output tokens at USD 10.00 per 1M.
4. Priced as Standard because `trafficType` was `ON_DEMAND` on every call, not `ON_DEMAND_PRIORITY`.

### 3.5 What drives latency (T4)

Same prompts, same answer length (about 370 tokens), different thinking:

| 3.5 Flash in Singapore | Thinking tokens | Median s | p90 s | USD per turn |
|---|---|---|---|---|
| `low`, run 1 | 748 | 4.6 | 6.3 | 0.0265 |
| `low`, run 2 | 925 | 5.4 | 7.5 | 0.0282 |
| `minimal` | 0 | 2.2 | 2.4 | 0.0190 |

- Between the two `low` runs, 177 more thinking tokens coincided with 0.8 s more latency. Between `low` and `minimal`, 748 to 925 thinking tokens coincided with 2.4 to 3.2 s, about 3.2 to 3.5 ms per thinking token [derived from these rows, not a Google figure].
- At `minimal` the call is 52% to 59% faster than at `low` (2.2 s against 4.6 s in run 1 and 5.4 s in run 2) and 33% cheaper in the same run (0.0190 against 0.0282). Answer length did not change (742 against 739 characters).
- The Flash-Lite models already sit near the floor. Their `minimal` rows differ little from `low`, except that 3.1 Flash-Lite's p90 tightens from 4.2 s to 2.0 s.
- Region does not matter for `gemini-3.5-flash`: Singapore 5.4 s, Tokyo 5.2 s, Mumbai 5.3 s in the same run. Singapore carries no latency penalty.
- Quality was graded only for 3.5 Flash in Singapore at `minimal` (section 3.3). The other `minimal` rows are latency-only.

### 3.6 Flex and Priority (T3, T7)

| Model | Standard median / p90 / max (s) | Flex median / p90 / max (s) | Slower by | Flex USD per turn | Standard USD per turn | Flex calls over 20 s |
|---|---|---|---|---|---|---|
| 3.5 Flash-Lite | 1.7 / 1.8 / 1.8 | 7.7 / 9.8 / 29.4 | 4.5x | 0.0018 | 0.0036 | 1 of 22 |
| 3.1 Flash-Lite | 2.3 / 4.2 / 5.6 | 17.3 / 18.7 / 20.6 | 7.5x | 0.0016 | 0.0032 | 1 of 22 |
| 3.5 Flash (against `global` Standard) | 5.0 / 6.5 / 7.9 | 18.0 / 32.1 / 48.3 | 3.6x | 0.0116 | 0.0233 | **6 of 22 (27%)** |
| 3.6 Flash (promo) | 2.6 / 3.8 / 4.9 | 9.2 / 12.2 / 13.5 | 3.5x | 0.0048 | 0.0087 | 0 of 22 |
| 3.8 Flash (promo) | 4.3 / 23.4 / 55.4 | 14.2 / 19.5 / 31.5 | 3.3x | 0.0043 | 0.0085 | 2 of 22 |

- **Flex worked as documented.** All 110 Flex calls reported `ON_DEMAND_FLEX`. The price is half of Standard. The latency is a constant penalty on top of the model time: 3.1 Flash-Lite took 16.8 to 20.6 s on every call, 3.5 Flash-Lite about 7.6 s on most.
- **Google's documentation says the same.** Flex is for "non-critical workloads that can tolerate longer response times and higher throttling". It supports only the `global` endpoint, allows a request timeout up to 30 minutes, and has its own quota of 3,000 QPM per base model per project.
- **Priority did nothing for this project.** The header was accepted on all 43 successful calls, but every response reported `ON_DEMAND`. Latency matched Standard (3.5 Flash-Lite 1.6 s; 3.5 Flash 5.8 s) and the cost would be Standard. Google's page says Priority is generally supported on `global`, `us` and `eu`; Singapore is not listed. [INFERENCE] the project may not meet an eligibility condition; this was not checked.
- **Batch** was not tested. It is asynchronous and unsuitable for chat.

### 3.7 Reliability incidents

| Incident | Where | Count | Note |
|---|---|---|---|
| Call stalled over the 60 s client timeout | 3.5 Flash, `global`, Standard | 3 of 22 | None on Singapore (0 of 44) |
| Call stalled over 60 s | 3.5 Flash, `global`, Priority header | 2 of 22 | |
| HTTP 429 `RESOURCE_EXHAUSTED` | 3.5 Flash, `global` (Priority header and `minimal` runs) | 2 | [INFERENCE] a Standard PayGo usage-tier limit on the global endpoint |
| Heavy tail | 3.8 Flash, `global` | p90 23.4 s, max 55.4 s, 4 of 22 over 20 s | |
| `ServerError` | 3.7 Flash, 3.8 Flash (T2) | 4 and 1 | One 3.7 run lost the RM handoff |
| `ClientError` on Q8 | 3.5 Flash, `global` and Singapore (T2) | 2 | Not reproduced in 13 later runs. Replaying the same body succeeded in every config. T6 found no SDK-level exception. Cause unknown |
| One-word probe timeout | Argon, `global` | 1 | The next 3 calls succeeded |

### 3.8 Answer style (T2 samples, Q5 and Q10)

All three samples refuse a buy, sell or hold call, cite the same figures and refer the customer to an advisor.

- **3.5 Flash** writes three to four short paragraphs: the facts, the market note, the goal shortfall, then an offer to involve the RM.
- **3.1 Flash-Lite** writes one dense paragraph, opens with the customer's first name and ends with a question about the time horizon.
- **3.6 Flash** uses a bullet list of holdings and, in Q10, repeated the word "synthetic" from the market note's title to the customer.

## 4. Findings by point of view

### 4.1 Latency and Singapore

- **The constraint is real.** Only two models answer in Singapore (section 3.1). Everything cheaper or faster is on `global`, `us` or `eu`; `gemini-3.5-flash-lite` also answers in Mumbai.
- **The current setup is steady.** 44 of 44 calls succeeded, the worst took 8.4 s, and the p90 stayed under 7.5 s. A customer sees about 6.5 s per reply (median; p90 9.4 s, worst 13.3 s over 50 sequential questions from the local harness). `minimal` thinking brings that to 4.1 s (p90 6.5 s). The gap between model time and reply time is about 1.5 to 2 s of retrieval, database and validation work.
- **The global endpoint is less steady for the same model.** 3.5 Flash on `global` had the same median (5.0 s) but 3 of 22 calls stalled beyond 60 s, and two other global calls returned HTTP 429. With the app's 20 s timeout those turns fail with the fallback message. Google's locations page says the global endpoint "can improve overall availability and reduce resource exhausted (429) errors"; this small sample showed the opposite. It is the strongest reason not to move `gemini-3.5-flash` to `global` for a small saving.
- **Thinking, not size, sets latency.** The Flash-Lite models are fast mainly because they think little (0 to 263 tokens). With thinking removed, 3.5 Flash in Singapore reaches 2.2 s, within 0.5 s of Flash-Lite.
- **Reply time also includes a cold start.** After the API scaled to zero, the first request took 5.1 s against 0.45 s warm (measured separately on 18 Oct, see `docs/DEPLOY.md`). Warm the API before judging or recording.

Suggestion: keep Singapore at `low`. If you need a Singapore reply under 3 s, fix the numeric validator first (section 4.4) and re-test `minimal`.

### 4.2 Gemini 4 Argon

| Fact | Value | Source |
|---|---|---|
| Model ID | `gemini-4-argon` | Locations table |
| Endpoints | `global`, `us`, `eu`. Not Singapore, Mumbai or Tokyo | T1 and locations table |
| Standard price | USD 2.00 / 10.00 until 30 Nov 2026; USD 4.00 / 20.00 from 1 Dec 2026; regional +10% | Pricing page |
| Priority and Batch | Priority 3.60 / 18.00 (7.20 / 36.00 later); Batch 1.00 / 5.00 (2.00 / 10.00 later); no Flex | Pricing page, Flex page |
| Cost per average turn | USD 0.024 (IDR 431) now; USD 0.048 (IDR 863) from 1 Dec | T3, normalised (3) in section 3.4 |
| Latency | 8.6, 9.2 and 13.1 s on the three shortest prompts | T3 |
| Output | Valid JSON 3 of 3; 887 to 1,063 characters against about 740 for the others; 0 thinking tokens at `low` | T3 |
| Quality | Not graded on the ten questions | |
| Reliability | One 60 s timeout on a one-word prompt, then 3 of 3 succeeded | T1, T3 |

**Finding.** Argon costs about as much as the current model during the promo (-9%) and 1.8 times as much after it. It is about twice as slow as the current model and 4 to 6 times slower than Flash-Lite, it is not in Singapore, and nothing shows it is more reliable on this task. Its quality is unmeasured, so a quality advantage is unproven.

**Suggestion.** Do not use it for the customer chat. A hypothesis for later, not tested: as an offline quality judge for the AI-quality panel, where latency does not matter. That would need its own ten-question-style test and a cost check after 30 Nov.

### 4.3 Cheapest yet good model

"Good" here means at least 27 of 30 on the ten questions, no provider failures, no stalls, and p90 under 5 s. Cost is per average turn at list price.

| Model (endpoint) | USD (IDR) per turn | Against current | Per 1,000 turns (IDR) | Ten-question | p90 s | Verdict |
|---|---|---|---|---|---|---|
| 2.5 Flash-Lite (`global`) | 0.0012 (22), from T2 token counts | -95% | 22k | 3/10 | n/a | Cheapest, not good |
| **3.1 Flash-Lite (`global`)** | **0.0032 (57)** | **-88%** | **57k** | **30/30** | 4.2 | **Cheapest good** |
| 3.5 Flash-Lite (`global`) | 0.0036 (64) | -86% | 64k | 28/30 | 1.8 | Good, but two answers omitted required content |
| 3.5 Flash-Lite (Mumbai) | 0.0039 (70) | -85% | 70k | 28/30 (global run) | 1.8 | Same, with a regional endpoint |
| 2.5 Flash (Singapore) | 0.0054 (96) | -80% | 96k | 6/10 | 5.8 | Not good |
| 3 Flash Preview (`global`) | 0.0057 (103) | -78% | 103k | not graded | 3.6 | Worth a test; a preview model |
| 3.6 Flash (`global`, promo) | 0.0087 (156) | -67% | 156k | 28/30 | 3.8 | Good; -34% only after 1 Jan |
| 3.7, 3.8 Flash (`global`, promo) | 0.0085 (153) | -68% | 153k | 26/30, 27/30 | 7.7, 23.4 | Not good: errors and tail |
| 3.5 Flash (`global`) | 0.0233 (418) | -12% | 418k | 28/30 | 6.5 | Not worth the stalls |
| 3.5 Flash, Singapore, `minimal` | 0.0190 (342) | -28% | 342k | 43/50 | 2.4 | Not good yet |
| **3.5 Flash, Singapore, `low` (current)** | 0.0265 (476) | 0% | 476k | 114/120 | 6.3 | **Cheapest good in Singapore** |

(`minimal` against `low` in the same run is -33%; the -28% above compares with run 1.)

**Finding.** `gemini-3.1-flash-lite` is the cheapest model that is also good. It has the only 30/30 sweep, a 2.3 s median, no failure in 44 calls (22 at `low`, 22 at `minimal`), and the lowest per-turn cost of any model that passed. Its caveats are the missing Singapore endpoint, the lack of a residency guarantee (section 4.7), a one-paragraph style, and a documented retirement date of 7 May 2027 or later. Inside Singapore, the current model is the only good option.

**Not tested, could lower the cost further.** Implicit caching of the repeated prompt prefix (cached input costs 10% of the input price). The replay disabled it on purpose.

### 4.4 Quality and reliability

**Failure kinds seen across 370 graded questions.**

| Kind | Examples | Who hits it | What the customer sees |
|---|---|---|---|
| Numeric validator refusal. The model computed a total or gap itself and the app rejected the number as unsupported | 357,142.86; 2,732,142.86; 931,666.67; 8,000,000; 2,380,000; 375,000; "3.4%" | Every model, including the current one; more often at `minimal` | "I could not answer that reliably..." |
| Delivered answer missing required content | 6.10% figure; advisor or RM referral; IDR 84,000; IDR 10,399,000 | 3.5 Flash-Lite, 2.5 models, `minimal` | An answer that passed the app's checks but omits something the test requires |
| Source-binding or action refusal | "unauthorized or nonexistent source"; "unavailable binding action or unsupported assessment" | 2.5 Flash-Lite, 3.8 Flash, `minimal` | The fallback message |
| Provider error | `ServerError`, `ClientError` | 3.7 Flash, 3.8 Flash; `ClientError` on 3.5 Flash twice | The fallback message |

- **Most failures are safe failures.** The app refuses to show an answer it cannot support; it does not show a wrong figure. The cost is availability (about 5% of questions at the current setting).
- **The main cause is fixable in code.** The numeric validator rejects numbers that are not in the cited sources, the finance context, the message or the declared goal. When the model adds up or subtracts, the result is not in that corpus. The same numbers recur across models (357,142.86 appears in five configs). A deterministic total and gap in the goal-progress card (`services/api/app/services/planning.py`), so the model quotes figures instead of computing them, should remove most numeric refusals for every model. This is a hypothesis; it has not been built or measured.
- **The Q8 `ClientError` is unexplained.** It appeared twice in the first runs and never in 13 later ones. The app records only the exception type, so the HTTP status is lost. Recording the status code would make the next occurrence diagnosable.
- **Earlier claims are overstated.** The README, `docs/ARCHITECTURE.md`, `docs/DEPLOY.md` and the deck say "10 of 10 live". That was true for one run. Pooled over twelve runs at the current setting, 95.0% of questions pass.

### 4.5 Flex, Priority and Batch

- **Flex suits background work only.** It cuts the price in half, but multiplies the median latency by 3.3 to 7.5, lifts the worst case to 20 to 48 s, and works only on `global`.
- **Against the 20 s app timeout** (not overridden by the deploy script), 6 of 22 `gemini-3.5-flash` Flex calls would fail. The two Flash-Lite Flex models would fail 1 call in 22 each, and 3.1 Flash-Lite's typical call (17.3 s) leaves 2.7 s of margin.
- **The saving is small.** Flex saves IDR 28 to 32 per turn on Flash-Lite and IDR 267 on `gemini-3.5-flash` (476 to 209). At 300 turns that is IDR 8k to 80k.
- **NextRM has no Flex-shaped call.** The evaluation worker re-uses the interactive chat path and records its latency, so a Flex client would distort the quality panel's latency numbers. RM brief and draft calls are interactive.
- **Priority** was not effective (section 3.6). Do not plan around it.
- **Flash-Lite against Flex, directly.** Standard 3.5 Flash-Lite (1.7 s, IDR 64) beats Flex 3.5 Flash (18.0 s, IDR 209) on both latency and cost. Standard Flash-Lite is the better "cheap" choice, and Flex Flash-Lite is only useful if both latency and residency are irrelevant.

### 4.6 The 3.6, 3.7 and 3.8 Flash promo

| Model | Promo to 31 Dec 2026 | From 1 Jan 2027 | Behaviour in the tests |
|---|---|---|---|
| 3.6 Flash | 0.75 / 3.75 (USD 0.0087 per turn) | 1.50 / 7.50 (USD 0.0174) | 2.6 s median, p90 3.8 s, 28/30. Cleanest of the three |
| 3.7 Flash | same | same | 4.3 s median, p90 7.7 s, 26/30, four `ServerError` |
| 3.8 Flash | same | same | 4.3 s median, p90 23.4 s, max 55.4 s, 27/30, one `ServerError` |

- **The promo is a credit.** The invoice shows the list price and a 50% credit line, so the saving appears only after the credit posts.
- **The saving halves on 1 Jan 2027.** For 3.6 Flash the advantage over the current model falls from -67% to -34%, which is much less than Flash-Lite's -86 to -88%.
- **All three are `global`, `us` and `eu` only,** like Flash-Lite, without Flash-Lite's price.
- **Pick 3.6 over 3.7 or 3.8** if you want this class. 3.8 is the newest but showed the worst tail, [INFERENCE] likely new-model capacity.

### 4.7 Data residency for a BFSI story

| Option | Where the call is processed (per Google's pages) | Deck wording |
|---|---|---|
| 3.5 Flash on `asia-southeast1` | The model page lists `asia-southeast1` under ML processing, so processing is in Singapore | Matches "Gemini 3.5 Flash on Vertex AI (asia-southeast1)" |
| 3.5 Flash-Lite on `asia-south1` | Mumbai; the model page lists ML processing in `asia-south1` and the `us` and `eu` multi-regions | Needs rewording (India) |
| Any model on `global` | Google: "you can't control or know which region your ML processing requests are sent to" | Needs rewording |
| 3.1 Flash-Lite | The model page lists ML processing in the US and EU multi-regions only | Needs rewording |

Google's locations page also warns that endpoints in general "don't guarantee data residency or in-region ML processing", so the ML processing list on the model page is the value to check. All demo data is synthetic, so the demo itself carries no residency risk. The wording matters for the BFSI narrative and for what a real bank would need. This is not legal advice; a real deployment needs its own regulatory review.

### 4.8 Cost at demo and production scale

| Model | Per 300 judge turns (IDR) | Per 1,000 turns (USD) | Per 1,000,000 turns (USD) |
|---|---|---|---|
| 3.5 Flash, Singapore, `low` (current) | 143k | 26.5 | 26,500 |
| 3.5 Flash, Singapore, `minimal` | 103k | 19.0 | 19,000 |
| 3.6 Flash, `global` (promo / after) | 47k / 94k | 8.7 / 17.4 | 8,700 / 17,400 |
| 3.5 Flash-Lite, `global` | 19k | 3.6 | 3,600 |
| 3.1 Flash-Lite, `global` | 17k | 3.2 | 3,200 |
| Argon (promo / after) | 129k / 259k | 24.0 / 48.0 | 24,000 / 48,000 |

- **At demo volume cost is a rounding error.** 300 judge turns on the current model cost IDR 143k, against about IDR 30k per day of fixed infrastructure (from the cost review in `docs/DEPLOY.md`).
- **At production scale it is not.** Per million turns the gap between the current model and 3.1 Flash-Lite is about USD 23,000, so a bank would move to Flash-Lite after a residency and quality review.
- **The testing itself cost** about USD 12 at list price (IDR 215k): 548 successful replay calls at USD 6.1, plus about 370 graded harness turns at roughly USD 5.9.

### 4.9 Operations: switching, rollback and monitoring

- **Switch with one deploy.** The deploy script reads `GEMINI_MODEL`, `GEMINI_LOCATION` (it sets `GOOGLE_CLOUD_LOCATION`) and `GEMINI_THINKING_LEVEL`. The API-only redeploy took about 66 s earlier. Re-run the smoke test and the ten questions on the deployed URL afterwards.
- **Roll back** by sending traffic to the revision that served before the change (today `nextrm-api-00013-8ct`).
- **Thinking parameters differ by family.** Gemini 3 models take `GEMINI_THINKING_LEVEL`; 2.5 models take `GEMINI_THINKING_BUDGET` (2.5 Flash-Lite rejects a budget below 512). The engine prefers the budget when both are set. 3.5 Flash-Lite ignores a custom temperature, top-K and top-P and rejects penalty settings (the app sends temperature 0, which is ignored).
- **Retirement.** Per their model pages: `gemini-3.5-flash` "May 19, 2027 or later", `gemini-3.5-flash-lite` "July 21, 2027 or later", `gemini-3.1-flash-lite` "May 7, 2027 or later". Preview models (`3-flash-preview`, `3.1-pro-preview`) can change sooner.
- **Monitor** `trafficType` in responses, the AI-admin panel's latency and error counts, and the share of "could not answer reliably" turns.

## 5. Recommendations

### Before the deadline (19 Oct 2026, 01:29 WIB)

1. **Keep the production model setting unchanged**: `gemini-3.5-flash`, `asia-southeast1`, thinking `low`, Standard PayGo. It matches the deck and has the best reliability on the ten questions.
2. **Restate the "10 of 10 live" claims** in the README, `docs/ARCHITECTURE.md`, `docs/DEPLOY.md` and the deck as a dated snapshot. Suggested wording: "95% of 120 questions passed over twelve local runs on 18 Oct 2026 (50 of 50 in the last five)". Failures are refusals by the app's own guardrails.
3. **Warm up and reset before recording.** Run `scripts/gcp/reset-demo-data.sh --yes`, then send one request to the API (a cold request takes about 5 s), then record.
4. **Do not change to a Flash-Lite model, to `global`, to Flex or to `minimal` now.** Each one changes the "Singapore" claim, the quality profile or both, and none was verified end to end on the deployed app.

### Decisions for you

| Decision | Options | My view |
|---|---|---|
| Fix the numeric validator by giving the model pre-computed totals and gaps | Yes (about 1 to 2 hours: `planning.py`, redeploy, ten-question runs) / No | Yes if time allows. It lifts reliability for every model and is the only route to Singapore at 2.2 s |
| Speed over the Singapore claim | Stay in Singapore / `gemini-3.1-flash-lite` on `global` / `gemini-3.5-flash-lite` in Mumbai | Stay in Singapore for the submission |
| Plan B rehearsal | Rehearse `gemini-3.1-flash-lite` on a no-traffic tagged revision, or skip | Optional and low risk, but not free of side effects: `gcloud run services update nextrm-api --region asia-southeast1 --no-traffic --tag fast --update-env-vars GEMINI_MODEL=gemini-3.1-flash-lite,GOOGLE_CLOUD_LOCATION=global`. The live revision keeps serving, but the web service reaches the API through the main URL, so you must call the tagged URL directly with an identity token. [INFERENCE] a no-traffic update pins traffic to the current revision, so a later deploy would get no traffic until you restore automatic routing with `gcloud run services update-traffic nextrm-api --region asia-southeast1 --to-latest` |

### After the submission

1. Fix the validator, then re-test `minimal` thinking with at least 100 questions per setting.
2. If a residency review accepts `global` or Mumbai, move to `gemini-3.1-flash-lite` (or hardened `gemini-3.5-flash-lite`) and keep `low` thinking.
3. Grade `gemini-3-flash-preview` (USD 0.0057 per turn, 3.0 s median, never graded) and, for the offline quality-judge idea only, Argon.
4. Record the HTTP status on provider failures so a `ClientError` is diagnosable.
5. Measure implicit caching on the live path, and repeat the replay at different times of day with larger samples.
6. Find out why Priority was served as Standard, if a low-latency tier is ever needed.

### Do not use

| Option | Why |
|---|---|
| Flex for chat | 3.3 to 7.5 times slower; 27% of `gemini-3.5-flash` Flex calls exceed the 20 s timeout |
| Priority | No effect for this project |
| `gemini-3.5-flash` on `global` | Same median, 3 stalls in 22 calls, only 12% cheaper |
| 2.5 Flash, 2.5 Flash-Lite | 6/10 and 3/10 on the ten questions |
| 3.7 Flash, 3.8 Flash | Server errors and a 55 s worst case |
| Argon for chat | Slow, unmeasured quality, price doubles on 1 Dec |

## Appendix: data notes

1. **Argon cost was normalised.** The earlier chat summary quoted USD 0.0206 for Argon. That used the mean of its three shortest prompts (7,623 tokens). Normalised to the 9,327-token average the figure is USD 0.0240 (IDR 431), and USD 0.0480 after 1 Dec.
2. **Per-turn tokens differ by source.** The replay measured 9,327 input and 1,117 to 1,296 output (including thinking) tokens per turn for 3.5 Flash in Singapore. An earlier Cloud Monitoring read over mixed runs gave about 8,600 and 1,000. Cost here uses the replay.
3. **Two controls for the current model.** Run 1 gave 4.6 s median, run 2 gave 5.4 s. Both are reported; they differ by the amount of thinking the model did (748 and 925 tokens).
4. **T2 latencies are not used.** They came from nine parallel processes. In the first set the current model's median was 7 to 10 s, against 4.6 to 5.4 s in the replay and 6.5 s end to end in the sequential runs.
5. **Priority rows** are priced as Standard because that is what was served.
6. **Files.** `replay-results.jsonl` has one JSON object per call (`run`, `cfg`, question and repeat, `ms`, `status`, token counts, `traffic`, `finish`, `json_ok`, `answer_chars`, error text). `availability-probe.json` has the 78 probe results. `quality-harness-runs.txt` holds the saved harness output (warning lines with local paths removed). The capture run and the three error-capture runs were not saved. The throwaway scripts used for capture, replay and analysis were not committed.
