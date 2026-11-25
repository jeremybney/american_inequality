# Voice + playbook for Jeremy's Substack Notes

Every batch is written against this file. It comes from 404 of Jeremy's notes
(Jun–Nov 2026) plus ~800 from Derek Thompson, Paul Krugman, Hannah Ritchie and
Steve Rattner. Engagement score = likes + 3x restacks + 2x replies.

## What the data says

| Finding | Evidence (Jeremy's notes, median score) |
|---|---|
| Native image/chart beats a link card by ~3x | image 34 · text-only 38 · link-card-to-own-post 10 · external link 9.5 |
| Put a number in it | with a number 29 · without 15 |
| Short wins | under 400 characters for almost every top note |
| Links in the body hurt | 9.5 with a link vs 21 without |
| Weekends are underused | Fri 29 · Sun 28 · Sat 24.5 vs Tue 14 |
| Best weekday windows | ~6:30–8 am, ~noon, ~5–7:30 pm ET (see data/timing_model.json, retuned weekly) |
| Replies come from questions | "Can you name them?" note: 40 replies on 17 likes |

Peers: Rattner is the template. 168 of 196 notes are a chart plus a one-to-two-sentence claim with
a specific number, and his restack ratio is the best of the group (Trump manufacturing jobs: 1,374 likes / 779
restacks). Krugman's biggest notes are personal and pointed. Ritchie's are a stat ladder ("2022: 1% / 2023: 7% /...").
Derek Thompson mostly shares post cards and those underperform his own averages.

## Formats that work (use a mix every week)

1. **Claim + chart** (Rattner): one sentence with the number, one sentence of meaning. Chart does the rest.
2. **Stat ladder**: years down the page, no commentary until the last line.
   (`1965: 20x / 1978: 30x / 2025: 281x` was a top-10 note.)
3. **Two numbers side by side**: "Black unemployment: 6.6%. White: 3.7%."
4. **Read past the headline**: an official stat everyone is repeating, and what it leaves out.
5. **Topical hook → evergreen chart**: today's news, one of Jeremy's own charts that explains it.
6. **Question**: weekend evenings. Ask something people can answer in a word.

## How Jeremy writes notes

- Short declaratives. Fragments are fine. "Richer zip code, better school."
- Opinionated but not shouty. A dry last line does more than an exclamation point.
- First person when it's his own work or view: "I think this is the key chart people are missing."
- Plain words: "kids," "rent," "make $30,000," not "households earning below the threshold."
- Numbers written the way people say them: "$210," "1 in 3," "14 times."
- Emoji rarely (🤷 🤦🏻), never more than one, never at the start.
- Tags people/outlets with @ sometimes; never hashtags.

## Hard rule: no repeated visuals within 6 months

Never use a chart or map that appeared in one of Jeremy's notes or articles in the last 6 months, and never
schedule the same visual twice within 6 months. Same data drawn as a different chart counts as a repeat if the
note makes the same point (e.g. a top-1% wealth line and a top-1% wealth ladder in the same month).
`python3 check_reuse.py --refresh` fingerprints every image and must report 0 problems before any batch or
rapid note ships.

## Data sources beyond FRED/ACS

`data/ext/` (fetched, not committed if licensed): Zillow ZHVI/ZORI (files.zillowstatic.com, public CSVs),
Opportunity Atlas county outcomes (opportunityinsights.org), Our World in Data grapher CSVs, BEA regional,
Fed SCF, FHFA HPI, LEHD. Todd Jones's list (github.com/toddrjones/datasets) for more. ProMap data only from CSVs
Jeremy downloads himself into Drive (it's a paid, login-only product; never scrape it or commit its data).
County maps: `charts.county_map(values={fips: value}, ...)`.

## Learned from Jeremy's own edits (Nov 2026, highest priority)

Jeremy rewrote nine notes in the first batch. What he changed:

- **No colons in sentences.** "Mississippi: 24.6%. DC: 24.5%." becomes a sentence. "Earlier this week: X" becomes
  "at the same time that X". The only exception is the stat ladder (`1989: 22.8%` on its own lines), which is his format.
- **Rarely "you".** Use Americans, households, families, people, workers, renters. ("How you define a problem" →
  "How a problem gets defined".)
- **Join the contrast into one flowing sentence** instead of staccato fragments. He replaced
  "Corporate profits ... record. / Earlier this week: workers' share ... record low. / Same economy." with
  "Corporate profits are now a bigger share of the economy than at any point on record at the same time that
  workers' share of those gains just hit a record low."
- **Cut the zinger, keep the stakes.** He deleted punchy kickers and political jabs ("Same economy.",
  "The bill keeps shifting to paychecks.", "Inflation hits hardest at the bottom...", "it compounds every month")
  and, where he added anything, it was what the number means for a real family ("the difference between a
  secure household and living in a shelter"; prices that "show up for families right around the holidays").
- **Let the stat stand alone when it's strong.** The corporate-tax note became just the two numbers.
- **Drop setup lines.** "Same median-priced new home. Same 20% down." was cut; he went straight to the numbers.
- **Ground claims in a source or document** ("When you look at old HUD documents...").

### Second round of edits (Nov 25, 2026, highest priority)

Jeremy flagged these as "written to sound too much like AI":

- **No "That's ..." / "It's ..." sentences that point back at the previous sentence.** "That's 53 years of a growing
  economy, and ..." and "That's the number families are actually living with." Put the fact in the sentence itself.
- **No ", and it hits hardest ..." clauses**, and no superlative add-ons tacked on with "and".
- **No "That part ..." or "The part that's most surprising ...".**
- **No short, dramatic fragments or aphorism kickers.** "That part isn't stinginess. Rent and groceries come first.",
  "When everyone moves somewhere cheap, it stops being cheap.", "A starter home.", "Same country, very different math."
- **What he added instead:** a personal, conversational line ("I've talked with a lot of people who could really use
  that extra $830/month", "tell your uncle about this 31% jump"). He does use "you" when it's conversational.
- He cut a political opener ("Democrats just won... Here's where I'd start.") and kept the data.

## What performs (Nov 16-25, score = likes + 3x restacks + 2x replies)

- Scheduled notes had a median score of 40, against 21 for his other notes.
- Winners were records on capital vs labor (profit share 137, top-1% wealth 100, labor share 82,
  corporate tax share 89), one-number housing stats (first-time buyer age 40, 91), electricity vs inflation (79)
  and Rattner reshares (72).
- Weakest were state maps (median 30), small big-stat cards on safety-net topics (SNAP, uninsured kids, under 20),
  Aziz reshares and gas prices.
- Midday posts did best (median 49), then evening (36), then morning (27). From Dec 7 the calendar runs **2 a day,
  midday and evening**.

## Reshares (others' charts + Jeremy's take)

- Run `python3 aiq_notes/peers.py` to rank recent image notes from Rattner, Derek Thompson, Aziz Sunderji,
  Our World in Data, Max Roser, Hannah Ritchie, Krugman by engagement per hour. Add others to `WATCH` freely.
- Pick charts on Jeremy's beat (inequality, housing, wages, health, education, place). 2-4 a week.
- Credit with a real Substack mention, written `@[Steve Rattner](1658881)` in the note text (the poster turns it
  into a mention, which also notifies them). Say it plainly ("in this chart from", "Great map from").
- Add Jeremy's view in one or two sentences tying it to his own data or that week's notes. Don't restate the chart.
- Use their image as-is (it carries their branding and source); never alter or crop out their credit.
- Twitter/X and LinkedIn aren't reachable from the content sessions yet; Substack notes are.

## Never (these read as AI)

- Em dashes. Use a period or a comma.
- "Here's the thing," "Let that sink in," "This is huge," "The reality is," "It's worth noting," "In today's economy."
- "It's not X, it's Y." / "Not just X, but Y."
- Three-item lists in every note. Rhetorical triplets as a habit.
- Colons in sentences at all (see Jeremy's edits above). Ladders are the only exception.
- Opening with a question unless the whole note is the question.
- Summarizing the chart's title back in the text word for word.
- "That's ..." / "It's ..." sentences pointing back at the previous sentence; ", and it hits hardest"; "That part".
- Wrap-up morals ("We have to do better." "The data is clear.").
- Hashtags, "🧵," "1/," or calls to subscribe.
- Links in the note body. If the source needs a link, it goes on the chart.

## Charts

- House style = The Big 5 of Inequality (aiq_notes/charts.py): Roboto, bold headline that states the conclusion,
  grey subtitle with the measure, Datawrapper blue `#1d81a2` for the baseline, red `#c71e1d` for the point,
  grey `#a8a8a8` for counterfactuals, one or two short annotations max.
- The headline is the takeaway ("The minimum wage is worth the least since 1949"), never a label ("Real minimum wage").
- Always a source line and "Chart: Jeremy Ney | americaninequality.substack.com".
- Big-stat card when one number carries it (aiq_notes/charts.big_stat).
- **Mostly net new.** Jeremy's readers have seen his archive. At least ~85% of each week's visuals are new:
  fresh data releases, news, and charts rebuilt from other people's published data (credited in the source line).
- Reuse one of Jeremy's own charts only if it came from a top performer (his best articles by likes/restacks:
  philanthropy, generational wealth, disability/Ivy League, real estate & schools, stealth tax, homeless data,
  blue-state billionaires; or a note that scored in his top 20) AND today's news makes it relevant again.
  At most 3 a week. Note text must match what that chart actually shows.

## Fact rules

- Every number in a note must appear on the chart or in a cited source. No rounding that changes meaning.
- Say "per new Census data" / "BLS" etc. in the note when the release itself is the hook.
- If a claim can't be verified from a primary or named secondary source, it doesn't go in.
