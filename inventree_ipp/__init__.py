"""InvenTree IPP Label Printer Plugin."""

from plugin import InvenTreePlugin
from plugin.base.integration.MachineMixin import MachineDriverMixin

from inventree_ipp.driver import IppLabelPrinterDriver


class InvenTreeIppPlugin(MachineDriverMixin, InvenTreePlugin):
    NAME = "IPP Label Printer"
    SLUG = "inventree-ipp"
    TITLE = "IPP Label Printer"
    DESCRIPTION = "Print labels to any IPP-capable network printer"
    VERSION = "0.1.1"
    MIN_VERSION = "0.18.0"

    def get_machine_drivers(self):
        return [IppLabelPrinterDriver]
