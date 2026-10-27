import json,math,tempfile,unittest
from pathlib import Path
from generate import bounded_normal,generate
from import_catalog import convert,dimensions,weight

ROOT=Path(__file__).parent
class Tests(unittest.TestCase):
    def test_unit_parsers_do_not_use_maximum_supported_weight(self):
        self.assertAlmostEqual(weight('25.4 pounds'),25.4*.45359237)
        self.assertEqual(dimensions('18.5"D x 16"W x 35"H'),[18.5*.0254,16*.0254,35*.0254])
        self.assertIsNone(dimensions('26.8"L x 26.8"W'))
    def test_import_is_audited_and_strict_does_not_accept_product_dimensions(self):
        strict,proxy,audit=convert(ROOT/'data/amazon_furniture_sample.csv')
        self.assertEqual(audit['raw_rows'],312)
        self.assertGreater(len(proxy),0)
        self.assertTrue(all(x['dimension_basis']=='explicit_package' and x['weight_basis']=='shipping_or_package' for x in strict))
        self.assertEqual(len(set(x['id'] for x in proxy)),len(proxy))
    def test_proxy_mode_requires_explicit_opt_in(self):
        catalog=json.loads((ROOT/'data/catalog_proxy.json').read_text());vs=json.loads((ROOT/'data/vehicles.json').read_text())
        with self.assertRaises(ValueError):generate(catalog,vs)
    def test_seed_reproducibility_and_capacity_witness(self):
        catalog=json.loads((ROOT/'data/catalog_proxy.json').read_text());vs=json.loads((ROOT/'data/vehicles.json').read_text())
        x=generate(catalog,vs,42,2,True);y=generate(catalog,vs,42,2,True)
        self.assertEqual(x,y);self.assertEqual(x['fleet_size'],5)
        self.assertEqual(x['schema_version'],3)
        self.assertEqual(len(x['customers'])-1,102)
        self.assertEqual(len(x['vehicles']),5);self.assertEqual(len(x['vehicle_types']),3)
        for v in x['vehicles']+x['vehicle_types']:
            for key in ['wage_eur_per_h','maintenance_eur_per_1000km','speed_kmh']:
                self.assertGreater(v[key],0)
            self.assertEqual(v['speed_kmh'],x['model']['schedule_average_speed_kmh'])
        for key in ['shift_hours','overtime_multiplier','fuel_price_eur_per_l','volume_buffer',
                    'min_stops_per_trip','max_stops_per_trip']:
            self.assertIn(key,x['model'])
        visits=[];clocks=[0.]*5
        for trip in x['reference_transports']:
            v=x['vehicles'][trip['vehicle']];cs=[x['customers'][i] for i in trip['customers']]
            self.assertLessEqual(sum(c['weight_kg'] for c in cs),v['payload_kg']+1e-8)
            self.assertLessEqual(sum(c['volume_m3'] for c in cs),v['volume_m3']*(1-x['model']['volume_buffer'])+1e-8)
            self.assertGreaterEqual(trip['start_minutes'],clocks[trip['vehicle']])
            clocks[trip['vehicle']]=trip['finish_minutes'];visits+=trip['customers']
        self.assertEqual(sorted(visits),list(range(1,len(x['customers']))))

    def test_exact_250_fixed_fleet_and_buffer_witness(self):
        catalog=json.loads((ROOT/'data/catalog_proxy.json').read_text());vs=json.loads((ROOT/'data/vehicles.json').read_text())
        x=generate(catalog,vs,42,5,True,customers_target=250,fixed_fleet=True)
        self.assertEqual(x['schema_version'],3)
        self.assertEqual(len(x['customers'])-1,250)
        self.assertEqual(len(x['reference_transports']),25)
        self.assertGreaterEqual(min(len(t['customers']) for t in x['reference_transports']),3)
        self.assertFalse(x['model']['fleet_mix_is_decision'])
        self.assertEqual([v['type_id'] for v in x['vehicles']],
                         ['caddy','sprinter','sprinter','man','man'])
        for v in x['vehicles']:
            self.assertEqual(v['speed_kmh'],x['model']['schedule_average_speed_kmh'])
        for name in ('development.json','benchmark_250.json'):
            frozen=json.loads((ROOT/'data'/name).read_text())
            self.assertTrue(all(v['speed_kmh']==frozen['model']['schedule_average_speed_kmh']
                                for v in frozen['vehicles']))
        visits=[]
        for trip in x['reference_transports']:
            v=x['vehicles'][trip['vehicle']]
            demand=[x['customers'][i] for i in trip['customers']]
            self.assertLessEqual(sum(c['weight_kg'] for c in demand),v['payload_kg']+1e-8)
            self.assertLessEqual(sum(c['volume_m3'] for c in demand),v['volume_m3']*.9+1e-8)
            visits.extend(trip['customers'])
        self.assertEqual(sorted(visits),list(range(1,251)))
        self.assertEqual(x,generate(catalog,vs,42,5,True,customers_target=250,fixed_fleet=True))

    def test_invalid_customer_target_and_buffer(self):
        catalog=json.loads((ROOT/'data/catalog_proxy.json').read_text());vs=json.loads((ROOT/'data/vehicles.json').read_text())
        with self.assertRaises(ValueError):generate(catalog,vs,42,2,True,customers_target=250)
        with self.assertRaises(ValueError):generate(catalog,vs,42,2,True,volume_buffer=1)

if __name__=='__main__':unittest.main()
