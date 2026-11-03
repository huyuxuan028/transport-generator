"""Convert the PSO team's frozen CSVs to GA schema v3; never regenerate orders."""
import argparse,csv,hashlib,json,math
from pathlib import Path
SOURCE_COMMIT='ac8a15d8c6d49794d490782df3c68e8a08b24d5d'
def convert(root,stop_policy='hard'):
 root=Path(root)
 def rows(name):
  with (root/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 def number(row,key):
  x=float(row[key])
  if not math.isfinite(x) or x<0:raise ValueError('Invalid '+key)
  return x
 p=json.loads((root/'params.json').read_text());loc=sorted(rows('locations.csv'),key=lambda r:int(r['location_id']));n=len(loc)
 if [int(r['location_id']) for r in loc]!=list(range(n)) or n!=p['num_customers']+1:raise ValueError('Invalid location IDs/count')
 if p['packing_mode']!=1 or not p['must_return_to_depot'] or not p['allow_multiple_trips_per_vehicle']:raise ValueError('Unsupported problem rules')
 if p['distance_unit']!='km' or p['time_unit']!='min' or p['depot_id']!=0:raise ValueError('Unexpected source units/depot')
 if stop_policy not in ('hard','soft'):raise ValueError('Invalid stop policy')
 catalog={r['id']:r for r in rows('furniture_clean.csv')};customers=[dict(id=0,weight_kg=0.,volume_m3=0.,service_minutes=0.,items=[])];orders={}
 for row in rows('orders.csv'):
  i=int(row['location_id'])
  if i in orders or not 1<=i<n:raise ValueError('Duplicate/invalid order location')
  orders[i]=row
 if set(orders)!=set(range(1,n)):raise ValueError('Missing orders')
 for i in range(1,n):
  r=orders[i];ids=[v for v in r['item_ids'].split(';') if v];items=[]
  if len(ids)!=int(r['num_items']):raise ValueError('Wrong item count')
  for k in ids:
   f=catalog[k];dims=[number(f,a) for a in ('length_m','width_m','height_m')]
   items.append(dict(catalog_id=k,dimensions_m=dims,weight_kg=number(f,'weight_kg'),volume_m3=math.prod(dims),dimension_basis='shared_catalog_not_independently_verified_package'))
  w=number(r,'total_weight_kg');v=number(r,'total_volume_m3');loading=number(r,'loading_time_min');unloading=number(r,'packing_time_min')
  if abs(sum(t['weight_kg'] for t in items)-w)>.02 or abs(sum(t['volume_m3'] for t in items)-v)>.002:raise ValueError('Item/order aggregation mismatch')
  customers.append(dict(id=i,weight_kg=w,volume_m3=v,service_minutes=unloading+(loading if p['loading_counts_as_work_time'] else 0),loading_minutes=loading,unloading_minutes=unloading,source_order_id=r['order_id'],address=loc[i]['full_address'],items=items))
 types=[];vehicles=[];source_ids=[];by_type={}
 for k,r in enumerate(rows('vehicles.csv')):
  tid=r['type_id'];v=dict(id=tid,name=r['model'],payload_kg=number(r,'max_weight_kg'),volume_m3=number(r,'max_volume_m3'),fuel_l_per_100km=number(r,'fuel_l_per_km')*100,speed_kmh=number(r,'avg_speed_kmh'),wage_eur_per_h=number(r,'wage_per_h'),maintenance_eur_per_1000km=number(r,'maintenance_per_1000km'),cargo_dimensions_m=[number(r,a) for a in ('cargo_length_m','cargo_width_m','cargo_height_m')])
  if tid in by_type and by_type[tid]!=v:raise ValueError('Type has differing per-vehicle properties; extend schema before importing')
  if tid not in by_type:by_type[tid]=v;types.append(v)
  vehicles.append(dict(v,id=f'{tid}-{k+1}',type_id=tid));source_ids.append(r['vehicle_id'])
 with (root/'distances.csv').open(newline='') as f:
  reader=csv.reader(f);header=next(reader);matrix_rows=[r for r in reader if r]
 if list(map(int,header[1:]))!=list(range(n)) or [int(r[0]) for r in matrix_rows]!=list(range(n)):raise ValueError('Matrix ID mismatch')
 d=[[float(x)*1000 for x in r[1:]] for r in matrix_rows]
 if len(d)!=n or any(len(r)!=n for r in d) or any(not math.isfinite(x) or x<0 for r in d for x in r):raise ValueError('Invalid distances')
 model=dict(depot=0,fleet_mix_is_decision=False,multiple_sequential_trips=True,all_orders_available_at_time_zero=True,time_horizon_minutes=None,schedule_average_speed_kmh=35,shift_hours=p['shift_hours'],overtime_multiplier=p['overtime_multiplier'],fuel_price_eur_per_l=p['fuel_price_per_l'],volume_buffer=p['required_free_volume_ratio'],min_stops_per_trip=p['min_customers_per_trip'],max_stops_per_trip=p['max_customers_per_trip'],stop_count_mode=stop_policy,packing_mode=1)
 coords=[[number(r,'lon'),number(r,'lat')] for r in loc];origin=coords[0];km=[[(r[0]-origin[0])*111.32*math.cos(math.radians(origin[1])),(r[1]-origin[1])*110.574] for r in coords]
 # Capacity-feasible singleton witness supplies coverage/assignment only; it is not
 # a hard-stop-feasible benchmark or an optimized plan. Search must decode it.
 trips=[];clocks=[0.]*len(vehicles)
 for i in range(1,n):
  c=customers[i];eligible=[k for k,v in enumerate(vehicles) if c['weight_kg']<=v['payload_kg'] and c['volume_m3']<=v['volume_m3']*(1-model['volume_buffer'])]
  if not eligible:raise ValueError(f'Order {i} fits no shared vehicle')
  k=min(eligible,key=lambda k:(vehicles[k]['volume_m3'],k));v=vehicles[k];distance=(d[0][i]+d[i][0])/1000;duration=distance/v['speed_kmh']*60+c['service_minutes'];trips.append(dict(vehicle=k,customers=[i],start_minutes=clocks[k],finish_minutes=clocks[k]+duration,distance_km=distance,fuel_litres=distance*v['fuel_l_per_100km']/100));clocks[k]+=duration
 return dict(schema_version=3,name='PSO-shared-Budapest-250-'+stop_policy,fleet_size=len(vehicles),vehicle_types=types,vehicles=vehicles,customers=customers,coordinates_lonlat=coords,coordinates_km=km,distance_matrix_m=d,reference_transports=trips,model=model,provenance=dict(source_repository='https://github.com/xsilentkiller/industrial-transport',source_commit=SOURCE_COMMIT,source_vehicle_ids=source_ids,source_files_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.iterdir() if f.is_file()},distance_method='Source CSV: haversine times 1.3; NOT road distances',location_method='Imported source addresses/coordinates; not independently verified deliveries',service_mapping='packing_time_min is unloading, matching their data_loader; loading also included when configured',reference_plan='Singleton capacity witness; not a hard-stop-feasible plan',stop_policy_note='Hard mode requires feasible final plans; soft mode here is audit-only and DOES NOT reproduce PSO penalties. Compare only jointly validated zero-violation final plans.'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--stop-policy',choices=['hard','soft'],default='hard');a=p.parse_args();x=convert(a.dataset,a.stop_policy);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2,allow_nan=False));print(x['name'],len(x['customers'])-1,[v['type_id'] for v in x['vehicles']])
if __name__=='__main__':main()
