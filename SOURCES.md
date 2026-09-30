# SOURCES — raw inputs, provenance and checksums

Generated 2026-09-23 by `make_sources.py`. Retrieval dates are the download dates recorded on the acquisition machine.

The raw inputs total roughly 3 GB and are **not deposited**. This file is what stands in for them. Every derived table in `Data/` is deposited in full and is sufficient to reproduce every number in the paper without re-downloading anything.

A **direct** URL was verified as a working file link. A **landing page** must be navigated; the agency does not publish a stable direct path, or we did not verify one. Regulator endpoints move, so a hash that no longer matches anything downloadable is a record of what we used, not a promise about what is served.

---

## Pennsylvania

**Pennsylvania Department of Environmental Protection**  
Landing page: `https://newdata.pa.gov/dataset/oil-and-gas-well-permits`

The table used here is the compiled well/production/permit join built for the companion study, not a single agency download. Its own provenance is recorded in that study's deposit; the hash below is of the compiled file as consumed here.

| file | size | SHA-256 | note |
|---|---|---|---|
| `P2_wells_with_logs.csv` | 1.4 MB | `0aa3b4b9e5b35de314b1ae98b4f92b55d824d953b7acba3f25a41f102519cf13` |  |

## Ohio

**Ohio Department of Natural Resources, Division of Oil and Gas Resources Management**  
Landing page: `https://ohiodnr.gov/discover-and-learn/safety-conservation/about-ODNR/oil-gas/oil-gas-resources/featured-content-3`

RBDMS is published as a weekly ZIP containing two Access databases. Production is published separately as quarterly and annual spreadsheets at https://ohiodnr.gov/business-and-industry/energy-resources/well-information/production . Reading the .mdb files needs mdbtools; no Access installation is required.

| file | size | SHA-256 | note |
|---|---|---|---|
| `Rbdmsd97Weekly.zip` | 289.4 MB | `8503c7d7d35a0586609b502f1dcdeb2384cd26c2e27b7b17a8bac432cd6ad615` |  |
| `2020_AllQtrs_FINAL_11172022.xlsx` | 726.2 kB | `dafbca66d9e39a0f4d6022e9ba9944c873b6ff63454fe419f67f68246cab4465` |  |
| `2021_AllQtrs_FINAL_11172022.xlsx` | 771.8 kB | `72901f3da4e2c6a8acf464f245832bdc49cf240fd7e5342e43eab9d6a32862cc` |  |
| `2022_AllQtrs_FINAL_03032023.xlsx` | 836.0 kB | `901aafec4633e6daa8dba5fdc1cb2a445e57d0ac89285ce5e2e2fb3cf5cebfbb` |  |
| `2023_AllQtrs_FINAL_05312024.xlsx` | 884.4 kB | `35ad1414482039166b51c88c800c022530754ec4a5a3dd81fcd6e1785d2f953b` |  |
| `2024_AllQtrs.xlsx` | 939.1 kB | `ab1d5825a40c56e5e6a24dea6febf15e4c203649c9abc24891db2c9a05970978` |  |
| `2025_AllQtrs_FINAL_20260420.xlsx` | 1.0 MB | `681e85f56755f4bef0b56ab14db1eef45105a4609f3c7c2db766b8777aa63a62` |  |
| `2026_AllQtrs_FINAL_20260820.xlsx` | 540.3 kB | `293a5e771bd65bde7a5409ce0c3aee1a96d052185f7e31bfe540b4bebc46af24` |  |
| `2026-1st_Quarter.xlsx` | 283.4 kB | `6a4ce9a426b7e43cc28c45654e7511198698c713b327921038cf22834b2148db` | superseded by 2026_AllQtrs_FINAL_20260820.xlsx |
| `2018_Horizontal_and_Vertical_Production_08292022.xlsx` | 4.0 MB | `5445e760ce3c4ec9cd8737dbcca4e3d7c7dcd8de151bd27f32767d7d7d183f5e` |  |
| `2019_Horizontal_and_Vertical_Production_11172022.xlsx` | 4.0 MB | `c23c86534f9715671010c06ff2799d2b741dd306a1364d66c90b6e5f5609e976` |  |
| `2020_Horizontal_and_Vertical_Production_11172022.xlsx` | 4.3 MB | `3a3c69f8454b01000883267e3390a820b42ed3e5ddcbb07a86cb034859bb2c6b` |  |
| `2021_Horizontal_and_Vertical_Production_03202024.xlsx` | 4.0 MB | `1fef8b47e11964782d847b46c2774597e4599f7034c9a378e87e5fd4c258e3c4` |  |
| `2022_Horizontal_and_Vertical_Production_1228223.xlsx` | 4.1 MB | `423a3746ab4d273de2aa95f77c4d7069a99cf07182fff5120bd3fa90932ccc01` |  |
| `2023_Horizontal_and_Vertical_Production_07022025.xlsx` | 3.9 MB | `d1f222a9ed1a9f271a3706800afd1aa481f16155b9038e027a21909c50526d04` |  |
| `2024_Horizontal_and_Vertical_Production_07022025.xlsx` | 3.3 MB | `379d56938a4f5b66ff37ac034a3617da41dc2eb66df763522b538fef021952ec` |  |
| `2025_Horizontal_and_Vertical_Production_20260831.xlsx` | 3.9 MB | `a1041cdae05fbd7fbe4670535a7f4beccbe6695127f5580739dfb53d4f246b6f` |  |

## New Mexico

**New Mexico Energy, Minerals and Natural Resources Department, Oil Conservation Division**  
Direct: `ftp://ftp.emnrd.nm.gov/Public/OCD/OCD Interface v1.1/`

Anonymous FTP, port 21, passive. Core tables sit at the root; the volume tables are under volumes/. The server drops data connections after roughly fifteen listings, so the fetch script reconnects and retries. Files are UTF-16 XML inside the ZIPs.

| file | size | SHA-256 | note |
|---|---|---|---|
| `wellhistory.zip` | 42.2 MB | `2511a6ddc60765e99a0e514adeba8d75b822c01a6283bce7192b86c7b3ae612c` |  |
| `wchistory.zip` | 38.6 MB | `94d59fdccc5a9086b569c21a9c1407e55c89102e63dc2213aff6b68f74929eed` |  |
| `pod.zip` | 3.2 MB | `74f5abcb95021f12e9b245478b0041681104d511c8b222fd37b45a4376e5b67a` |  |
| `podwc.zip` | 2.2 MB | `bf76151aabac21911cba307fca34fcdaf5d6eb6ca5d1fb5933b48b8f69de99ea` |  |
| `property.zip` | 1.5 MB | `31955dc7084c7e9241550dd0b421a54a3a976610f14997195440da2f6e003b9b` | not used |
| `pool.zip` | 203.5 kB | `8b63072ab915fad751a479b8dcc255716a45a23031ab8931548731599ffcc1d4` | not used |
| `spacingunit.zip` | 998.1 kB | `eed6734ededb4683eb204dd0985178ba6d1f5028792c2e53640f3089921f9252` | not used |
| `acreage.zip` | 2.2 MB | `91136acf12ede42b6641897a115ea3bab876c1b63852f90237acd340d75c3427` | not used |
| `ogrid.zip` | 2.6 MB | `e57a32306cb6d4c13912072c96e7dc408409ccc7afbdee8accc9a6ccf8f08df6` | operator registry; not used (operator comes from the well table) |
| `punevent.zip` | 3.4 MB | `c9fc474b554e69ae5fe1f1e373d22837f419ef49c1fabafb3ac195cdbbf44f82` | not used |
| `README_CORE.txt` | 174 B | `7c7779fa8a053e6fc80c9cd37730ef6567ed185bef406380a6eb859558df9ac4` | agency note |
| `README_VOLUMES.txt` | 83 B | `8adbc8e0486041416b8d5e0bb9157533c1e98ddbcf9b17eb8fb56884afbe5941` | agency note |
| `OCD Interface v1.1 Data Dictionary.xlsx` | 29.8 kB | `eae1cd092e34e84fc9021c533652165c85e2e901705f7fcabb352244eec1eb52` | agency schema documentation |
| `wcproduction.zip` | 926.3 MB | `702cf2bc4f0174f19a6a1752d65c1d675429adad3bd528d0b226865aebdc6174` |  |
| `wcinjection.zip` | 35.8 MB | `b1ddbe80cd4773c96f85e0c7c4e2629477e016412a2d572ddf5baee8159ae9b9` | injection volumes; not used (gas production only) |
| `podvolume.zip` | 436.9 MB | `cb661e2967effa4e252f72203cf16fc7417b520fa15e3ba1d49093d9647afb56` | not read by the pipeline |
| `podstorage.zip` | 174.3 MB | `893d63f8f457a50441d064d39ce29771d4c3733287eab19e7b7ea1fd407750d4` | not read by the pipeline |
| `othervolume.zip` | 96.8 MB | `283ba7ec61845f35c689138066feceb60deec97a5253d3f3fc10200fe19e6d73` | not read by the pipeline |

## Colorado

**Colorado Energy and Carbon Management Commission**  
Landing page: `https://ecmc.state.co.us/data2.html`

Annual production files are served directly at https://ecmc.state.co.us/documents/data/downloads/production/<year>_prod_reports.csv (verified), each also offered as a ZIP. The GIS shapefiles are reached from the data page; their direct paths are not recorded here because they were not verified independently of the browser session that fetched them.

| file | size | SHA-256 | note |
|---|---|---|---|
| `monthly_prod.csv` | 72.3 MB | `fc0f517f7588d01c6539e506162bbf057c10cc5eeb3300821b11fd4f7f609c28` |  |
| `WELLS_SHP.ZIP` | 15.0 MB | `6c187132e20606a0f1d4166b878a4d8fefc4472fb7d00dae0d6b5c89ae9a085b` |  |
| `DIRECTIONAL_BOTTOMHOLE_LOCATIONS_SHP.ZIP` | 1.8 MB | `937cf2321c54d04405514bfa63519e49997a53699054ef8d8ca397a9419c4c00` |  |
| `DIRECTIONAL_LINES_SHP.ZIP` | 11.0 MB | `afcbad0b97488ba5fded9bbd6f4068d4235525e812f55d6951f2096dc006edf1` | directional survey lines; not used |
| `1999_prod_reports.zip` | 4.4 MB | `d9e2048d8906bd784a98c302ced5a12acc9025b6491807fa6aece1a39530ef3b` |  |
| `2000_prod_reports.zip` | 4.6 MB | `4450bb439d9096ba91473543f99d9c15d8cf4f8aa80afde9c3b25cb9d2d289ce` |  |
| `2001_prod_reports.zip` | 4.7 MB | `5409ea939880034ab88f1bec2040ecbebe6245cd3d8ef93c6dfffb44ba15afc5` |  |
| `2002_prod_reports.zip` | 5.0 MB | `5e8cfb091b60539f5d1ad9bdac9ecccd6ead591c37b169b01112454c80743960` |  |
| `2003_prod_reports.zip` | 5.3 MB | `112b0b2428c04a107543ab62dfa064acdce2c6dca6eb791746e1873722cd9966` |  |
| `2004_prod_reports.zip` | 5.7 MB | `165cff4f190b697a63866dc86277ac010b4b1baaa93fc2dabb6326bdd3e3f56f` |  |
| `2005_prod_reports.zip` | 6.3 MB | `64f6ad208460df3282b59da63c422b9466039fb3002de55f95202ff78ca1ff87` |  |
| `2006_prod_reports.zip` | 7.0 MB | `08d1077d249b910ef302b9cc8f48bb4fe3d14f7196a82e2212271854c1b0060c` |  |
| `2007_prod_reports.zip` | 7.9 MB | `3efaeb1d7f870ab7bc895749e2dbd70dba75c270084be8a1fc8e4a82243c3acf` |  |
| `2008_prod_reports.zip` | 8.9 MB | `13985ffb3798c4a380c7b47166d2040fdce0d26673004ab067dae379dd7cb922` |  |
| `2009_prod_reports.zip` | 9.4 MB | `d01e75ca3f1ba14057eb62342d0f9afd5f42a4048b005627d6e14ff3c00262c4` |  |
| `2010_prod_reports.csv` | 93.7 MB | `17217a972718757bd2195b425a623f239f8dfab1ec80b73eeba02080fdc0c823` |  |
| `2010_prod_reports.zip` | 10.1 MB | `aa52b0e7fdd77cb7fea981871a8c3cb86ec5f28c13c5edf998e78b6d4cb97828` |  |
| `2011_prod_reports.csv` | 100.7 MB | `d972f131d23ca1438702a5140a5932f35df7d06dc6f9cea9b190f3a88f09026e` |  |
| `2011_prod_reports.zip` | 10.8 MB | `35fd1e31da927e52818029a8a7d1faa5484a4a195c4d47a02d76c76ab7756683` |  |
| `2012_prod_reports.csv` | 106.1 MB | `d4136f8e6e0308167693de22946e0fafbb94aef4ccf8ac3a351fc58b519fba4e` |  |
| `2012_prod_reports.zip` | 11.4 MB | `b4d2f5f085cddd979d344043aff3fe4566ebee297efabf5ae5de9465beed286f` |  |
| `2013_prod_reports.csv` | 109.4 MB | `4761b835723b19e0b1f496046b8c6bcd7922bfe1c99f91862d96c47311927b97` |  |
| `2013_prod_reports.zip` | 11.8 MB | `ff562d7f9873f18d38ddb10cab953538e46a209c06b5a10ca90e0fb6e3af601c` |  |
| `2014_prod_reports.csv` | 111.8 MB | `7fc9b9cd205db95dcfb339d5e7fe94650395c703a6253f1fae0bcecc7c3c535e` |  |
| `2014_prod_reports.zip` | 12.0 MB | `b181054a874b2d4ae79b1ec8d4e6fd7de2d7a25d7ac80a3c94bf3d4d80df4768` |  |
| `2015_prod_reports.csv` | 112.7 MB | `3acb1d72e90ea89365508877fa9f48cab30ba5fa979a01a23fb451b7de42a77e` |  |
| `2015_prod_reports.zip` | 12.3 MB | `65c9a97469fd56aa4f4273777ab96f106795a2c01fbaf9fcd4fabc3f82f2d014` |  |
| `2016_prod_reports.csv` | 111.9 MB | `6674ec9d54ab3d1339ee41e475afa27b67e19ab3c070ef77672fc358b3fb15a2` |  |
| `2016_prod_reports.zip` | 12.2 MB | `839ac5535e4e906057bd96cd4663b43bb8f8f591cbf588ea175337f7006e4c32` |  |
| `2017_prod_reports.csv` | 110.7 MB | `b99d6cf4e28df2f179e3f8de499eecdf07ca5e0362f019a05714640cf8ecb3cc` |  |
| `2017_prod_reports.zip` | 11.6 MB | `29f87045adc085822bc921d4fe2793a3e8e26fe6d07901edb46c8c5c2dc37945` |  |
| `2018_prod_reports.csv` | 109.2 MB | `09d5a44e22cbf4bf018dd42c6a32882a7e588ddefd9a0629ffffc29c0700a910` |  |
| `2018_prod_reports.zip` | 11.2 MB | `34f2184149f3bbbde072e546f05e16bb775b7d6f3de45fc7e8965ac7d6ad7855` |  |
| `2019_prod_reports.csv` | 107.7 MB | `9e92d963cf29bf5123a113bb2fb8c18271ab515c023a66537614e2a0483c1dd6` |  |
| `2019_prod_reports.zip` | 11.1 MB | `14dae3c30fc7975eb4b111f3980ad911d8b9876452886f40228d021f0e836cb0` |  |
| `2020_prod_reports.csv` | 103.7 MB | `c150e5b48d386e8502c0e2a162fc2513faab0f860d51a3898288a8739c9188b4` |  |
| `2020_prod_reports.zip` | 10.4 MB | `3656df463515891c3b0dddc9e0b442a42ac77a6caa9197210aaf74cacacf3723` |  |
| `2021_prod_reports.csv` | 101.9 MB | `53f35bd23e8b1f68e4f1ccd7fa67c694d82dab0ae420f5301e0b292e8fe30526` |  |
| `2021_prod_reports.zip` | 10.2 MB | `37a348ba04f2d6ee842f80f534856c7102d9c998c22ea16172a05987da19130f` |  |
| `2022_prod_reports.csv` | 99.8 MB | `60ed0d42d9f847ec58ad2357860a11d17f64b2e32a8bd92520de55bb0023837f` |  |
| `2022_prod_reports.zip` | 10.0 MB | `4304f871f6a579f90f88ae8da71c9adda278c90e7f6f24388b42388971b626bf` |  |
| `2023_prod_reports.csv` | 98.3 MB | `f2ed9fd0d83bc214aed799460074c88e9bd1a67e7b6e67008497ec1c78328214` |  |
| `2023_prod_reports.zip` | 9.7 MB | `156098457e3fec27de171cba54425fd2655731fe5c46173c3ac58f890050bc4c` |  |
| `2024_prod_reports.csv` | 96.9 MB | `0e96f90d333b908617014684df6433242b18b86ef348c0c56c7ae756590050ff` |  |
| `2024_prod_reports.zip` | 9.5 MB | `c95967bd4d5df796fff4f647eb721acdbe22b918fde174f6fd62c897a65587b1` |  |
| `2025_prod_reports.csv` | 150.1 MB | `92a12bac2a9659443cb96234baccf142b2ffc5669fea60e89a17b60b99d3fd43` |  |

---

## Verifying

```sh
cd <raw directory>
for f in *; do [ -f "$f" ] && \
    echo "$(sha256sum "$f" | cut -d' ' -f1)  $(stat -c%s "$f")  $f"; \
done | sort -k3            # compare against the tables above
```

## Known gaps

None among the raw inputs. `2018_prod_reports.csv` was missing for a time -- only its ZIP had been kept -- and was restored from that ZIP on 23 September 2026. It carries 744,618 data rows, matching the count in the Colorado build log exactly, so it is the same file the published results were computed from.

Every raw input listed above carries a SHA-256. The four New Mexico volume archives were hashed in place on the acquisition machine with PowerShell `Get-FileHash` rather than through the inventory files, because at 97 MB to 926 MB they were not moved.

**The one derived file not hashed** is `Data/NewMexico/csv/wcproduction.csv`, the 4.35 GB extraction of `wcproduction.zip` holding 48,254,734 rows. It is the largest intermediate in the project and exists only on the acquisition machine. To close the chain from archive to derived table, run

```powershell
Get-FileHash "Data\NewMexico\csv\wcproduction.csv" -Algorithm SHA256
```
