# Q3 E6 resource semantics

E6 extends the frozen reference communication model with executable resource calendars. See [the complete report](../../results/q3/E6_RESOURCE_REPORT.md) and [the artifact-bound gate](../../results/q3/e6/validation.json).

There are two relay UAVs and six energy components. UAV occupancy is `[preparation start, return + 300 s)`; component occupancy is `[takeoff, return + full recharge)`. Components must be fully charged at takeoff and may finish charging during UAV preparation. Relay preparation is 180 s and setup is 30 s. Charging uses the frozen two-stage charging model.

Each relay sortie flies from O01 to one fixed hover point and returns to O01. Multiple transport UAVs may share the relay at that point. This is an explicit modeling assumption requested for E6; no throughput or MAC-capacity guarantee follows. Communication module power is counted once over the union of active intervals. During intervening gaps the relay pays hover power without communication power. Flight/setup/return energy and reserve are recomputed after every merge or translation.

The only paths are direct T–G01 or single-relay T–R–G01. Relay–relay multihop is prohibited. Every inherited atomic outage task has exactly one assigned relay. E6 derives guards of 2 s on both sides, clipped to the actual transport flight, because full-flight independent auditing exposed inaccurate inherited gap boundaries. E52 inputs remain byte-for-byte unchanged. Guarded assigned sites are revalidated over the whole guarded interval.

Level A diagnoses the inherited pool with transport times fixed. Level B expands common sites and considers complete preparation/flight/service/turnaround/recharge occupancy. Its unavoidable-occupancy lower bounds are restricted to the retained candidate pool. A failed finite-column schedule is not a physical impossibility proof.

Level C preserves each plan's transport box assignment, route, visit order and type, translating whole sorties by nonnegative delays. The current search also preserves original transport UAV/battery IDs and their orders; unconstrained deadlines have a 20,000 s search cap. These additional restrictions must be disclosed when discussing optimality. Hard deadlines are constraints, then total delay and maximum delay are lexicographic timing objectives. Exact LP timing applies only to chosen relay groups/sites/orders; bounded outer grouping and ordering search is not globally optimal.

Joint makespan ends at the last transport/relay return. Resource-utilization denominators additionally include UAV turnaround and component recharge completion and are common to all resources within a plan.

Independent validation reconstructs transport and relay physics and resource calendars, audits all retained expanded edges, checks full transport flights at 0.5 s plus phase/task boundaries and observed LOS/sign changes refined to 0.1 s, and rechecks representative P01 at 0.25 s. Zero uncovered duration is a numerical audit result, not an analytic continuous-time theorem or ns-3 throughput guarantee.
