# Demo script (12 scenarios)

Start with `python main.py`. Each scenario lists what to do, what the audience should see, and the requirement it shows. Allow about 10 minutes for scenarios 1–6 and 6 more for 7–12.

> Scenarios 1–6: the team should still check them against the six listed in A3 §8 (that PDF is not in this repository) and adjust the wording to match.
> Scenarios 7–12 show the optional features. Every number in them was read from the running program on 25 October 2026 with the real data, and the behaviour is covered by the tests named in `decisions.md` [D47]–[D58].

## 1. Plain route with one change (FR3, FR6, FR7, FR10)
1. In **From**, type `samay`, press ↓ and Enter → "Samaypur Badli".
2. In **To**, type `noida city`, press ↓ and Enter → "Noida City Centre".
3. **See:** the route starts automatically. The panel shows *Yellow Line → change at Rajiv Chowk → Blue Line* with minutes per leg and the total. The map dims the network and draws the two legs (the second with a white dashed centre) and fits to the route.

## 2. Typo tolerance and ambiguity (FR3, ER2, ER3, [D16])
1. Press **Esc** to reset.
2. Type `hauz kas` in From → the list starts with "Did you mean …?" and offers Hauz Khas.
3. Type `raj` → Rajiv Chowk, Rajouri Garden … each with its lines listed; nothing is chosen until you pick.
4. Type `xyz` → "No station matches 'xyz'." under the field.

## 3. Branch change and walkway (FR8, [D17])
1. From **Noida Electronic City** to **Vaishali** → one Blue → Blue change at **Yamuna Bank**.
2. From **Dhaula Kuan** to **Lajpat Nagar** → a **Walk** leg to Durgabai Deshmukh South Campus (dotted on the map) and then the Pink Line, with **0 interchanges**.

## 4. Map interaction (FR4, FR9, FR11, FR12, [D21])
1. Reset. Scroll to zoom about the cursor; labels appear as you zoom in (interchanges → terminals → all).
2. Drag to pan; press `0` to fit; `+` / `-` to zoom.
3. Hover over a cluster → the tooltip lists every nearby station, nearest first, with its lines.
4. Click a station (From), click another (To) → the route appears. Click a third → it becomes the new From.

## 5. Criteria and the Pink ring (FR16, [D14])
1. From **Deepali Chowk** to **Kalkaji Mandir** (Fastest), note the route and time.
2. Change **Criterion** to *Fewest interchanges* and press **Find route** → compare.
3. From **Sarojini Nagar** to **Ashram** → the Pink leg says "towards Dilli Haat - INA" (a loop has no terminus). Press **Swap** (Alt+W) → it now says "towards Lajpat Nagar".

## 6. Errors never crash the app (FR14, ER5, ER7, ER8)
1. Choose the same station in both fields → "Choose two different stations." and Find is disabled (hover it for the reason).
2. Start the app on a broken dataset: `python main.py tests/fixtures/broken/time_too_small` (folder with a missing file) → the start-up dialog lists the problem and the data folder; **Quit** exits with code 1. To show the multi-problem dialog, copy `tests/fixtures/toy_metro` to a folder and paste the files from `tests/fixtures/broken/multi_defect` over it.
3. Keyboard only: Tab through From → To → Criterion → Find → Swap → Reset → route list → map, then Esc to reset.

## 7. Stations along each leg (FR7, [D53])
1. Reset. Choose **Rajiv Chowk** → **Hauz Khas**. The panel shows one Yellow leg: *22 min · 0 interchanges · 9 stops*.
2. Click **▶ 8 stations in between** (or Tab to the row and press Enter). The list opens with Patel Chowk, Central Secretariat, Udyog Bhawan, Lok Kalyan Marg, Jorbagh, Dilli Haat - INA, AIIMS, Green Park, and the arrow turns to ▼. Click it again to close.
3. On the command line the same list is `python tools/route_cli.py data "Rajiv Chowk" "Hauz Khas" --stations`.

## 8. The route on the map: dots and change badges (FR10, FR11, [D52])
1. Choose **Samaypur Badli** → **Noida City Centre**: *79 min · 1 interchange · 30 stops*, Yellow then Blue.
2. **See:** the rest of the network is dimmed, but every station on the route has a white dot and keeps its name. Rajiv Chowk has a heavy ring and a boxed label **⇄ Change at Rajiv Chowk**.
3. Click a leg in the panel: the map zooms to that leg. Click **▶ 14 stations in between** to see which dots they are.

## 9. Alternatives and comparison (FR17, [D47], [D56])
1. Choose **Dwarka Sector 21** → **Botanical Garden**. Three tabs appear above the summary.
   - **Route 1:** 71 min · 2 interchanges · 19 stops (Airport Express, Yellow, Blue). *Best at: Fastest, Fewest stops.*
   - **Route 2:** 98 min · **0** interchanges · 41 stops (Blue only). *Best at: Fewest interchanges.* Slower, but no change of train.
   - **Route 3:** 71 min · 2 interchanges · 19 stops, but through the Pink Line instead of the Yellow. *Best at: Fewest stops.*
2. Click the tabs: the panel and the map follow.
3. Press **Compare routes**. The table puts the three side by side, the best value in each row in bold. Routes 1 and 3 look the same in minutes, interchanges and stops, and the **Lines used** row shows how they differ. Press **Choose this route** under Route 2.
4. Change **Criterion** to *Fewest interchanges*: the search runs again by itself ([D49]) and Route 2 becomes the first tab.

## 10. Favourites and export (Could tier, [D48], [D57])
1. With a route on screen press **☆ Add to favourites**; it becomes **★ Saved - click to remove**.
2. Press **Reset (Esc)**, open **Favourites** and choose the saved route: both fields, the Criterion box and the route come back.
3. Press **Export**. *Copy to clipboard* and paste into any editor. *Save as Markdown…* writes a `.md` file with a heading, the summary and every station of every leg.
4. If a file cannot be written (a full disk, a folder that went read-only), a red message appears in the banner and the route stays on screen. The tests simulate this; the operating system's own save dialog may stop you before it can happen, so it is not worth trying live.
5. Close and reopen the program: the favourite is still there.

## 11. Dark theme, map buttons and crowded labels (Could tier, [D50], [D51], [D55])
1. Press the **◐** button on the map: the whole window turns dark and a route is drawn with a soft glow. Press it again for light. Close and reopen: the last choice is remembered.
2. Use **+**, **−** and **Fit** to zoom without the keyboard or wheel.
3. Zoom in on the centre of the network (Rajiv Chowk, Patel Chowk, Central Secretariat). Names that would print over each other are left out and appear one by one as you zoom further.

## 12. Animation and the station card (Could tier, [D54], [D58])
1. With a route on screen press **▶** on the map (or Space): a red marker travels along the route, about a quarter of a second per station. The button becomes **❚❚**; press it to pause.
2. Press **»** (or `.`) to jump to the next station, and `,` to go back one. After the end, play starts again from the beginning.
3. Right-click a station: **Station details…**, **Set as From**, **Set as To**. The card shows its code, aliases, a coloured tag per line (with the line's name), whether it is an interchange or a terminal, its neighbours and its position.
4. From the keyboard, press **Ctrl+I** to open the card of the To station (or the From station if there is no To yet).
