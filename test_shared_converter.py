import csv,importlib.util,json,tempfile,unittest
from pathlib import Path
from convert_shared_dataset import convert
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data'/'shared_source'
class ConverterTests(unittest.TestCase):
 def test_source_identity_units_and_service(self):
  x=convert(DATA);self.assertEqual(len(x['customers']),251);self.assertEqual([v['type_id'] for v in x['vehicles']],['caddy','caddy','sprinter','sprinter','man_tgl']);self.assertAlmostEqual(x['vehicles'][0]['fuel_l_per_100km'],5.35);self.assertAlmostEqual(x['customers'][1]['service_minutes'],10.2);self.assertEqual(x['coordinates_lonlat'][1],[19.042551,47.534701]);self.assertNotIn('road_network',x)
  with (DATA/'distances.csv').open() as f:r=csv.reader(f);next(r);row=next(r)
  self.assertAlmostEqual(x['distance_matrix_m'][0][1],float(row[2])*1000)
 def test_reject_unsupported_policy(self):
  with self.assertRaises(ValueError):convert(DATA,'ignore')
 def test_model_retains_shared_parameters(self):
  x=convert(DATA);p=json.loads((DATA/'params.json').read_text());self.assertEqual(x['model']['volume_buffer'],p['required_free_volume_ratio']);self.assertEqual(x['model']['shift_hours'],8);self.assertEqual(x['model']['overtime_multiplier'],2);self.assertEqual(x['model']['stop_count_mode'],'hard')
if __name__=='__main__':unittest.main()
