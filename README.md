# Furniture Transport Generator

Initial generator for the instructor's heterogeneous multi-trip transport brief.
Python 3.10+, standard library only. The raw Kaggle sample and its API metadata
are retained with a SHA-256 audit; catalog dimensions are not silently relabelled.

## Data audit

The candidate is `crawlfeeds/furniture-products-dataset-from-amazon` on Kaggle.
The downloaded sample has 312 rows, 305 unique ASINs and 7 repeated/empty-ASIN
rows. The metadata reports CC0: Public Domain. Filtering furniture records with
parseable 3D dimensions and item/shipping weight leaves 193 proxy-capable records.
Under the strict rule requiring explicit package dimensions and shipping/package
weight, zero records qualify. This is a property of this audited sample/rule,
not a claim about all Amazon furniture data or the completeness of the provider's
full dataset. `data/catalog_audit.json` records rejected ASINs and reasons.

The sample's `package_dimensions` field can repeat `Product Dimensions`, and
`Item Weight` is not necessarily shipping weight. The importer therefore exports
both a strict catalog and a clearly labelled proxy catalog. Product sets and
multiple-package ambiguity remain a limitation; this is not verified carton data.

## Reproduce

```powershell
python import_catalog.py data/amazon_furniture_sample.csv
python generate.py --catalog data/catalog_proxy.json --allow-proxy --fleet-size 5 --cycles 2 --seed 42 --output data/development.json
python generate.py --catalog data/catalog_proxy.json --allow-proxy --customers 250 --fixed-fleet --seed 42 --output data/benchmark_250.json
python -m unittest -v test_generator
```

Strict mode is the default and fails clearly when its catalog is empty. Using
`--allow-proxy` is an explicit choice for the simplified first algorithm. To use
future verified packaging, provide a nonempty catalog with `dimension_basis` set
to `explicit_package` and `weight_basis` to `shipping_or_package` and omit that flag.

## Simulation procedure

Generate a feasible witness with five physical vehicles: two Caddies, two
Sprinters and one MAN by default. This default mix does not constrain the GA.
`--fixed-fleet` instead supplies one Caddy, two Sprinters and two MANs and sets
`model.fleet_mix_is_decision=false`; the solver must honor that flag before
claiming the fixed-fleet benchmark has been optimized. For each loading
cycle and witness vehicle, draw a target number of stops from bounded normal N(10,2), rounded to
an integer. Draw a limiting-resource utilization target from bounded N(0.8,0.07).
Select appropriately small catalog units categorically and draw their synthetic
weights and three dimensions around catalog means (CV 5% and 3%). Reject load
additions that violate either vehicle capacity. Partition the accepted furniture
units among the generated customers, then generate bounded normal coordinates
and service times. Shuffle delivery order, return to depot and start the next
transport for that same physical vehicle. Finally, split reference transports
whose volume exceeds the effective `vehicle.volume_m3 * (1 - volume_buffer)`
limit. The resulting witness is feasible for both capacity dimensions.

For seed 42 and two cycles, the included development case retains the same 102
customers and 584 synthetic furniture units as the original pilot. Ten
loading cycles requested 11, 10, 12, 11, 12, 8, 8, 10, 9 and 11 stops,
averaging 10.2. The 10% volume reserve splits one of those into two, so the
schema-v3 instance has eleven feasible reference transports. The frozen
250-customer benchmark candidate has 25 loading cycles and 32 reference
transports after buffer-based splitting. `--customers` allocates exact stop
counts across its cycles using bounded normal draws adjusted to the target.
The 10–50 stops per trip range is audited softly by the solver; capacity
splitting can create shorter trips.
Catalog suitability filtering, truncation and capacity rejection condition the
distributions; the resulting demands are not unconditioned normal samples.

## Vehicles and units

`data/vehicles.json` reproduces the instructor's three vehicle parameter sets.
They are treated as adopted course inputs, not independently reverified vehicle
specifications. Payload and volume apply separately to every trip. Overall
vehicle length is not cargo-bay length; top speed is not operating speed.

Input/outputs use kg, m3, km coordinates, nearest-integer Euclidean metres and
minutes. Fuel consumption is sampled once per type per instance from a bounded
normal around the supplied range midpoint. All vehicles of that type use the
same fixed rate in candidate comparisons. The illustrative schedule uses
`vehicles[].speed_kmh=35`, not vehicle top speed. It also retains
`model.schedule_average_speed_kmh=35` for compatibility with the initial solver.

Schema v3 adds `wage_eur_per_h`, `maintenance_eur_per_1000km`, and `speed_kmh`
to vehicle types and the five physical vehicles. `model` adds `shift_hours=8`,
`overtime_multiplier=2`, `fuel_price_eur_per_l=1.60`, `volume_buffer=0.10`,
`min_stops_per_trip=10`, and `max_stops_per_trip=50`. Overtime beyond the regular
shift is allowed and costs double the hourly wage. The regular shift and
multiplier come from the team clarification. **Wage (€12/h), diesel (€1.60/L),
maintenance (€80/110/180 per 1,000 km), speed (35 km/h), buffer (10%), and
trip-size audit range are scenario assumptions**, not measured values or
instructor-specified prices. Agree and document official-source-backed cost
inputs with the supervisor before final comparison. Earlier frozen examples
must be replaced with schema-v3 copies when the solver reads these fields.

## Simplification boundary

The generator simulates a sequence of transports, but the first optimization
instance is a static batch with all orders available at time zero. Vehicles may
make sequential trips over an unrestricted horizon. Overtime is allowed and
should be priced by the cost solver. No time windows, reloading delay, traffic
or 3D loading feasibility are claimed. Synthetic
service times generate schedules; they do not impose a deadline.

The optimization witness is feasible for aggregate weight/volume, not proven
packable furniture. Dataset proxies, generated loads and a random tour should
not be described as observed operating records.

## Catalog references

- https://www.kaggle.com/datasets/crawlfeeds/furniture-products-dataset-from-amazon
- https://www.kaggle.com/api/v1/datasets/view/crawlfeeds/furniture-products-dataset-from-amazon
- https://crawlfeeds.com/datasets/furniture-products-dataset-from-amazon

Original dataset license metadata is retained separately. Original code in this
repository is provided under MIT; this does not replace third-party data licenses.
