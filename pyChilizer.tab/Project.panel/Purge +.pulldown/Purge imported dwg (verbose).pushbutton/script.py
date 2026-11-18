# -*- coding: utf-8 -*-
"""Verbose, crash-traceable version of pyChilizer 'Purge imported dwg'.

The original looped over the ids but passed the WHOLE list to doc.Delete
on every pass (137 x a bulk delete of the same, already-deleted elements,
errors swallowed by a bare except, all in one transaction).
This version deletes one element per transaction and logs everything.
"""
import os
import sys
import time
import traceback

from pyrevit import forms, script, revit, DB
from pyrevit.framework import List

doc = revit.doc
output = script.get_output()
REPORT_ONLY = __shiftclick__  # noqa: F821  (pyRevit builtin)

# ---------------------------------------------------------------- logging --
log_path = os.path.join(
    os.environ.get("TEMP", os.path.expanduser("~")),
    "pyChilizer_purge_dwg_{}.log".format(time.strftime("%Y%m%d_%H%M%S")))
_log = open(log_path, "w")


def log(msg, echo=True):
    line = "{} | {}".format(time.strftime("%H:%M:%S"), msg)
    _log.write(line + "\n")
    _log.flush()
    try:
        os.fsync(_log.fileno())  # make sure it's on disk if Revit dies next
    except Exception:
        pass
    if echo:
        print(msg)


def eid_int(eid):
    return eid.Value if hasattr(eid, "Value") else eid.IntegerValue


# ---------------------------------------------------- failure swallowing --
class SwallowWarnings(DB.IFailuresPreprocessor):
    """Delete warnings so no dialog pops per element; let errors roll back."""
    def PreprocessFailures(self, fa):
        for f in fa.GetFailureMessages():
            if f.GetSeverity() == DB.FailureSeverity.Warning:
                log("    warning: {}".format(f.GetDescriptionText()))
                fa.DeleteWarning(f)
            else:
                log("    ERROR: {}".format(f.GetDescriptionText()))
                return DB.FailureProcessingResult.ProceedWithRollBack
        return DB.FailureProcessingResult.Continue


# ---------------------------------------------------------------- collect --
log("Document: {}".format(doc.Title))
log("Revit {} | Python {}".format(
    doc.Application.VersionNumber, sys.version.split()[0]))
log("Log file: {}".format(log_path))

imports = [i for i in DB.FilteredElementCollector(doc)
           .OfClass(DB.ImportInstance) if not i.IsLinked]

if not imports:
    log("No imports found.")
    _log.close()
    forms.alert("No Imports, well done!")
    script.exit()

rows = []
info = []
for imp in imports:
    eid = imp.Id
    typ = doc.GetElement(imp.GetTypeId())
    try:
        tname = DB.Element.Name.GetValue(typ) if typ else "?"
    except Exception:
        tname = "?"
    cat = imp.Category.Name if imp.Category else "?"
    if imp.OwnerViewId != DB.ElementId.InvalidElementId:
        ov = doc.GetElement(imp.OwnerViewId)
        placement = "view: {}".format(ov.Name if ov else imp.OwnerViewId)
    else:
        placement = "model (3D)"
    in_group = imp.GroupId != DB.ElementId.InvalidElementId
    editable = True
    if doc.IsWorkshared:
        st = DB.WorksharingUtils.GetCheckoutStatus(doc, eid)
        editable = st != DB.CheckoutStatus.OwnedByOtherUser
    skip = None
    if in_group:
        skip = "in a group"
    elif not editable:
        skip = "owned by another user"
    info.append((imp, skip))
    rows.append([output.linkify(eid), cat, tname, placement,
                 "yes" if imp.Pinned else "", skip or ""])
    log("found {} | {} | {} | {} | pinned={} | skip={}".format(
        eid_int(eid), cat, tname, placement, imp.Pinned, skip), echo=False)

output.print_table(rows, columns=["Id", "Category (file)", "Type",
                                  "Placement", "Pinned", "Skip reason"],
                   title="{} CAD imports".format(len(rows)))

to_delete = [(i, s) for i, s in info if not s]
skipped = len(info) - len(to_delete)
log("{} to delete, {} skipped".format(len(to_delete), skipped))

if REPORT_ONLY:
    log("Shift+Click: report only, nothing deleted.")
    _log.close()
    script.exit()

if not forms.alert(
        "{} CAD imports found ({} will be skipped).\n\n"
        "Delete the other {} one at a time?\n\n"
        "Progress is logged to:\n{}".format(
            len(info), skipped, len(to_delete), log_path),
        ok=False, yes=True, no=True):
    log("Cancelled by user.")
    _log.close()
    script.exit()

# ----------------------------------------------------------------- delete --
deleted, failed = 0, []
tg = DB.TransactionGroup(doc, "Remove dwg imports (verbose)")
tg.Start()
try:
    for n, (imp, _) in enumerate(to_delete, 1):
        eid = imp.Id
        label = "{} ({})".format(
            eid_int(eid), imp.Category.Name if imp.Category else "?")
        output.update_progress(n, len(to_delete))
        log("[{}/{}] deleting {} ...".format(n, len(to_delete), label))
        t = DB.Transaction(doc, "Delete import {}".format(eid_int(eid)))
        opts = t.GetFailureHandlingOptions()
        opts.SetFailuresPreprocessor(SwallowWarnings())
        opts.SetClearAfterRollback(True)
        t.SetFailureHandlingOptions(opts)
        t.Start()
        try:
            if imp.Pinned:
                imp.Pinned = False
            removed = doc.Delete(eid)
            status = t.Commit()
            if status == DB.TransactionStatus.Committed:
                deleted += 1
                log("    ok ({} element(s) removed)".format(removed.Count))
            else:
                failed.append((label, str(status)))
                log("    NOT committed: {}".format(status))
        except Exception as ex:
            if t.HasStarted() and not t.HasEnded():
                t.RollBack()
            failed.append((label, str(ex)))
            log("    FAILED: {}".format(ex))
            log(traceback.format_exc(), echo=False)
    tg.Assimilate()
except Exception:
    log("Fatal error, rolling back everything:\n" + traceback.format_exc())
    if tg.HasStarted() and not tg.HasEnded():
        tg.RollBack()
    raise
finally:
    log("Done. Deleted {}, failed {}, skipped {}.".format(
        deleted, len(failed), skipped))
    for label, why in failed:
        log("  failed: {} -> {}".format(label, why))
    _log.close()
