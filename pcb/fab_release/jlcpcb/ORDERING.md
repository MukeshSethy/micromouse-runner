# JLCPCB ordering notes (rev 7.2)

1. Upload `micromouse-pcb-rev7.2-jlcpcb.zip` (gerbers + Excellon drill, flat).
   Board: 4-layer, 100 x 120 mm, 1.6 mm; the default JLC 4-layer stackup is
   fine (no controlled impedance required -- USB is full-speed).
2. For SMT assembly add `bom_jlcpcb.csv` + `cpl_jlcpcb.csv`. LCSC part
   numbers are intentionally blank: use JLC's "match by MPN" in the BOM
   review step (all MPNs are major-distributor parts; some may be
   Global-Sourcing lines with longer lead).
3. CHECK ROTATIONS in JLC's assembly preview -- KiCad and JLC rotation
   conventions differ per package; fix any flipped polarized part
   (U1/U2/U3/U6/U7/U8, D29, Q-parts) in their editor before confirming.
4. THT parts (J1/J5/J6/J7-J10, SW1-SW6, sensors, motors' connectors) are NOT
   in JLC economic SMT -- order them loose and hand-fit, or use JLC Standard
   PCBA. J10 (XT60) is optional: fit only if your pack lead is XT60.
5. The exact robu motor plugs straight into J5/J6 (JST ZH) -- meter-check
   the cable's VCC/GND (positions 2/5) once before first plug-in.
6. The CPL uses KiCad's drill-file origin (negative Y). JLC's assembly
   preview auto-aligns the centroid file to the board -- verify visually in
   the review step; if parts render off-board, use their "adjust origin"
   button once.
