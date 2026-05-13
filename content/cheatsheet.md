# Interview Cheatsheet — Open Before Interview

---

## By Question Type

| Type | First sentence | Key trap | Core move |
|---|---|---|---|
| **Diagnose** | "Let me understand what exactly dropped — volume, depth, or quality? And was this sudden or gradual?" | Technical issue as default hypothesis | Behavior → mechanism (not symptom) → 2–3 checks |
| **Improve retention** | "Are we focusing on [riders/users/X]? And is there a supply-demand issue I should know about?" | New users → activation (wrong in transactional) | Segment → failure definition → lever |
| **Improve engagement** | "I'd focus on [segment] — who is least engaged and has the most to gain?" | Jump to features before defining failure | Core loop → failure point → solutions |
| **Improve conversion** | "I'll assume conversion = [order/signup] per session. New or existing users? Where's the drop-off?" | Availability problem vs decision problem | Funnel → bottleneck → decision context |
| **Favorite product** | "My favorite product is [X]. It succeeds because [2-line core value]." | "I love it because it's useful" | Why successful → problem → failure → fit-philosophy solution |
| **Feature design** | "Let me understand the ecosystem — how does this fit the existing surface and product philosophy?" | Feature in vacuum, ignores what already exists | Ecosystem fit → user need → tradeoffs |
| **0→1** | "Let me clarify the user segment and the specific pain before I think about the product." | Jumping to product before validating problem | Problem → segment → MVP → success metric |
| **Strategy/Tradeoff** | "Before I say yes or no, let me think through what this would mean for the core business." | Obvious yes/no without second-order effects | Benefit → cost → timing → recommendation |
| **Execution/Ops** | "What's the adoption situation right now — who is and isn't using this, and why?" | Treating it like a design question | Segments by adoption stage → barriers → rollout plan |

---

## Signal Reading (Diagnose Quick-Reference)

| Signal pattern | Most likely cause |
|---|---|
| Gradual + existing users most affected | Recommendation/algorithm degradation |
| Sudden + all users equally | Technical issue or external event |
| Volume stable, depth/quality drops | Consumption mix or content shift |
| DAU up, interactions down | Passive consumption shift (Reels pattern) |
| Requests up, conversion down | Signal pollution or decision friction |
| New users affected more | Activation/onboarding failure |
| Browse but don't act | Decision fatigue, not supply problem |

---

## Failure Definition — Fix In Real Time

**Weak:** "Too much information" / "users are less engaged" / "not enough drivers"

**Strong pattern:** [specific behavior] → [mechanism] → [impact on core value]

Examples:
- "Important conversations lose visibility because all communication competes equally for attention"
- "Post-match cancellations increase because drivers are geographically misallocated"
- "Users browse but don't order because too many options without decision signals"

---

## Prioritization Framework (any case)

1. Impact on core metric
2. Frequency — how often does this failure happen?
3. Severity — is it recoverable or trust-breaking?
4. Fits product philosophy?

Always: **name the winner + one tradeoff of your choice**.

---

## Senior Signal Moves

- **"Why now":** connect the problem to the product's evolution stage
- **One tradeoff:** "The risk is [X]. I'd monitor [guardrail metric] as a guardrail."
- **Existing features:** "I assume [feature] already exists — I'd focus on improving its effectiveness."
- **Philosophy fit:** "This fits [product]'s approach because it's [non-invasive / user-controlled / extends existing behavior]."
- **Hypothesis rejection:** "[Y] is less likely because it would cause sudden drop / affect all users equally."

---

## All Cases — Quick Reference

| Product | Type | Key insight (one line) |
|---|---|---|
| Instagram | Diagnose | Reels cannibalize Feed by design — passive format → fewer likes/comments by structure |
| Slack | Diagnose | Content type shifted to broadcast → reading loop replaced conversation loop |
| Uber | Diagnose | Post-match cancellations = matching quality problem, not supply volume |
| LinkedIn | Diagnose | Signal pollution: fake accounts + LinkedIn's own growth mechanics |
| Spotify | Diagnose | Gradual + existing users + skips↑ = recommendation degradation, not technical |
| Notion | Diagnose | DAU stable + creation dropped = creating became harder or less valuable |
| Telegram | Favorite product | Evolved from messaging to ecosystem → "why now" makes attention problem natural |
| Google Maps | Improve retention | Utility product: task success = retention. Incorrect data > poor discovery (irreversible) |
| Uber | Improve retention | Marketplace: supply-demand first. Transactional: activation ≠ retention |
| Wolt | Improve conversion | "Browse but don't order" = decision problem. Social proof beats AI |
| ChatGPT | Improve engagement | Casual users: friction at ask step + no return trigger. Habit > quality |

---

## Metrics Pattern

**Primary metric:** the core outcome you're trying to move
**Secondary metric:** supporting behavioral signal
**Guardrail:** what you don't want to break

Example (Telegram):
- Primary: % unread personal chats opened per session
- Secondary: response latency for personal conversations
- Guardrail: channel engagement (don't cannibalize community)

---

## English Quick Fixes

| Weak | Strong |
|---|---|
| "not enough drivers" | "poor supply distribution and weak matching quality" |
| "users feel less need to reply" | "content structure shifted toward informational content" |
| "too much information" | "important communication loses visibility among lower-priority content" |
| "users are less engaged" | "sessions per user dropped while skip rate increased" |
| "I would add a report button" | "I assume reporting exists — I'd focus on making correction faster and automated" |
