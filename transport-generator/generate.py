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

def generate(catalog,vehicle_specs,seed=42,cycles=2,allow_proxy=False):
    if cycles<1:raise ValueError('cycles must be positive')
    if not catalog:raise ValueError('Empty catalog: supply audited data or explicitly allow a proxy catalog')
    if not allow_proxy and any(x['dimension_basis']!='explicit_package' or x['weight_basis']!='shipping_or_package' for x in catalog):
        raise ValueError('Proxy catalog requires --allow-proxy; do not claim assembled dimensions are packaging')
    rng=random.Random(seed);vehicles=[]
    for spec in vehicle_specs:
        v=dict(spec);lo,hi=v['fuel_range_l_per_100km']
        v['fuel_l_per_100km']=round(bounded_normal(rng,(lo+hi)/2,(hi-lo)/6,lo,hi),5)
        vehicles.append(v)
    coords=[[0.,0.]];customers=[{'id':0,'weight_kg':0.,'volume_m3':0.,'service_minutes':0.,'items':[]}]
    witness=[];counts=[];util_targets=[];clocks=[0.]*len(vehicles)
    for cycle in range(cycles):
        for k,v in enumerate(vehicles):
            requested=int(round(bounded_normal(rng,10,2,3,20)))
            utilization=bounded_normal(rng,.8,.07,.6,.95)
            counts.append(requested);util_targets.append(utilization)
            eligible=[x for x in catalog if x['mean_weight_kg']<=v['payload_kg']*utilization/requested
                and x['volume_m3']<=v['volume_m3']*utilization/requested]
            if not eligible:
                raise ValueError(f'No small-enough catalog unit to target {requested} stops on {v["id"]}')
            items=[];weight=volume=0.;attempts=0
            while max(weight/v['payload_kg'],volume/v['volume_m3']) < utilization or len(items)<requested:
                attempts+=1
                if attempts>10000:raise ValueError('Loading could not reach target safely')
                product=rng.choice(eligible)
                dims=[bounded_normal(rng,x,.03*x,.8*x,1.2*x) for x in product['mean_dimensions_m']]
                kg=bounded_normal(rng,product['mean_weight_kg'],.05*product['mean_weight_kg'],.7*product['mean_weight_kg'],1.3*product['mean_weight_kg'])
                m3=math.prod(dims)
                if weight+kg>v['payload_kg'] or volume+m3>v['volume_m3']:continue
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
    for trip in witness:
        k=trip['vehicle'];route=trip['customers'];dist=route_metres(route,d)/1000
        duration=dist/35*60+sum(customers[i]['service_minutes'] for i in route)
        trip.update({'start_minutes':clocks[k],'finish_minutes':clocks[k]+duration,'distance_km':dist,
            'fuel_litres':dist*vehicles[k]['fuel_l_per_100km']/100})
        clocks[k]+=duration
    return {'schema_version':1,'name':f'Heterogeneous-{len(customers)-1}-seed{seed}',
        'seed':seed,'cycles_per_vehicle':cycles,'vehicles':vehicles,'customers':customers,
        'coordinates_km':coords,'distance_matrix_m':d,'reference_transports':witness,
        'provenance':{'catalog_source':'Audited Kaggle Amazon furniture sample',
            'proxy_mode':allow_proxy,'normal_parameters':{'stop_count_mean':10,'stop_count_sd':2,
            'utilization_mean':.8,'utilization_sd':.07,'dimension_cv':.03,'weight_cv':.05,
            'location_mean_km':0,'location_sd_km':10,'service_mean_minutes':10,'service_sd_minutes':2},
            'warning':'Synthetic orders and locations. Sampling is truncated and capacity-conditioned; proxy dimensions/item weights are not verified package measurements.'},
        'model':{'depot':0,'one_physical_vehicle_per_type':True,'multiple_sequential_trips':True,
            'all_orders_available_at_time_zero':True,'time_horizon_minutes':None,
            'objective':'fuel_litres','schedule_average_speed_kmh':35,
            'not_implemented':['3D packing','time windows','release times','shift limits','road network','load-dependent fuel']},
        'generation_statistics':{'transports':len(witness),'requested_stops':counts,
            'mean_stops_per_transport':sum(counts)/len(counts),'total_items':sum(len(c['items']) for c in customers)}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',type=Path,default=ROOT/'data/catalog_strict.json');p.add_argument('--allow-proxy',action='store_true')
    p.add_argument('--seed',type=int,default=42);p.add_argument('--cycles',type=int,default=2)
    p.add_argument('--output',type=Path,default=ROOT/'data/development.json');a=p.parse_args()
    x=generate(json.loads(a.catalog.read_text()),json.loads((ROOT/'data/vehicles.json').read_text()),a.seed,a.cycles,a.allow_proxy)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'instance':x['name'],**x['generation_statistics']},indent=2))

if __name__=='__main__':main()
