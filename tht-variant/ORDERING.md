# THT variant — Lion Circuits ordering flow (self-assembly)

This variant is ordered as **bare PCB fab + a parts kit** — no assembly
service (that's the point: you solder it).

## When the layout is done (see DESIGN.md §8)
1. **Bare board**: upload the THT variant's gerber zip to Lion as a
   fab-only order (no assembly). 2-layer if the layout session confirms it
   (cheaper), else 4-layer, 1.6 mm, HASL is fine for hand-soldering.
2. **Parts kit**: upload `BOM-THT.csv`'s MPN column as a Lion parts order
   (they sell components without assembly), or buy the jellybeans anywhere.
   - `CD74HC4067E` (or 2× `CD74HC4051E`): catalog pages 404/OOS — put them
     in the BOM tool anyway; Lion procures turnkey. Any distributor carries
     them.
   - Inductor exact value (`RLB0914-330KL`) and schottky (`1N5822`):
     confirm the slugs in Lion's BOM tool (family verified In Stock).
3. **From robu.in** (customer-supplied modules that plug into sockets):
   - ESP32-S3-DevKitC-1-N8R2 (also In Stock at Lion — either source)
   - TB6612FNG breakout (~₹150)
   - GY-BNO055 breakout (~₹700)
   - The GA12-N20 motors plug into J5/J6 exactly as on the SMD board.

## Hand-assembly order (lowest → tallest, standard THT practice)
resistors → diodes → DIP sockets (use sockets for the muxes!) → TO-92s →
ceramics → LEDs → tact/slide switches → electrolytics → TO-220s →
inductors → PPTC → connectors (XH/ZH/XT60/headers) → female sockets for
the three modules. Then the rev-7.2 bring-up order from `fw/README.md`
(SW5 first, meter the rails, flash through the DevKit's USB-C, sensors,
then SW6 wheels-up).

## Cost picture (why this variant exists)
- SMD board: fab + turnkey assembly + parts = Lion quote dominated by
  assembly setup.
- THT board: fab-only + loose parts + 3 modules + an evening of soldering.
