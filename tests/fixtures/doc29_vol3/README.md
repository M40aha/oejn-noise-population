# Doc 29 Vol 3 reference tables (test fixtures)

The tables are exported unchanged, cell for cell, from the ECAC Doc 29 5th Ed. Vol 3 workbooks locked in `config/a5.yaml`:

| Fixture | Workbook | sha256 |
|---|---|---|
| A-1, A-2, A-6, A-7, A-9, A-10, A-11, A-12, B-1, B-2 | `ecac_doc29_5e_vol3_workbook_part1.xlsx` (noise model reference cases) | `59cdb927840168ffab446e7d29c62973346abd87b2e881326d3f7ad058beddc3` |
| C2 (jet coefficients), C8 (case list), C61 (procedural steps), D2 (performance results) | `ecac_doc29_5e_vol3_workbook_part2.xlsx` (performance reference cases) | `ddad40f9db322e111ef792499d18589f8d74b2d7e1e545c3fd97e9824f11285f` |

The sheet names are kept as file names (C2/C8/C61/D2 = Part 2 tables C-2, C-8, C-61, D-2). Values are stored as parquet (zstd);
there is no editing, rounding or unit conversion. Receptor coordinates are in nmi; the tests use x = nmi × 6076 ft, which
reproduces the B-2 geometry.
