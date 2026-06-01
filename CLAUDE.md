# CLAUDE.md — Real Estate & Loans Content Channel

<!--
Note: user has to set the following environment variables:

BASE_CHANNEL = 'realestate-channel'
BASE_CODE_DIR = '$HOME/$BASE_CHANNEL'
BASE_CONTENT_DIR = '$HOME/Library/CloudStorage/GoogleDrive-do.khoa.d@gmail.com/My Drive/$BASE_CHANNEL'

code:
export BASE_CHANNEL 
export CONTENT_BASE="$HOME/Library/CloudStorage/GoogleDrive-do.khoa.d@gmail.com/My Drive/realestate-channel"

-->

## Channel identity

**Channel name:** Real Estate with AI
**Niche:** Real estate, mortgages, loans, property investing
**Audience:** Intermediate — they know what a mortgage is, they don't need hand-holding on basics, but they're not licensed professionals. Treat them like a smart friend who's done some research but hasn't pulled the trigger yet.
**Tone:** Conversational and relatable. You're the knowledgeable friend who happens to work in real estate finance — not a professor, not a hype guy. Explain things the way you'd explain them over coffee. Use contractions. Avoid jargon unless you immediately define it. Never say "it's important to note that."
**Format mix:** Educational explainers, news & commentary, case studies — roughly equal thirds.

---

## Content rules (always follow these)

**Voice**
- Write in second person ("you") not third person ("investors")
- Short sentences. One idea per sentence when possible.
- Analogies over abstractions — if you can make it concrete, do it
- Occasional rhetorical questions to keep the reader engaged
- Never start a sentence with "Furthermore," "Moreover," or "In conclusion"
- Never use the phrase "game-changer," "deep dive," or "unpack"

**Accuracy & disclaimers**
- All financial content must include a disclaimer variant: "This is not financial advice — always talk to a licensed professional before making decisions"
- Rates, regulations, and tax rules change — always flag when data may be time-sensitive with "[verify current rates]" inline
- When covering loan products, be specific about whether you're describing conventional, FHA, VA, USDA, or jumbo — never be vague
- Never make price predictions. Describe trends, conditions, and factors. Let the viewer draw their own conclusions.

**Content depth calibration**
- Assume the viewer has bought or sold one home OR researched it seriously but hasn't done a deal OR is thinking about investing in real estate
- Skip: what a mortgage is, what interest means, what equity is
- Don't skip: how points work, what DTI actually affects, the real difference between rate and APR, why pre-approval ≠ pre-qualification

---

## Pipeline A — content operation

This is the research, ideation, scripting, repurposing, and distribution layer.

### Stage 1: Research & ideation

**Primary tools:** Web search + YouTube MCP
**Goal:** Find video ideas ranked by search opportunity + audience fit

When asked to research topics or generate video ideas:
1. Search for trending real estate / mortgage questions (Reddit r/FirstTimeHomeBuyer, r/RealEstate, r/personalfinance are good signals)
2. Check YouTube search volume signals — titles with high view counts on small channels indicate strong search demand
3. Output ideas as a ranked list with: Title idea | Why it's timely | Search angle | Content type (explainer/news/case study)
4. Flag if a topic requires rate data that needs verification before filming

**Competitor channels to analyze for gaps (ask me to update this list):**
- Ken Pozek, https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://www.instagram.com/kenpozek/%3Fhl%3Den&ved=2ahUKEwi_uYPs0-SUAxV9IUQIHUWjItcQFnoECC4QAQ&usg=AOvVaw0i1Ee4t7kpGzT4q5mZw8yE
- Sarah Maslowski @movingtoGeorgia, https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://www.youtube.com/c/MovingtoGeorgia&ved=2ahUKEwiP68WI1OSUAxVBlu4BHVYjA2IQFnoECD8QAQ&usg=AOvVaw1e5GllQbcPQ8if7ZaKczSN

### Stage 2: Scripting

When writing a video script:
- Output format: Scene-by-scene with [HOOK], [INTRO], [SECTION_1]...[CTA] markers
- Hook must land in the first 15 seconds — start with a question, a surprising stat, or a relatable scenario. Never start with "Hey guys, welcome back to the channel."
- Each script should have a natural spoken length of 6–10 minutes for long-form, 45–60 seconds for Shorts
- Include [B-ROLL SUGGESTION: ...] cues inline where visual support would help
- Include [GRAPHIC: ...] cues for any numbers, comparisons, or processes that need visualization
- End every video with one clear CTA — subscribe, comment with a question, or link to a related video (never stack multiple CTAs)
- After writing, output a separate SHORT DESCRIPTION block (150 words max) and a TAGS block (15 tags, comma-separated)

**Script checklist before delivering:**
- [ ] Hook lands before 15 seconds
- [ ] Disclaimer included (financial advice variant)
- [ ] Time-sensitive data flagged with [verify current rates]
- [ ] No jargon left undefined
- [ ] CTA is singular and clear

### Stage 3: Repurposing

When given a YouTube video URL or transcript:
1. Extract the 3 strongest standalone points
2. Generate: LinkedIn post (250 words, professional but warm), X/Twitter thread (5–7 tweets), Short-form script (60 sec, hook-first), Newsletter section (400 words, more depth than the video)
3. Each repurposed piece should feel native to the platform — not like a copy-paste
4. LinkedIn: slightly more professional, lead with a data point or counterintuitive observation
5. X/Twitter: punchy, each tweet standalone, last tweet = CTA
6. Shorts: reframe the most surprising or counterintuitive moment from the video, not just a clip summary
7. Newsletter: go one level deeper than the video — add what you didn't have time to cover

### Stage 4: Distribution (via Postiz MCP)

When scheduling content:
- YouTube long-form: Tuesday or Thursday, 10am–12pm local time (best for finance audience)
- YouTube Shorts: daily if pipeline allows, any time
- LinkedIn: Tuesday–Thursday, 8–10am
- X/Twitter: any day, 8am or 6pm
- Never schedule more than 2 pieces of content on the same platform on the same day
- Always confirm the schedule before posting — never auto-publish without my approval

### Stage 5: Analytics & feedback loop

When pulling YouTube analytics:
1. Flag any video with >50% drop-off in the first 30 seconds — the hook needs work
2. Flag any video with unusually high retention (>60% average view duration) — identify what it did differently
3. For each weekly report: top 3 videos by views, top 3 by watch time, top search terms that brought new viewers
4. Feed retention winners back into scripting: "Videos with [characteristic] performed 40% better — incorporate this pattern"

---

## Working style preferences

**How I like to work:**
- I am a developer-level user but new to this specific toolchain — explain tool commands clearly the first time, but don't over-explain once I've confirmed I understand
- When you're about to run a command or make a change, tell me what you're about to do and why BEFORE doing it
- If something could go wrong or there's a decision with meaningful tradeoffs, stop and ask me before proceeding
- I prefer to review scripts before they go anywhere near publishing
- Show me the output at each stage so I can jump in and edit if needed
- Provide me a jumping in point information so that I can see how it is done at each step for the purpose of education me

**Corrections protocol:**
- If I correct your tone, phrasing, or approach → add a rule to this CLAUDE.md under the relevant section
- If I correct a factual error → note it as a known issue and double-check that category going forward
- If I tell you a script "doesn't sound like me" → ask me what specifically feels off before rewriting

**File organization:**
- Base Content Directory: BASE_CONTENT_DIRECTORY = '~/Library/CloudStorage/GoogleDrive-do.khoa.d@gmail.com/My Drive/realestate-channel'
- Set that as environment variable if not set
- Scripts go in: $BASE_CONTENT_DIRECTORY/scripts/[YYYY-MM-DD]-[slug].md
- Repurposed content goes in: $BASE_CONTENT_DIRECTORY/repurposed/[YYYY-MM-DD]-[slug]/
- Analytics reports go in: $BASE_CONTENT_DIRECTORY/analytics/[YYYY-MM]/
- Ideas backlog goes in: $BASE_CONTENT_DIRECTORY/ideas/backlog.md (append, never overwrite)

---

## Things I haven't figured out yet (update as I learn)

- Competitor channels to track: [TO BE ADDED]
- My posting cadence target: [TO BE DECIDED — start with 1 long-form/week + 3 Shorts]
- Channel monetization strategy beyond AdSense: [TBD — affiliate links? lead gen?]
- Whether I'll appear on camera or use AI avatar: [TBD — Pipeline B decision]

---

## Known corrections (add to this as we work together)

_None yet — this will grow as we catch things._

---
_Last updated: 05/31/2026 — update this whenever you make changes_
