/-!
# Bresenham's line

The integer algorithm of `exactfig.pixel.pxmath.line`, step for step: the error term starts at dx + dy (dy ≤ 0), and at
each point a horizontal step is taken when 2·err ≥ dy and a vertical one when 2·err ≤ dx, both tested against the same
2·err. Every annotation, iso-line and chord in exactfig is drawn with it.

Proved here by Lean's kernel for every pair of endpoints with coordinates in 0..4 (625 lines): the line starts and ends
at its endpoints, consecutive points are 8-neighbours (it has no gaps and never repeats a point), and it has exactly
max(|Δx|, |Δy|) + 1 points (the fewest possible for an 8-connected path). `main` prints the lines for every pair of
endpoints in −3..3 (2401 lines) as JSON, and `tests/test_lean.py` checks that exactfig draws exactly the same points.

Plain Lean 4 (core only, no Mathlib). Run with `lean --run lean/Line.lean > lean/data/lines.json`.
-/

/-- The loop of the algorithm. `fuel` bounds the number of points (it is never the reason the loop stops for a fuel of
|Δx| + |Δy| + 1; the theorems below show the line reaches its end). -/
def lineGo (x1 y1 dx dy sx sy : Int) : Nat → Int → Int → Int → List (Int × Int)
  | 0, _, _, _ => []
  | fuel + 1, x, y, err =>
    if x = x1 ∧ y = y1 then [(x, y)] else
      let e2 := 2 * err
      let err1 := if e2 ≥ dy then err + dy else err
      let x' := if e2 ≥ dy then x + sx else x
      let err2 := if e2 ≤ dx then err1 + dx else err1
      let y' := if e2 ≤ dx then y + sy else y
      (x, y) :: lineGo x1 y1 dx dy sx sy fuel x' y' err2

/-- The points of the line from (x0, y0) to (x1, y1), both ends included. -/
def line (x0 y0 x1 y1 : Int) : List (Int × Int) :=
  let dx : Int := (x1 - x0).natAbs
  let dy : Int := -((y1 - y0).natAbs : Int)
  let sx : Int := if x0 < x1 then 1 else -1
  let sy : Int := if y0 < y1 then 1 else -1
  lineGo x1 y1 dx dy sx sy ((x1 - x0).natAbs + (y1 - y0).natAbs + 1) x0 y0 (dx + dy)

def adjacent (p q : Int × Int) : Bool :=
  p ≠ q && (p.1 - q.1).natAbs ≤ 1 && (p.2 - q.2).natAbs ≤ 1

def chained : List (Int × Int) → Bool
  | p :: q :: rest => adjacent p q && chained (q :: rest)
  | _ => true

def coords (lo hi : Int) : List Int := (List.range (hi - lo + 1).toNat).map fun (k : Nat) => lo + Int.ofNat k

/-- Every pair of endpoints with coordinates in lo..hi. -/
def pairs (lo hi : Int) : List (Int × Int × Int × Int) :=
  (coords lo hi).flatMap fun a => (coords lo hi).flatMap fun b =>
    (coords lo hi).flatMap fun c => (coords lo hi).map fun d => (a, b, c, d)

def good (q : Int × Int × Int × Int) : Bool :=
  let (a, b, c, d) := q
  let l := line a b c d
  l.head? == some (a, b) && l.getLast? == some (c, d) && chained l &&
    l.length == max (c - a).natAbs (d - b).natAbs + 1

/-- Endpoints, 8-connectedness and the minimal length, for all 625 lines with coordinates in 0..4. -/
theorem bresenham_correct_on_box : (pairs 0 4).all good = true := by decide +kernel

def jsonPoint (p : Int × Int) : String := s!"[{p.1},{p.2}]"

def main : IO Unit := do
  let rows := (pairs (-3) 3).map fun (a, b, c, d) =>
    s!"[[{a},{b},{c},{d}],[" ++ ",".intercalate ((line a b c d).map jsonPoint) ++ "]]"
  IO.println ("{\"source\": \"lean/Line.lean\", \"theorem\": \"bresenham_correct_on_box\", \"lines\": [" ++
    ",".intercalate rows ++ "]}")
