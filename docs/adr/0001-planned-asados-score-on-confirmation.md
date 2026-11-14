# Planned asados earn points only once a member confirms them after the date

Asados can be put on the calendar ahead of time, but plans change: people drop out, the meat changes, the whole thing gets cancelled. So an asado dated in the future is an **Asado Planificado**. It earns nothing until a member saves it on or after its date, which **confirms** it and works out its points at that moment. Status is decided by one rule on every save: if the asado was last saved on or after its date, it's Confirmado; otherwise it's Planificado. That rule applies to the web form, the seed script and any future import. Every point total, ranking and chart in the app, and the CSV export, counts confirmed asados only. (Issue #17, decided while designing the calendar in #5.)

## Considered Options

- **Points start automatically when the date arrives.** Simpler, with no action needed, but a cancelled or changed asado would start scoring as originally planned, and nobody would be prompted to correct it.
- **Only an admin can confirm.** Rejected because any member can already edit any asado. Accountability comes from the activity log, which records who confirmed.

## Consequences

- An asado whose date has passed but that nobody has saved since stays at zero points ("Por confirmar"). The home page lists these so they don't go unnoticed. Nothing is ever confirmed or deleted automatically.
- A planned asado still stores points, as an estimate shown as such. Confirming is a save, and every save re-freezes weights and points from the current `config.py`, so the stored points are only final once the asado is confirmed.
- "Today" is Chile's date (America/Santiago), not the server's UTC date.
