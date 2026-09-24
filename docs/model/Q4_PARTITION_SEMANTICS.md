# Q4 fixed-execution independent partitions

Authority: Q3E7_001, Gamma_C = 0 dB. This is the time-priority formal E7
representative. E8 is a sensitivity study; its unresolved Gamma 6 case does not
gate Q4. No Q3 reoptimization is performed.

## Inherited invariants

Box-to-sortie assignment, visit sequence, types, physical flight geometry,
preparation/departure/return/service/charging times and communication assignments
stay fixed. All services in a transport sortie belong to one group. Under the
frozen whole-relay-sortie task interpretation, all transport sorties supported
by that relay sortie also belong to one group. Relays are neither duplicated
nor split across groups. These dependencies, not shared original physical IDs,
define the unsplittable connected components.

The source has five components. K=2 and K=3 partitions are exact unlabeled
partitions of these components, giving 15 and 25 cases. All 15 services appear
once; each group is nonempty. Original source resource IDs remain in provenance
columns, while each group receives a dedicated independent pool. Reassigning
IDs is necessary to measure minimum independent resource quantities and does
not reschedule any task.

## Exact resources

Transport UAVs occupy [preparation, return); typed batteries occupy [takeoff,
full-charge-ready). Relay UAVs occupy [preparation, turnaround-complete); relay
energy components occupy [takeoff, full-charge-ready). A 1e-6-second endpoint
tolerance matches the frozen scheduling audit. For each group and resource
class, interval-graph maximum concurrency is a lower bound and greedy coloring
attains it. The output contains both clique certificates and explicit calendars.

Resource requirements sum group minima, while inventory shortages are computed
componentwise by type. Resources cannot move across groups. Reported Q4
configurations requiring additional inventory are valid gap-analysis outputs,
but cannot be called executable with current inventory. Charging resource
capacity itself follows the original unlimited-parallel-charging assumption.

Partition redundancy is the difference between the summed group minima and the
unpartitioned minimum pool for this same fixed execution. Inventory surplus is
a separate measure. Neither is the number of distinct source IDs previously
used. UAV-occupied-time workload includes transport preparation through return
and relay preparation through turnaround; CV uses population standard deviation.
Box counts, mass and sortie counts are additional balance diagnostics.

## Selection and claim scope

The exact nondominated set has eight resource-count dimensions plus workload CV.
Submission representatives minimize summed inventory-shortage counts, then summed
resource counts, then CV and canonical labels. No purchase prices are supplied,
so these counts are not monetary costs. A balance-priority representative is
also exported for each K. Full partition tables permit another ranking without
rerunning Q3 or changing resource arithmetic.

The fixed execution has no inventory-feasible independent K=2 or K=3 partition.
The minimum shortage counts are 2 and 6 respectively. This is an exact claim
only for this frozen Q3 source and whole-relay dependency interpretation. It is
not a lower bound across other E7 points or rescheduled/split/replicated tasks.

Independent validation uses graph traversal, exhaustive labeled assignments and
an event sweep; it imports no optimizer or coloring routine. Physical Q3 and
communication validity are inherited by checked source audit hashes and strict
unchanged-task comparisons. Four output packages have independently verified
group-specific calendars. Mutation tests reject changed task times, understated
minimum resources and cross-group relay dependencies.

The two xlsx files retain the official Q4 header and contain only Q4 draft pages.
They are not final whole-contest submission workbooks. Source raw files remain
immutable. Main commands: src.q4.partition, src.q4.report, q4_validate.py and
test_q4_regressions.py, using the project .venv with single-threaded BLAS.
