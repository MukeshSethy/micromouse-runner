# Lion Circuits ordering notes (rev 7.2)

1. Upload `micromouse-pcb-rev7.2-gerbers.zip` + `BOM.csv` + the pos file in
   Lion's turnkey flow. 4-layer, 1.6 mm, 1 oz outer / 0.5 oz inner is fine.
2. F1 (`MINISMDC350F/16-2`): Lion's part-page URL cannot encode the slashed
   MPN -- confirm the line in their BOM tool; approved equivalent:
   Bourns MF-MSMF350-2 (1812, 3.5 A hold / 7 A trip).
3. J10 (AMASS XT60-M): catalog page may show Out of Stock -- Lion sources
   turnkey and can usually procure. If not: leave unpopulated; it is a
   one-minute THT hand-fit (polarity + ONE PACK ONLY silk on board).
4. Assembly PDFs carry every refdes (the board silk carries the
   debug-critical subset).
