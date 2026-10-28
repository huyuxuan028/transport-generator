"""Generate static heterogeneous multi-trip routing cases with a feasible witness.

Vehicle limits are instructor inputs. Sampled numbers use bounded normal draws.
Categorical SKU selection and route shuffling are discrete, not normal variables.
"""
import argparse,json,math,random
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def bounded_normal(rng,mean,sd,low,high):
    if sd <= 0 or not low <= mean <= high:raise ValueError('Invalid normal parameters')
    for _ in range(10000):
        x=rng.gauss(mean,sd)
        if low <= x <= high:return x
    raise ValueError('Could not draw bounded normal value')

def distance_matrix(coords):
    return [[int(math.floor(math.dist(a,b)*1000+.5)) for b in coords] for a in coords]

def route_metres(route,d):return sum(d[a][b] for a,b in zip([0]+route,route+[0]))

def exact_stop_counts(rng,total,trip_count):
    """Bounded normal stop draws, adjusted to sum to an exact benchmark size."""
    if not 3*trip_count<=total<=20*trip_count:raise ValueError('Customer target is incompatible with 3..20 stops per generated transport')
    counts=[int(round(bounded_normal(rng,10,2,3,20))) for _ in range(trip_count)]
    while sum(counts)!=total:
        direction=1 if sum(counts)<total else -1
        slots=[i for i,c in enumerate(counts) if 3<=c+direction<=20]
        counts[rng.choice(slots)]+=direction
    return counts

def split_reference_trip(trip,customers,vehicle,volume_buffer):
    """Keep the same customer visit order and create capacity-feasible tours."""
    pieces=[];route=[];weight=volume=0.
    for node in trip['customers']:
        c=customers[node]
        if c['weight_kg']>vehicle['payload_kg']+1e-8 or c['volume_m3']>vehicle['volume_m3']*(1-volume_buffer)+1e-8:
            raise ValueError(f'Indivisible customer {node} exceeds the effective vehicle capacity')
        if route and (weight+c['weight_kg']>vehicle['payload_kg']+1e-8 or
                      volume+c['volume_m3']>vehicle['volume_m3']*(1-volume_buffer)+1e-8):
            pieces.append(dict(trip,customers=route));route=[];weight=volume=0.
        route.append(node);weight+=c['weight_kg'];volume+=c['volume_m3']
    if route:pieces.append(dict(trip,customers=route))
    return pieces

def generate(catalog,vehicle_specs,seed=42,cycles=2,allow_proxy=False,fleet_size=5,witness_types=None,
             customers_target=None,fixed_fleet=False,volume_buffer=.10):
    if cycles<1 or fleet_size!=5:raise ValueError('cycles must be positive and fleet_size must equal five')
    if not isinstance(volume_buffer,(int,float)) or not math.isfinite(volume_buffer) or not 0<=volume_buffer<1:
        raise ValueError('volume_buffer must be a finite fraction between 0 and 1')
    if not catalog:raise ValueError('Empty catalog: supply audited data or explicitly allow a proxy catalog')
    if not allow_proxy and any(x['dimension_basis']!='explicit_package' or x['weight_basis']!='shipping_or_package' for x in catalog):
        raise ValueError('Proxy catalog requires --allow-proxy; do not claim assembled dimensions are packaging')
    rng=random.Random(seed);vehicle_types=[]
    for spec in vehicle_specs:
        v=dict(spec);lo,hi=v['fuel_range_l_per_100km']
        v['fuel_l_per_100km']=round(bounded_normal(rng,(lo+hi)/2,(hi-lo)/6,lo,hi),5)
        vehicle_types.append(v)
    if len(set(v['id'] for v in vehicle_types))!=len(vehicle_types):raise ValueError('Vehicle type IDs must be unique')
    # A feasible generating witness, not an imposed fleet mix for optimization.
    if witness_types is None:witness_types=[0,1,1,2,2] if fixed_fleet else [i%len(vehicle_types) for i in range(fleet_size)]
    if len(witness_types)!=fleet_size or any(not isinstance(i,int) or i<0 or i>=len(vehicle_types) for i in witness_types):
        raise ValueError('Exactly fleet_size valid witness type indices are required')
    vehicles=[dict(vehicle_types[t],id=f'{vehicle_types[t]["id"]}-{k+1}',type_id=vehicle_types[t]['id'])
              for k,t in enumerate(witness_types)]
    coords=[[0.,0.]];customers=[{'id':0,'weight_kg':0.,'volume_m3':0.,'service_minutes':0.,'items':[]}]
    witness=[];counts=[];util_targets=[];clocks=[0.]*len(vehicles)
    target_counts=None if customers_target is None else exact_stop_counts(rng,customers_target,cycles*fleet_size)
    # Preserve the legacy development instance's sampling and customer IDs.
    # New exact-size instances reserve volume during loading instead of splitting
    # an otherwise full transport after its customers have been assigned.
    loading_volume_factor=1-volume_buffer if target_counts is not None else 1.
    for cycle in range(cycles):
        for k,v in enumerate(vehicles):
            requested=(target_counts[cycle*fleet_size+k] if target_counts is not None
                       else int(round(bounded_normal(rng,10,2,3,20))))
            utilization=bounded_normal(rng,.8,.07,.6,.95)
            counts.append(requested);util_targets.append(utilization)
            eligible=[x for x in catalog if x['mean_weight_kg']<=v['payload_kg']*utilization/requested
                and x['volume_m3']<=v['volume_m3']*loading_volume_factor*utilization/requested]
            if not eligible:
                raise ValueError(f'No small-enough catalog unit to target {requested} stops on {v["id"]}')
            items=[];weight=volume=0.;attempts=0
            while max(weight/v['payload_kg'],volume/(v['volume_m3']*loading_volume_factor)) < utilization or len(items)<requested:
                attempts+=1
                if attempts>10000:raise ValueError('Loading could not reach target safely')
                product=rng.choice(eligible)
                dims=[bounded_normal(rng,x,.03*x,.8*x,1.2*x) for x in product['mean_dimensions_m']]
                kg=bounded_normal(rng,product['mean_weight_kg'],.05*product['mean_weight_kg'],.7*product['mean_weight_kg'],1.3*product['mean_weight_kg'])
                m3=math.prod(dims)
                if weight+kg>v['payload_kg'] or volume+m3>v['volume_m3']*loading_volume_factor:continue
                items.append({'catalog_id':product['id'],'weight_kg':kg,'volume_m3':m3,'dimensions_m':dims,
                    'dimension_basis':product['dimension_basis'],'weight_basis':product['weight_basis']})
                weight+=kg;volume+=m3
            rng.shuffle(items)
            groups=[[] for _ in range(requested)]
            for j,item in enumerate(items):groups[j%requested].append(item)
            stops=[]
            for group in groups:
                i=len(customers)
                coords.append([round(bounded_normal(rng,0,10,-30,30),4),round(bounded_normal(rng,0,10,-30,30),4)])
                customers.append({'id':i,'weight_kg':sum(x['weight_kg'] for x in group),
                    'volume_m3':sum(x['volume_m3'] for x in group),
                    'service_minutes':round(bounded_normal(rng,10,2,2,30),3),'items':group})
                stops.append(i)
            rng.shuffle(stops)
            witness.append({'vehicle':k,'cycle':cycle,'customers':stops,'target_utilization':utilization})
    d=distance_matrix(coords)
    # The original development case keeps its exact 102 customers and visit
    # order; only that legacy path needs post-loading capacity splitting.
    if target_counts is None:
        witness=[piece for trip in witness for piece in
                 split_reference_trip(trip,customers,vehicles[trip['vehicle']],volume_buffer)]
    for trip in witness:
        k=trip['vehicle'];route=trip['customers'];dist=route_metres(route,d)/1000
        duration=dist/vehicles[k]['speed_kmh']*60+sum(customers[i]['service_minutes'] for i in route)
        trip.update({'start_minutes':clocks[k],'finish_minutes':clocks[k]+duration,'distance_km':dist,
            'fuel_litres':dist*vehicles[k]['fuel_l_per_100km']/100})
        clocks[k]+=duration
    return {'schema_version':3,'name':f'Heterogeneous-{len(customers)-1}-five-vehicle-seed{seed}',
        'seed':seed,'cycles_per_vehicle':cycles,'fleet_size':fleet_size,'vehicle_types':vehicle_types,
        'vehicles':vehicles,'customers':customers,
        'coordinates_km':coords,'distance_matrix_m':d,'reference_transports':witness,
        'provenance':{'catalog_source':'Audited Kaggle Amazon furniture sample',
            'proxy_mode':allow_proxy,'normal_parameters':{'stop_count_mean':10,'stop_count_sd':2,
            'utilization_mean':.8,'utilization_sd':.07,'dimension_cv':.03,'weight_cv':.05,
            'location_mean_km':0,'location_sd_km':10,'service_mean_minutes':10,'service_sd_minutes':2},
            'cost_parameter_basis':'Illustrative scenario assumptions, pending supervisor approval and official-source calibration; shift 8h and double overtime are team clarifications.',
            'warning':'Synthetic orders and locations. Sampling is truncated and capacity-conditioned; proxy dimensions/item weights are not verified package measurements.'},
        'model':{'depot':0,'fleet_mix_is_decision':not fixed_fleet,'multiple_sequential_trips':True,
            'all_orders_available_at_time_zero':True,'time_horizon_minutes':None,
            'objective':'fuel_litres','schedule_average_speed_kmh':35,
            'shift_hours':8,'overtime_multiplier':2.0,'fuel_price_eur_per_l':1.60,
            'volume_buffer':volume_buffer,'min_stops_per_trip':10,'max_stops_per_trip':50,
            'not_implemented':['3D packing','time windows','release times','road network','load-dependent fuel'],
            'cost_parameters_are_assumptions':True},
        'generation_statistics':{'transports':len(witness),'original_loading_cycles':cycles*fleet_size,
            'requested_stops':counts,
            'mean_stops_per_transport':sum(counts)/len(counts),
            'actual_mean_stops_per_reference_transport':(len(customers)-1)/len(witness),
            'total_items':sum(len(c['items']) for c in customers)}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',type=Path,default=ROOT/'data/catalog_strict.json');p.add_argument('--allow-proxy',action='store_true')
    p.add_argument('--seed',type=int,default=42);p.add_argument('--cycles',type=int)
    p.add_argument('--customers',type=int,help='Generate an exact number of customer orders (e.g. 250)')
    p.add_argument('--fixed-fleet',action='store_true',help='Use the given 1 Caddy, 2 Sprinter, 2 MAN fleet')
    p.add_argument('--volume-buffer',type=float,default=.10)
    p.add_argument('--fleet-size',type=int,default=5)
    p.add_argument('--output',type=Path,default=ROOT/'data/development.json');a=p.parse_args()
    cycles=a.cycles if a.cycles is not None else (max(1,math.ceil(a.customers/(a.fleet_size*10))) if a.customers is not None else 2)
    x=generate(json.loads(a.catalog.read_text()),json.loads((ROOT/'data/vehicles.json').read_text()),a.seed,cycles,a.allow_proxy,a.fleet_size,
               customers_target=a.customers,fixed_fleet=a.fixed_fleet,volume_buffer=a.volume_buffer)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'instance':x['name'],**x['generation_statistics']},indent=2))

if __name__=='__main__':main()
