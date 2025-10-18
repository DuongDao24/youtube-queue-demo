# YouTube Queue — Core Backend (v01.6.2)

Author: Duong – XDigital  
Updated: 2025-10-18

This backend is located in /core but is configured to use **templates/** and **static/** at the repo ROOT,
so your UI from v01.6.1 remains intact.

Key points:
- Persistent JSON storage (/core/data)
- CSV activity logging
- Queue<=50, History<=20 (auto-trim)
- Auto-clear is **disabled**
- Start command: python core/app.py
