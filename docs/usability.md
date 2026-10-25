# Usability evaluation [D25]

**Status, 25 October 2026: the sessions have not been run.** This file holds the protocol to follow and the tables to fill in. The results tables below are empty on purpose: the numbers in them have to come from real participants, and a mean SUS score only means something if the team can say who answered. Fill the tables in after the sessions and write the number of participants next to every mean.

The tasks below were written for the app as it is now (including the optional features). A3 lists its own tasks; that PDF is not in this repository, so check these against it and keep A3's wording where they differ.

## Method

**Participants.** Aim for at least 5, mixing the two profiles named in A3: daily commuters and first-time visitors. Record only a label (P1, P2, …), the profile, and whether they have used a route planner before. Say that the session tests the program and not them.

**Set-up.** The real data (`python main.py`), a screen at least 1100 px wide, no hints. One facilitator speaks only to give the task and to prompt "what are you thinking?" when the participant goes quiet; a second person (or a screen recording the participant agreed to) times each task.

**Think-aloud.** Ask the participant to say out loud what they are looking for, what they expect to happen and what surprises them. Note the exact words for each surprise.

**Tasks.** A task counts as a success when the participant reaches the stated end state without help. Stop a task after 3 minutes and mark it as failed.

| # | Task (read out as written) | End state | Feature it exercises |
|---|---|---|---|
| T1 | "You are at Samaypur Badli and want to get to Noida City Centre as quickly as you can. Find the route." | A route is shown on the map and in the panel | Station search, automatic search |
| T2 | "You do not like changing trains. Show the route with as few changes as possible." | The Criterion box says *Fewest interchanges* and the panel shows the new route | Criterion, instant recompute |
| T3 | "Which stations do you pass through on the first part of this journey?" | The list of stations in between is open | Station list on each leg |
| T4 | "Clear everything. Without typing, choose Hauz Khas and then Rajiv Chowk using the map." | Both fields filled and a route shown | Map clicks, labels, zoom buttons |
| T5 | "There may be other ways to go. Compare them and pick the one you would take. Then save this trip so you can find it again." | A route other than Route 1 is on screen, or the participant says why Route 1 is best; the journey is in the Favourites menu | Alternatives, comparison, favourites |

Each task is timed, and the facilitator notes errors (wrong clicks, going back, asking for help).

**After the tasks: SUS.** The 10-item System Usability Scale (Brooke, 1996), each answered 1 (strongly disagree) to 5 (strongly agree):

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

**Scoring.** For odd items take the answer minus 1; for even items take 5 minus the answer. Add the ten values and multiply by 2.5, which gives 0–100. A score of about 68 is the usual average; with only a handful of participants, report the individual scores as well as the mean.

## Results

Not yet collected.

| Participant | Profile | T1 | T2 | T3 | T4 | T5 | SUS score | Main observations |
|---|---|---|---|---|---|---|---|---|
| P1 | | | | | | | | |

Mean SUS (n = ): 

## Findings and changes made

| Finding | Severity | Change | Decision ID |
|---|---|---|---|
| | | | |

## Issues the developers found themselves

These come from reviewing screenshots of the program while building it. They are **not** user findings and do not replace the sessions above.

| Issue | Change | Decision ID |
|---|---|---|
| With three routes, labels such as "Route 3 (Fewest stops)" did not fit the 380 px panel and were cut to "Rout…" | Tabs say only "Route N"; a caption under them says what the selected route is best at | D56 |
| In the dark theme the small map buttons cut "Fit" to "…" | The map buttons get no padding of their own in the style sheet | D55 |
