DROP TABLE IF EXISTS postcodes;
SELECT postcode, ST_CENTROID(ST_COLLECT(wkb_geometry)) as geopunt
INTO postcodes
  FROM public.inspireadressen
GROUP BY postcode;

drop table if exists postcode_gebieden;
select 	p.postcode, 
	s.code as stadsdeel_code, 
	s.naam as stadsdeel_naam, 
	g.code as gebied_code, 
	g.naam as gebied_naam, 
	bc.vollcode as wijk_code, 
	bc.naam as wijk_naam,
	b.vollcode as buurt_code,
	b.naam as buurt_naam,
	ST_X(ST_TRANSFORM(p.geopunt, 4326)) as lon, 
	ST_Y(ST_TRANSFORM(p.geopunt, 4326)) as lat 
into 	postcode_gebieden 
from 	postcodes as p, 
	gebiedsgerichtwerken as g, 
	buurtcombinatie as bc, 
	buurt as b,
	stadsdeel as s 
where 	ST_Within(p.geopunt, g.wkb_geometry) and 
	ST_Within(p.geopunt, bc.wkb_geometry) and 
	ST_Within(p.geopunt, b.wkb_geometry) and 
	ST_Within(p.geopunt, s.wkb_geometry)
order by p.postcode asc;