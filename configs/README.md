# County configs

One YAML per county. Everything the pipeline needs to know about a county that is not already
statewide. Statewide layers (DOR tax-rate polygons, SST address ranges, Comptroller municipal
boundaries, NG911 address points and roads) are declared once in `statewide.yaml` and filtered by
county name at run time.

Schema (all keys documented in `schema.yaml`):

```yaml
county: WILSON                # DOR COUNTY value, upper case
fips: "47189"
situs:                        # from the DOR layer; the fetcher verifies this list against it
  "9500": Unincorporated
  "9501": Lebanon
tiers:
  parcels: comptroller        # comptroller | county | city | request | none
  business: ecd               # ecd | city | county | commercial | permits | none
business_layers:              # any number; each becomes a business-universe source
  - id: wilson_ecd_business_points
    url: https://services1.arcgis.com/.../Business_Labels/FeatureServer/53
    name_field: BUSINESS_NAME
    where: "1=1"
city_layers:                  # limits / annexations / UGB per municipality
  - id: mtjuliet_annexations
    url: ...
    role: annexations         # limits | annexations | ugb
    date_field: Annex_Num     # or a real date field
usps_only_places:             # postal names that are NOT municipalities, and their home county
  OLD HICKORY: DAVIDSON
contacts:
  finance: "Aaron Maynard, Finance Director"
```
