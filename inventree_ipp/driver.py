"""InvenTree label printer driver using IPP."""

import logging

from rest_framework import serializers

from machine.machine_types import LabelPrinterBaseDriver, LabelPrinterMachine

from inventree_ipp.ipp import (
    print_job,
    get_printer_attributes,
    validate_job,
    IppError,
)

logger = logging.getLogger("inventree_ipp")


class IppLabelPrinterDriver(LabelPrinterBaseDriver):
    SLUG = "ipp-label-printer"
    NAME = "IPP Label Printer"
    DESCRIPTION = "Print labels to any IPP-capable network printer"

    MACHINE_SETTINGS = {
        "PRINTER_URI": {
            "name": "Printer URI",
            "description": "Full IPP URI (e.g. ipp://10.0.4.250:631/ipp/print)",
            "default": "",
            "required": True,
        },
        "TIMEOUT": {
            "name": "Timeout",
            "description": "Request timeout in seconds",
            "default": 30,
            "validator": int,
        },
    }

    class PrintingOptionsSerializer(serializers.Serializer):
        copies = serializers.IntegerField(default=1, min_value=1, max_value=99, label="Copies")

    def _get_uri(self, machine: LabelPrinterMachine) -> str:
        return machine.get_setting("PRINTER_URI", "D")

    def _get_timeout(self, machine: LabelPrinterMachine) -> float:
        return float(machine.get_setting("TIMEOUT", "D") or 30)

    def print_label(self, machine, label, item, **kwargs):
        uri = self._get_uri(machine)
        timeout = self._get_timeout(machine)
        copies = kwargs.get("printing_options", {}).get("copies", 1)
        machine.set_status(LabelPrinterMachine.MACHINE_STATUS.PRINTING)
        pdf_data = self.render_to_pdf_data(label, item, **kwargs)
        job_name = f"inventree-{label.name}-{item.pk}"
        try:
            result = print_job(uri, pdf_data, job_name, copies=copies, timeout=timeout)
            logger.info("Printed %s to %s (job %s)", job_name, uri, result.get("job_id"))
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.OPERATIONAL)
        except IppError as e:
            logger.error("IPP print failed for %s: %s", uri, e)
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.DISCONNECTED)
            raise ConnectionError(str(e)) from e

    def init_machine(self, machine):
        uri = self._get_uri(machine)
        if not uri:
            machine.handle_error("No PRINTER_URI configured")
            return
        try:
            validate_job(uri, timeout=self._get_timeout(machine))
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.OPERATIONAL)
        except Exception as e:
            logger.warning("Failed to connect to %s: %s", uri, e)
            machine.handle_error(str(e))

    def ping_machines(self):
        for machine in self.get_machines():
            uri = self._get_uri(machine)
            if not uri:
                machine.set_status(LabelPrinterMachine.MACHINE_STATUS.DISCONNECTED)
                continue
            try:
                attrs = get_printer_attributes(uri, timeout=5.0)
                state = attrs.get("printer-state", 0)
                reasons = attrs.get("printer-state-reasons", "none")
                if state in (3, 4):  # idle or processing
                    machine.set_status(LabelPrinterMachine.MACHINE_STATUS.OPERATIONAL)
                elif state == 5:  # stopped
                    machine.set_status(LabelPrinterMachine.MACHINE_STATUS.DISCONNECTED)
                    machine.set_status_text(f"Stopped: {reasons}")
            except Exception as e:
                machine.set_status(LabelPrinterMachine.MACHINE_STATUS.DISCONNECTED)
                machine.set_status_text(str(e))
