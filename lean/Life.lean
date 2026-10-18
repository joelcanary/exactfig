/-!
# Life-like cellular automata on a torus

The update of `exactfig.forge.motion.life_step` with `wrap = true`: a dead cell is born when its number of live
neighbours is in `birth`; a live cell survives when it is in `survive`. A board is a list of rows of `Bool`, row 0 at the
top, and the eight neighbours wrap around the edges.

The theorems are checked by Lean's kernel (`decide +kernel`): nothing here is tested, it is proved for these boards.
`main` prints the 33 frames of the glider theorem as JSON; that output is `gallery/data/lean-glider.json`, which the
recipe `examples/recipes/lean-glider.json` animates, and `tests/test_lean.py` checks that exactfig's own Life computes
exactly the same frames.

Plain Lean 4 (core only, no Mathlib). Run with `lean --run lean/Life.lean > gallery/data/lean-glider.json`.
-/

abbrev Board := List (List Bool)

/-- The cell at column `x`, row `y` (dead outside the board). -/
def cell (b : Board) (x y : Nat) : Bool := (b.getD y []).getD x false

/-- Live neighbours of (x, y) on a w × h torus. Offsets are written as d - 1 for d ∈ {0, 1, 2}. -/
def neighbours (w h : Nat) (b : Board) (x y : Nat) : Nat :=
  [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)].foldl
    (fun n (d : Nat × Nat) => if cell b ((x + w + d.1 - 1) % w) ((y + h + d.2 - 1) % h) then n + 1 else n) 0

/-- One generation of the rule B`birth`/S`survive`. -/
def step (birth survive : List Nat) (b : Board) : Board :=
  let h := b.length
  let w := (b.headD []).length
  (List.range h).map fun y => (List.range w).map fun x =>
    let n := neighbours w h b x y
    if cell b x y then survive.contains n else birth.contains n

/-- `n` applications of `f`. -/
def iterate {α : Type} (f : α → α) : Nat → α → α
  | 0, a => a
  | n + 1, a => iterate f n (f a)

/-- Conway's rule, B3/S23. -/
def conway : Board → Board := step [3] [2, 3]

/-- An empty w × h board with the given live cells, shifted by (dx, dy) around the torus. -/
def board (w h : Nat) (cells : List (Nat × Nat)) (dx dy : Nat) : Board :=
  (List.range h).map fun y => (List.range w).map fun x =>
    cells.any fun c => (c.1 + dx) % w == x && (c.2 + dy) % h == y

/-- The glider, moving towards the bottom right. -/
def glider : List (Nat × Nat) := [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]

/-- Four generations move the glider one cell right and one cell down. -/
theorem glider_moves : iterate conway 4 (board 8 8 glider 2 2) = board 8 8 glider 3 3 := by decide +kernel

/-- On an 8 × 8 torus the glider is back where it started after 32 generations. -/
theorem glider_returns : iterate conway 32 (board 8 8 glider 2 2) = board 8 8 glider 2 2 := by decide +kernel

/-- The blinker has period 2. -/
theorem blinker_period_two :
    iterate conway 2 (board 5 5 [(1, 2), (2, 2), (3, 2)] 0 0) = board 5 5 [(1, 2), (2, 2), (3, 2)] 0 0 := by
  decide +kernel

/-- The blinker is not a still life (so the period is exactly 2, not 1). -/
theorem blinker_moves :
    conway (board 5 5 [(1, 2), (2, 2), (3, 2)] 0 0) ≠ board 5 5 [(1, 2), (2, 2), (3, 2)] 0 0 := by
  decide +kernel

def jsonRow (r : List Bool) : String := "[" ++ ",".intercalate (r.map fun c => if c then "1" else "0") ++ "]"

def jsonBoard (b : Board) : String := "[" ++ ",".intercalate (b.map jsonRow) ++ "]"

def main : IO Unit := do
  let frames := (List.range 33).map fun k => iterate conway k (board 8 8 glider 2 2)
  IO.println ("{\"source\": \"lean/Life.lean\", \"rule\": \"B3/S23\", " ++
    "\"theorems\": \"glider_moves glider_returns blinker_period_two blinker_moves\", " ++
    "\"frames\": [" ++ ",".intercalate (frames.map jsonBoard) ++ "]}")
