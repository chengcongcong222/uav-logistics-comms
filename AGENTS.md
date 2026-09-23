# Project Rules

1. data/raw is immutable.
2. All derived files must go to data/processed, data/cache, export, or results.
3. The contest communication model is authoritative for optimization.
4. ns-3 is a validation layer and must not redefine the contest model.
5. Do not introduce RL, Lyapunov optimization, artificial potential fields, or new MAC protocols.
6. Relay-to-relay multihop is prohibited.
7. Do not use AODV/OLSR to replace the relay schedule.
8. Q1-Q4 implementation must not start during E0.
9. All experiments must write machine-readable configuration and results.
10. All random experiments must use explicit seeds.
11. Do not silently change ns-3 version.
12. Do not modify source data.
13. Keep model assumptions, code assumptions, and experimental assumptions distinguishable.
14. A failed gate must be reported rather than bypassed by changing the scientific model.
