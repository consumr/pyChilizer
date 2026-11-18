__title__ = "Purge imported dwg"
__doc__ = "Delete all the imported dwg from the Project. All of them."

from pyrevit import forms
from pyrevit import revit, DB
from pyrevit.framework import List

uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document

cl = DB.FilteredElementCollector(doc)

cad_imports = List[DB.ElementId]([i.Id for i in cl.OfClass(DB.ImportInstance) if not i.IsLinked])

message = 'There are {} cad imports in the model. Are you sure you want to delete them?'.format(str(len(cad_imports)))

if len(cad_imports) == 0:
    forms.alert("No Imports, well done!")
else:
    if forms.alert(message, ok=False, yes=True, no=True, exitscript=True):
        failed = 0
        with revit.Transaction("Remove dwg imports"):
            for cad_id in cad_imports:
                try:
                    doc.Delete(cad_id)
                except Exception as ex:
                    failed += 1
                    print("Could not delete {}: {}".format(cad_id, ex))
        if failed:
            forms.alert("{} of {} imports could not be deleted. "
                        "See the output window.".format(failed, len(cad_imports)))




