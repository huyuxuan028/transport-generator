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
python generate.py --catalog data/catalog_proxy.json --allow-proxy --cycles 2 --seed 42 --output data/development.json
python -m unittest -v test_generator
```

Strict mode is the default and fails clearly when its catalog is empty. Using
`--allow-proxy` is an explicit choice for the simplified first algorithm. To use
future verified packaging, provide a nonempty catalog with `dimension_basis` set
to `explicit_package` and `weight_basis` to `shipping_or_package` and omit that flag.

## Simulation procedure

Assume one physical vehicle of each supplied type. For each loading cycle and
vehicle, draw a target number of stops from bounded normal N(10,2), rounded to
an integer. Draw a limiting-resource utilization target from bounded N(0.8,0.07).
Select appropriately small catalog units categorically and draw their synthetic
weights and three dimensions around catalog means (CV 5% and 3%). Reject load
additions that violate either vehicle capacity. Partition the accepted furniture
units among the generated customers, then generate bounded normal coordinates
and service times. Shuffle delivery order, return to depot and start the next
transport for that same physical vehicle. Each generated transport is retained
as a known feasible witness.

For seed 42 and two cycles, the included development case has 64 customers,
437 synthetic furniture units and six transports: 11, 10, 12, 11, 12 and 8 stops,
averaging 10.67. Targeting ten on average is not forcing every trip to have ten.
Catalog suitability filtering, truncation and capacity rejection condition the
distributions; the resulting demands are not unconditioned normal samples.

## Vehicles and units

`data/vehicles.json` reproduces the instructor's three vehicle parameter sets.
They are treated as adopted course inputs, not independently reverified vehicle
specifications. Payload and volume apply separately to every trip. Overall
vehicle length is not cargo-bay length; top speed is not operating speed.

Input/outputs use kg, m3, km coordinates, nearest-integer Euclidean metres and
minutes. Fuel consumption is sampled once per physical vehicle/instance from a
bounded normal around the supplied range midpoint and then kept fixed for all
candidate solutions. The illustrative schedule uses 35 km/h, not vehicle top
speed. This assumption is editable in the model metadata.

## Simplification boundary

The generator simulates a sequence of transports, but the first optimization
instance is a static batch with all orders available at time zero. Vehicles may
make sequential trips over an unrestricted horizon. No time windows, shift
limits, reloading delay, traffic or 3D loading feasibility are claimed. Synthetic
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
