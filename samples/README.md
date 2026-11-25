# Test samples — fetched, not bundled

These IFC files are third-party content. Their redistribution terms are unclear
(the buildingSMART Sample-Test-Files repo carries no license grant; the
rac_advanced model is Autodesk sample content mirrored by a third party), so
they are NOT part of this repository. The test suite skips any sample that is
absent. To run the full suite, fetch them yourself:

```bash
cd samples
curl -L -o building-architecture.ifc \
  'https://raw.githubusercontent.com/buildingSMART/Sample-Test-Files/main/IFC%202.3.0.1%20(IFC%202x3%20TC1)/Simple-Scene/Building-Architecture.ifc'
curl -L -o wall-with-opening-and-window.ifc \
  'https://raw.githubusercontent.com/buildingSMART/Sample-Test-Files/main/IFC%204.0.2.1%20(IFC%204%20ADD2%20TC1)/ISO%20Spec%20-%20ReferenceView_V1.2/wall-with-opening-and-window.ifc'
curl -L -o rac-advanced-sample.ifc \
  'https://raw.githubusercontent.com/jpatacas/ifcjs-viewer/b7eab226/models/rac_advanced_sample_project.ifc'
```

| File | Source | Provenance |
|------|--------|-----------|
| building-architecture.ifc | buildingSMART Sample-Test-Files (main) | IFC2x3 simple scene, SketchUp IFC export |
| wall-with-opening-and-window.ifc | buildingSMART Sample-Test-Files (main) | IFC4 ISO spec reference file |
| rac-advanced-sample.ifc | jpatacas/ifcjs-viewer mirror | Autodesk `rac_advanced_sample_project`, IFC2x3, exported by Revit's own exporter (EDM header), Spanish variant |

Do not commit IFC files to the repository; `../.gitignore` excludes them.
