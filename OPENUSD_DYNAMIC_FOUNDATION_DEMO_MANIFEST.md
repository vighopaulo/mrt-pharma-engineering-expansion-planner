# OpenUSD Dynamic Foundation Demo Manifest

Non-authoritative presentation summary only.

- simulation time basis: `MINUTES` (MRT Pharma authoritative unit)
- USD time-code mapping: 1 USD TimeCode = 1 simulation second (`timeCodesPerSecond=1.0`)
- moving canonical object ID: `MRT-CARRIER-001`
- number of time samples: 3
- start position (m): (5.0, 15.0, 0.0)
- end position (m): (24.0, 6.0, 4.0)
- movement state sequence: ['MOVING', 'MOVING', 'COMPLETE']
- OpenUSD prim path: `/MRTwayCampus/Facility/MRT/MRT_CARRIER_001`
- underlying CarrierTrajectory status (real, scheduler-derived): `COMPLETE`
- engineering-authority statement: canonical identity/transform/dimensions/room-floor assignment remain exclusively owned by `canonical_spatial_authority.py`; nothing above changes them.
- visualization-authority statement: OpenUSD/`dynamic_scene_state_authority` represent presentation-only dynamic state; they are not engineering, routing, or economic authorities.
