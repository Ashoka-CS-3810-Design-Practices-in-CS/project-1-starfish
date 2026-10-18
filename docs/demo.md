# Demo script (6 scenarios)

Start with `python main.py`. Each scenario lists what to do, what the audience should see, and the requirement it shows. Allow about 10 minutes in total.

> The team should check these scenarios against the six listed in A3 §8 and adjust the wording to match.

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
