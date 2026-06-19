# OMG 20250201 Machine-Readable Artifacts

This directory contains the OMG normative machine-readable artifacts used as
source input for the SysML v2 effort: MOF XMI abstract syntax artifacts and KPAR
model-library archives.

Formal OMG specification pages:

- KerML 1.0: https://www.omg.org/spec/KerML/1.0/About-KerML
- SysML 2.0: https://www.omg.org/spec/SysML/2.0/About-SysML

## Abstract Syntax XMI

Fetched on 2026-06-16 from the formal OMG specification pages.

| File | OMG URL | OMG file ID | SHA-256 |
| --- | --- | --- | --- |
| `KerML.xmi` | https://www.omg.org/spec/KerML/20250201/KerML.xmi | `ptc/25-04-04` | `45b18775afe2b2fcdc70e24f37c6d2f344defcc3f38a02075a193354e2d7b466` |
| `SysML.xmi` | https://www.omg.org/spec/SysML/20250201/SysML.xmi | `ptc/25-02-15` | `caa65d54f56798bf7582d173f7567e1eea37a49c45984f8bd7df145011cf8c6f` |

## KPAR Model Libraries

Fetched on 2026-06-19 by direct `curl -L --fail` from the formal OMG URLs below.
Each response was HTTP 200 and had ZIP magic bytes (`PK\x03\x04`). OMG served
these archives with `content-type: text/plain; charset=UTF-8`, so verification
uses ZIP structure and SHA-256 rather than MIME type.

| File | OMG URL | OMG file ID | Direct curl status | Bytes | SHA-256 |
| --- | --- | --- | --- | ---: | --- |
| `Semantic-Library.kpar` | https://www.omg.org/spec/KerML/20250201/Semantic-Library.kpar | `ptc/25-04-17` | HTTP 200, ZIP magic | 33031 | `6d9e311646a557cb08b64313cab6a7931109751b2ac7fbfcefad5c2216a6167b` |
| `Data-Type-Library.kpar` | https://www.omg.org/spec/KerML/20250201/Data-Type-Library.kpar | `ptc/25-04-18` | HTTP 200, ZIP magic | 4260 | `957e4ff5c60f7fc5eedaf0b6d4f776856061c0aa7a424e260eeccb8d6ed7bfbd` |
| `Function-Library.kpar` | https://www.omg.org/spec/KerML/20250201/Function-Library.kpar | `ptc/25-04-19` | HTTP 200, ZIP magic | 15929 | `a8319da3ab1d8ffc0f390ea1aef29d85a00451655c41a9267ce396845c2b1c8d` |
| `Systems-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Systems-Library.kpar | `ptc/25-04-24` | HTTP 200, ZIP magic | 27577 | `df7d8b2c6e08232ca7ce123a63148949c383fcbeaeba8d89c27ceece43793a1f` |
| `Analysis-Domain-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Analysis-Domain-Library.kpar | `ptc/25-04-25` | HTTP 200, ZIP magic | 6035 | `96f0230cd7091faa2d27345b7f7748e0249fb42cfbdc48265ce6e82d6ecc1b38` |
| `Cause-and-Effect-Domain-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Cause-and-Effect-Domain-Library.kpar | `ptc/25-04-26` | HTTP 200, ZIP magic | 3135 | `c097c70232b8c9d38acbc92b402d8caa3b67f4d847dade0f29994164a4e25e94` |
| `Geometry-Domain-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Geometry-Domain-Library.kpar | `ptc/25-04-27` | HTTP 200, ZIP magic | 7169 | `9cc40d628dfe8717b79af74297a7115103e3469708a54221cac0e42344ed8427` |
| `Metadata-Domain-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Metadata-Domain-Library.kpar | `ptc/25-04-28` | HTTP 200, ZIP magic | 4573 | `5c51cd3b21b60c89742dbba0f59f25bdbc34224d05e32975d77bb93092458b9b` |
| `Quantities-and-Units-Domain-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Quantities-and-Units-Domain-Library.kpar | `ptc/25-04-29` | HTTP 200, ZIP magic | 154748 | `81a6e7264a9f287e482ec5b35f8ef98725b81f393e0b2e82dae3599511c0adc7` |
| `Requirement-Derivation-Domain-Library.kpar` | https://www.omg.org/spec/SysML/20250201/Requirement-Derivation-Domain-Library.kpar | `ptc/25-04-30` | HTTP 200, ZIP magic | 2650 | `a136e72ac6afbd96ede220cfec77fd54c75242d577d3f5ab9e5278b25baee6e5` |

Use these files as immutable downloaded inputs. Do not edit them in place. If
OMG publishes an updated artifact set, add or replace files deliberately,
refresh this manifest, and update `docs/sysml-v2/MAPPING_DECISIONS.md`.
