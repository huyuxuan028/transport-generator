"""Audit the instructor's candidate Kaggle furniture sample (stdlib only).

Only explicit Package Dimensions plus a weight are accepted as strict packaging.
Product dimensions may be exported separately as clearly labelled proxies.
"""
import argparse, ast, csv, hashlib, json, math, re
from pathlib import Path

DATASET='https://www.kaggle.com/datasets/crawlfeeds/furniture-products-dataset-from-amazon'

def dimensions(text):
    text=str(text).lower().strip()
    # Require a three-axis expression with a stated unit; reject 2D mats.
    unit=.0254 if 'inch' in text or '"' in text else .01 if re.search(r'\bcm\b',text) else .001 if re.search(r'\bmm\b',text) else None
    if unit is None:return None
    parts=re.split(r'\s*[x×]\s*',text)
    if len(parts)!=3:return None
    nums=[]
    for part in parts:
        m=re.search(r'\d+(?:\.\d+)?',part)
        if not m:return None
        nums.append(float(m.group())*unit)
    return nums if all(.005 <= x <= 10 for x in nums) else None

def weight(text):
    m=re.search(r'(\d+(?:\.\d+)?)\s*(kilograms?|kg|pounds?|lbs?|ounces?|oz|grams?|g)\b',str(text),re.I)
    if not m:return None
    unit=m.group(2).lower()
    factor=1 if unit.startswith('k') else .45359237 if unit.startswith(('p','lb')) else .028349523125 if unit.startswith(('o','oz')) else .001
    value=float(m.group(1))*factor
    return value if 0 < value < 10000 else None

def read_fields(row):
    try:values=ast.literal_eval(row.get('specifications','[]'))
    except (ValueError,SyntaxError):values=[]
    fields={}
    for text in values if isinstance(values,list) else []:
        if isinstance(text,str) and ':' in text:
            k,v=text.split(':',1);fields.setdefault(k.strip().lower(),v.strip())
    return fields

def convert(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    strict=[];proxy=[];rejected=[];seen=set();duplicates=0
    for index,row in enumerate(rows,2):
        key=row.get('asin','').strip()
        if not key or key in seen:
            duplicates+=1;continue
        seen.add(key)
        if 'Furniture' not in row.get('categories',''):
            rejected.append({'asin':key,'reason':'Not classified as Furniture in the sample'});continue
        fields=read_fields(row)
        explicit=fields.get('package dimensions','')
        raw_dimensions=explicit or row.get('package_dimensions','')
        dims=dimensions(raw_dimensions)
        raw_weight=fields.get('shipping weight') or fields.get('package weight') or fields.get('item weight','')
        kg=weight(raw_weight)
        if dims is None or kg is None:
            rejected.append({'asin':key,'reason':'Missing/unparsed 3D dimensions or an explicit item/shipping weight'});continue
        basis='explicit_package' if explicit else 'unverified_column_or_assembled_proxy'
        item={'id':key,'name':row.get('title',''),'mean_dimensions_m':dims,'mean_weight_kg':kg,
            'volume_m3':math.prod(dims),'dimension_basis':basis,
            'weight_basis':'shipping_or_package' if fields.get('shipping weight') or fields.get('package weight') else 'item_weight_proxy',
            'raw_dimensions':raw_dimensions,'raw_weight':raw_weight,'source_row':index,
            'source_url':row.get('url') or DATASET,'dataset_url':DATASET,
            'interpretation':'A catalog unit may represent a set or several packages; count/multipackage ambiguity is retained.'}
        proxy.append(item)
        if basis=='explicit_package' and item['weight_basis']=='shipping_or_package':strict.append(item)
    audit={'dataset':DATASET,'license':'CC0: Public Domain as reported by the public Kaggle metadata API',
        'raw_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'raw_rows':len(rows),
        'unique_asins':len(seen),'duplicate_or_empty_asin_rows':duplicates,'strict_packaging_records':len(strict),
        'proxy_capable_records':len(proxy),'rejected_unique_records':len(rejected),'rejections':rejected,
        'warning':'A field called package_dimensions is not treated as verified packaging: source examples repeat Product Dimensions. Item weight is not automatically shipping weight.'}
    return strict,proxy,audit

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv',type=Path);p.add_argument('--output-dir',type=Path,default=Path(__file__).parent/'data');a=p.parse_args()
    strict,proxy,audit=convert(a.csv);a.output_dir.mkdir(parents=True,exist_ok=True)
    for name,payload in [('catalog_strict.json',strict),('catalog_proxy.json',proxy),('catalog_audit.json',audit)]:
        (a.output_dir/name).write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='rejections'},indent=2))

if __name__=='__main__':main()
