from . import ez, generic, jar, lemlib
from .common import ExportOptions

FORMATS = {
    "LemLib (PROS)": (lemlib.export, ".cpp"),
    "JAR-Template (VEXcode)": (jar.export, ".cpp"),
    "EZ-Template (PROS)": (ez.export, ".cpp"),
    "JSON": (generic.export_json, ".json"),
    "CSV": (generic.export_csv, ".csv"),
}

__all__ = ["FORMATS", "ExportOptions"]
