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
        self.assertEqual(x,y);visits=[];clocks=[0.,0.,0.]
        for trip in x['reference_transports']:
            v=x['vehicles'][trip['vehicle']];cs=[x['customers'][i] for i in trip['customers']]
            self.assertLessEqual(sum(c['weight_kg'] for c in cs),v['payload_kg']+1e-8)
            self.assertLessEqual(sum(c['volume_m3'] for c in cs),v['volume_m3']+1e-8)
            self.assertGreaterEqual(trip['start_minutes'],clocks[trip['vehicle']])
            clocks[trip['vehicle']]=trip['finish_minutes'];visits+=trip['customers']
        self.assertEqual(sorted(visits),list(range(1,len(x['customers']))))

if __name__=='__main__':unittest.main()
