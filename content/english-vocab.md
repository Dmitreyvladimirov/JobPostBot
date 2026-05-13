# English PM Vocabulary — Precision Wording

Goal: not fluency (you have it), but precision. The right word in the right slot.

---

## Verbs — Problem Analysis

| Verb | Meaning in PM context | Example |
|---|---|---|
| **surface** | bring something to visibility | "This surfaces a prioritization problem." |
| **attribute** | connect a metric to a cause | "We can attribute the drop to recommendation degradation." |
| **isolate** | separate one variable to study it | "To isolate the cause, I'd look at new vs returning users separately." |
| **diagnose** | identify the root cause | "Before jumping to solutions, let me diagnose what's actually broken." |
| **validate** | confirm a hypothesis with data | "I'd validate this with skip rate by surface." |
| **hypothesize** | form a structured guess | "My hypothesis is that friction increased at the creation step." |
| **articulate** | express precisely | "Let me articulate the failure more specifically." |
| **trace** | follow a cause backward | "We can trace this decline back to a content mix shift." |
| **narrow down** | reduce options | "I'd narrow this down to two most likely mechanisms." |
| **tease apart** | separate two mixed-up things | "We need to tease apart the volume drop from the quality drop." |

---

## Verbs — Solutions & Prioritization

| Verb | Meaning in PM context | Example |
|---|---|---|
| **address** | tackle a specific problem | "This directly addresses the prioritization friction." |
| **mitigate** | reduce a risk without eliminating it | "A confidence score mitigates false positive risk." |
| **de-risk** | reduce the chance of failure proactively | "A/B test before rollout de-risks the change." |
| **scope** | define the boundaries of a solution | "I'd scope this to existing users only in phase 1." |
| **anchor** | tie something to a reference point | "Every solution should anchor to the core value." |
| **compound** | when effects build on each other | "Good recommendations compound — each session trains the next." |
| **unlock** | enable something that was blocked | "Reducing friction unlocks creation behavior." |
| **nudge** | a light behavioral push | "A weekly digest nudges users back without being aggressive." |
| **extend** | build on existing behavior/feature | "This extends the existing folder logic — no new paradigm." |
| **preserve** | keep something intact | "The solution preserves chronological structure." |

---

## Verbs — Measurement

| Verb | Meaning in PM context | Example |
|---|---|---|
| **track** | monitor over time | "We'd track response latency as a secondary metric." |
| **benchmark** | compare against a baseline | "Benchmark against pre-rollout cohort." |
| **correlate** | observe that two things move together | "Skip rate correlates with recommendation quality." |
| **segment** | split users by meaningful attribute | "I'd segment by new vs returning users." |
| **proxy** | use as indirect signal | "Time to order proxies for friction quality." |
| **control for** | hold a variable constant to isolate another | "Control for seasonality before attributing to the feature." |
| **taper off** | decline gradually | "Engagement tends to taper off after week 2." |

---

## Product Mechanics — Key Concepts

| Term | Meaning | Example |
|---|---|---|
| **participation threshold** | Minimum participation level below which a feature stops working | "The digest has a participation threshold — below 60%, it loses value and people stop." |
| **negative flywheel** | Self-reinforcing cycle of decline. Each step makes the next worse. | "Low participation → useless digest → more dropoff → even lower participation." |
| **lapsed users** | Users who tried and stopped. Not new, not active — specifically those who fell off. | "Lapsed users have lower barrier than never-tried — they already have intent." |
| **lever** | An independent mechanism you can pull to change behavior. Think in levers, not features. | "Two levers here: friction (reminders) and motivation (value visibility)." |
| **flywheel** | Self-reinforcing positive loop. Each step makes the next stronger. | "More drivers → shorter wait → more riders → more drivers." |
| **participation rate** | % of eligible users who actually did the thing in a given period. | "Team participation rate dropped from 80% to 20% by week 3." |

---

## Nouns — Core PM Vocabulary

| Noun | Usage |
|---|---|
| **friction** | Any unnecessary effort in a user journey. "Friction at the creation step." |
| **leverage** | A place where a small change has large impact. "That's a high-leverage intervention." |
| **bottleneck** | The step where flow is most restricted. "The bottleneck is at the search → selection step." |
| **signal** | A data point that tells you something. "Post-match cancellations are a signal of matching quality issues." |
| **threshold** | A boundary or minimum level. "Below a certain quality threshold, users disengage." |
| **baseline** | The starting point for comparison. "Compare against pre-launch baseline." |
| **cohort** | A group of users defined by when/how they joined. "D7 retention by signup cohort." |
| **flywheel** | Self-reinforcing loop. "Data → better recommendations → more engagement → more data." |
| **tradeoff** | What you give up when you gain something. "The tradeoff: engagement up, discovery down." |
| **surface** | A specific UI location or product area. "Skip rate by surface (Feed vs Reels vs Search)." |
| **loop** | A recurring behavior pattern. "The core loop: open → ask → answer → return." |
| **failure point** | Where the value chain breaks. "The failure point is at the 'evaluate answer' step." |
| **backlog** | Unread messages / unprocessed items. "Unread backlog creates anxiety and churn." |
| **guardrail** | A metric you monitor to make sure you're not breaking something. "Session depth as a guardrail." |
| **vector** | Direction of impact or effort. "Supply-side and demand-side are two different vectors." |

---

## Adjectives — Precision Modifiers

| Adjective | Usage |
|---|---|
| **actionable** | Can be acted on immediately. "I'd focus on actionable signals first." |
| **measurable** | Can be quantified. "Failure needs to be measurable, not just felt." |
| **incremental** | Adding to existing, small step. "An incremental improvement to the existing folder logic." |
| **compound** | Effects that multiply over time. "Compound retention gains from habit formation." |
| **granular** | Highly detailed, specific. "I'd want granular data by surface and segment." |
| **reversible** | Can be undone. "Prefer reversible changes in early rollout." |
| **invasive** | Disrupts existing behavior significantly. "Algorithmic ranking feels invasive for Telegram users." |
| **non-invasive** | Light touch, minimal disruption. "A filter is non-invasive — users opt in." |
| **downstream** | Effect that happens later in the chain. "Notification overload has downstream effects on reply rate." |
| **upstream** | Effect that happens earlier in the chain. "Fix it upstream at the creation step, not downstream at the engagement step." |

---

## Interview Phrases — Structuring Your Answer

### Opening
- "Let me clarify one thing before I structure my answer."
- "I'll assume we're optimizing for [segment] — does that sound right?"
- "Before jumping to solutions, let me make sure I understand what's broken."

### Hypothesis framing
- "My hypothesis is that [X] because it explains [all three signals]."
- "[Y] is less likely because it would cause [sudden drop / equal impact across segments]."
- "The most likely mechanism is [X], not [Y], because..."

### Problem definition
- "The specific failure is: [measurable thing] because [mechanism]."
- "What's actually breaking here is not [symptom] but [root cause]."
- "Users [do X], which creates [failure Y], which maps to [metric Z]."

### Prioritization
- "I'd prioritize this over [alternative] because it directly attacks the root cause."
- "This solution fits the product philosophy — it's non-invasive and user-controlled."
- "I'd start with this because it's reversible and high signal."

### Tradeoffs
- "The risk here is [X] — we'd want to monitor [guardrail metric] closely."
- "There's a tradeoff: [benefit] at the cost of [something else]."
- "This could reduce [desirable thing] as a side effect — worth testing in a limited rollout first."

### Metrics
- "Primary metric: [outcome]. Guardrail: [what I don't want to break]."
- "I'd measure success by [behavioral change], not just [vanity metric]."

---

## Collocations — Things That Go Together

| Pattern | Examples |
|---|---|
| **directly [verb] the core value** | directly affects / directly attacks / directly tied to the core value |
| **fits the product philosophy** | "This fits Telegram's philosophy — minimalistic, user-controlled." |
| **natural extension of** | "A catch-up digest is a natural extension of the existing folder logic." |
| **at the [step] stage** | "The failure is at the creation stage, not the consumption stage." |
| **across [surfaces/segments]** | "I'd check engagement across surfaces and across user segments." |
| **by design** | "Reels generate fewer comments by design — it's a passive consumption format." |
| **in the wild** | "How does this behave in the wild, outside controlled testing?" |
| **drives [metric]** | "This drives D7 retention by forming a daily habit." |
| **root cause** | "We haven't identified the root cause — we've only named the symptom." |
| **zero-sum** | "Channel growth and personal chat engagement might be zero-sum." |
